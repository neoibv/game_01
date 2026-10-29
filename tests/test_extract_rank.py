from datetime import datetime, timedelta

import httpx
import respx

from giveaway import db
from giveaway.cli import collect, remind_and_expire
from giveaway.collectors.youtube import YouTubeClient
from giveaway.extract import API_URL, Extracted, Extractor
from giveaway.rank import KST, parse_deadline, score

from test_collect import CHANNELS, FILTERS, _mock

NOW = datetime(2026, 11, 1, 12, 0, tzinfo=KST)


def _tool_response(payload):
    return {"content": [{"type": "tool_use", "name": "record_giveaway", "input": payload}]}


def test_parse_deadline_date_only_is_end_of_day_kst():
    assert parse_deadline("2026-11-05") == datetime(2026, 11, 5, 23, 59, 59, tzinfo=KST)
    assert parse_deadline("") is None
    assert parse_deadline("내일") is None


def test_score_prefers_urgent_easy_expensive_it():
    hi = score(tags=["it"], prize_value_est=600000, entry_methods=["comment"],
               deadline="2026-11-01", now=NOW)
    lo = score(tags=["entertainment"], prize_value_est=0, entry_methods=["form"],
               deadline="2026-12-31", now=NOW)
    assert hi > lo and 0 <= lo and hi <= 100


def test_auto_enterable_only_for_plain_click():
    assert Extracted(entry_methods=["click"]).auto_enterable
    assert not Extracted(entry_methods=["click"], macro_banned=True).auto_enterable
    assert not Extracted(entry_methods=["click", "comment"]).auto_enterable
    assert not Extracted(entry_methods=["click"], needs_login_or_captcha=True).auto_enterable


@respx.mock
def test_extractor_parses_tool_use():
    respx.post(API_URL).respond(json=_tool_response(
        {"is_giveaway": True, "is_ended": False, "prize": "키보드 3명",
         "entry_methods": ["comment"], "deadline": "2026-11-05", "unknown_field": 1}))
    ex = Extractor("k").extract("본문", title="t", published_at="2026-10-30", today="2026-11-01")
    assert ex.is_giveaway and ex.prize == "키보드 3명" and ex.deadline == "2026-11-05"


@respx.mock
def test_extractor_raises_without_tool_use():
    respx.post(API_URL).respond(json={"content": [{"type": "text", "text": "hi"}]})
    try:
        Extractor("k").extract("본문", title="t", published_at="", today="")
        raise AssertionError("raise 안 됨")
    except ValueError:
        pass


class FakeExtractor:
    def __init__(self, result=None, error=None):
        self.result, self.error = result, error

    def extract(self, *a, **k):
        if self.error:
            raise self.error
        return self.result


@respx.mock(assert_all_called=False)
def test_collect_stores_extracted_fields_and_notifies(tmp_path, respx_mock):
    _mock(respx_mock, description="증정 이벤트")
    conn = db.connect(tmp_path / "t.db")
    sent = []
    ex = Extracted(is_giveaway=True, prize="SSD", prize_value_est=100000,
                   entry_methods=["comment"], deadline="2999-01-01")
    s = collect(conn, YouTubeClient("k", httpx.Client()), CHANNELS, FILTERS, sent.append,
                FakeExtractor(ex))
    assert s["new"] == 1
    row = conn.execute("SELECT * FROM events").fetchone()
    assert row["prize"] == "SSD" and row["status"] == "notified" and row["score"] > 0
    assert any("SSD" in m for m in sent)


@respx.mock(assert_all_called=False)
def test_collect_skips_non_giveaway_silently(tmp_path, respx_mock):
    _mock(respx_mock, description="증정 이벤트")
    conn = db.connect(tmp_path / "t.db")
    sent = []
    s = collect(conn, YouTubeClient("k", httpx.Client()), CHANNELS, FILTERS, sent.append,
                FakeExtractor(Extracted(is_giveaway=False)))
    assert s["new"] == 0 and s["skipped"] == 1
    assert not any("v1" in m for m in sent)
    assert conn.execute("SELECT status FROM events").fetchone()["status"] == "skipped"


@respx.mock(assert_all_called=False)
def test_collect_falls_back_when_extract_fails(tmp_path, respx_mock):
    _mock(respx_mock, description="증정 이벤트")
    conn = db.connect(tmp_path / "t.db")
    sent = []
    s = collect(conn, YouTubeClient("k", httpx.Client()), CHANNELS, FILTERS, sent.append,
                FakeExtractor(error=RuntimeError("boom")))
    assert s["new"] == 1 and any("이벤트 후보" in m for m in sent)


def test_remind_once_then_expire(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    db.add_event(conn, source="youtube", source_url="u", title="T", host="h", matched=[], raw_text="")
    db.update_event(conn, "u", status="notified", deadline="2026-11-01")
    sent = []
    assert remind_and_expire(conn, sent.append, NOW) == {"reminded": 1, "expired": 0}
    assert remind_and_expire(conn, sent.append, NOW) == {"reminded": 0, "expired": 0}
    assert len(sent) == 1
    later = NOW + timedelta(days=3)
    assert remind_and_expire(conn, sent.append, later)["expired"] == 1


def test_old_db_gets_migrated(tmp_path):
    import sqlite3
    p = tmp_path / "old.db"
    c = sqlite3.connect(p)
    c.executescript("CREATE TABLE events (id INTEGER PRIMARY KEY, source TEXT NOT NULL, "
                    "source_url TEXT NOT NULL UNIQUE, title TEXT NOT NULL, host TEXT, matched TEXT, "
                    "raw_text TEXT, first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, "
                    "status TEXT NOT NULL DEFAULT 'new');")
    c.close()
    conn = db.connect(p)
    assert "deadline" in {r["name"] for r in conn.execute("PRAGMA table_info(events)")}
