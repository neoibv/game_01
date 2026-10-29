from datetime import date
from pathlib import Path

import httpx
import respx

from giveaway.collectors import sites

FX = Path(__file__).parent / "fixtures"
TODAY = date(2026, 10, 29)


def _read(name):
    return (FX / name).read_text(encoding="utf-8")


def test_parse_eventskr():
    items = sites.parse_eventskr(_read("eventskr.html"), TODAY)
    assert len(items) == 5
    it = next(i for i in items if i.url.endswith("id=188"))
    assert it.host == "소상공인시장진흥공단" and it.category == "인증샷"
    assert it.prize == "디지털 온누리상품권 1만원" and it.deadline == "2026-11-15"
    assert it.url == "https://events.kr/event.php?id=188"


def test_parse_jupjup():
    items = sites.parse_jupjup(_read("jupjup.html"))
    assert len(items) >= 5
    first = items[0]
    assert first.url.startswith("https://jupjup.app/g/") and first.host == "다나와"
    assert first.prize == ""  # '확인 필요'는 빈 값
    assert any(i.prize == "네이버페이 포인트" for i in items)


def test_parse_danawa_dedupes_and_reads_badge():
    items = sites.parse_danawa(_read("danawa.html"))
    urls = [i.url for i in items]
    assert len(urls) == len(set(urls)) >= 4
    assert any(i.category == "체험단" and "<br>" not in i.title for i in items)


def test_month_day_rolls_over_year():
    assert sites._month_day_to_iso(1, 5, date(2026, 12, 20)) == "2027-01-05"
    assert sites._month_day_to_iso(11, 1, date(2026, 10, 29)) == "2026-11-01"


@respx.mock
def test_fetch_all_survives_one_failure_and_flags_empty():
    respx.get("https://events.kr/").respond(500)
    respx.get("https://jupjup.app/").respond(text=_read("jupjup.html"))
    respx.get("https://event.danawa.com/").respond(text="<html>구조 바뀜</html>")
    items, failed = sites.fetch_all(TODAY, httpx.Client(follow_redirects=True))
    assert items and all(i.source == "jupjup" for i in items)
    assert any(f.startswith("eventskr") for f in failed) and any("0건" in f for f in failed)


def _items():
    return [
        sites.SiteItem("jupjup", "https://jupjup.app/g/a", "SSD 추첨 이벤트", "다나와", prize="SSD"),
        sites.SiteItem("eventskr", "https://events.kr/event.php?id=1", "SSD 추첨 이벤트", "다른곳"),
        sites.SiteItem("eventskr", "https://events.kr/event.php?id=2", "시민 설문조사", "시청"),
    ]


class _Ex:
    def __init__(self, giveaway):
        self.giveaway = giveaway

    def extract(self, text, **k):
        from giveaway.extract import Extracted
        return Extracted(is_giveaway=self.giveaway, prize="SSD", entry_methods=["click"])


def test_collect_sites_dedupes_by_title_and_filters_with_ai(tmp_path):
    from giveaway import db
    from giveaway.cli import collect_sites
    conn = db.connect(tmp_path / "t.db")
    sent = []
    s = collect_sites(conn, _items(), {"include": ["추첨"]}, sent.append, _Ex(True))
    assert s["new"] == 2 and len(sent) == 2  # 같은 제목 1건은 중복으로 제외, 설문은 AI가 True라 통과
    sent.clear()
    assert collect_sites(conn, _items(), {"include": ["추첨"]}, sent.append, _Ex(True))["new"] == 0


def test_collect_sites_without_ai_uses_keywords_or_prize(tmp_path):
    from giveaway import db
    from giveaway.cli import collect_sites
    conn = db.connect(tmp_path / "t.db")
    sent = []
    s = collect_sites(conn, _items(), {"include": ["추첨"]}, sent.append, None)
    assert s["new"] == 1 and s["skipped"] == 1  # 설문은 건너뜀


def test_collect_sites_respects_notify_cap_without_losing_items(tmp_path, monkeypatch):
    from giveaway import cli, db
    monkeypatch.setattr(cli, "MAX_NOTIFY_PER_RUN", 1)
    conn = db.connect(tmp_path / "t.db")
    items = [sites.SiteItem("jupjup", f"https://jupjup.app/g/{i}", f"이벤트 {i}", prize="x")
             for i in range(3)]
    sent = []
    cli.collect_sites(conn, items, {"include": []}, sent.append, None)
    assert len(sent) == 1
    cli.collect_sites(conn, items, {"include": []}, sent.append, None)  # 다음 실행에서 이어서
    assert len(sent) == 2
