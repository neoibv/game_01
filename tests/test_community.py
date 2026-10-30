import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
import respx

from giveaway import approval, cli, db
from giveaway.collectors import community
from giveaway.collectors.youtube import API, YouTubeClient
from giveaway.extract import Extracted

FX = Path(__file__).parent / "fixtures" / "community.html"
NOW = datetime(2026, 10, 30, tzinfo=timezone.utc)


def test_parse_age_days():
    assert community.parse_age_days("4일 전(수정됨)") == 4
    assert community.parse_age_days("3주 전") == 21
    assert community.parse_age_days("1개월 전") == 30
    assert community.parse_age_days("5시간 전") == 0
    assert community.parse_age_days("2 weeks ago") == 14
    assert community.parse_age_days("알 수 없음") is None


def test_parse_posts_reads_video_ids_from_real_urls_and_dedupes():
    posts = community.parse_posts(FX.read_text(encoding="utf-8"), "UC1")
    assert [p.post_id for p in posts] == ["UgkxPOST1", "UgkxPOST2", "UgkxPOST3"]
    first = posts[0]
    assert first.video_ids == ["YuLq2RdS1Z4"]  # 본문 텍스트는 '...'로 잘려도 URL에서 읽는다
    assert first.age_days == 4 and first.edited
    assert first.url == "https://www.youtube.com/post/UgkxPOST1"
    assert posts[1].video_ids == ["_FviurU8FR8"]  # shorts 링크
    assert community.parse_posts("<html>no data</html>", "UC1") == []


@respx.mock
def test_fetch_posts_uses_channel_posts_url():
    r = respx.get("https://www.youtube.com/channel/UC1/posts").respond(text=FX.read_text(encoding="utf-8"))
    assert len(community.fetch_posts("UC1", httpx.Client())) == 3
    assert "ko-KR" in r.calls.last.request.headers["accept-language"]


class PostExtractor:
    """게시물 본문에 따라 결과를 돌려주는 가짜 추출기."""
    def __init__(self):
        self.calls = []

    def extract(self, text, **kw):
        self.calls.append(kw)
        if "준비했습니다" in text:
            return Extracted(is_giveaway=True, product="아이폰듀오 애플랜덤박스", entry_methods=["subscribe", "like", "comment"],
                             entry_steps=["보겸TV·보겸s 구독", "게시글 좋아요", "게시글에 댓글"],
                             required_keywords=["보겸", "아이폰듀오"], comment_target="both", membership="optional",
                             entry_format="'보겸','아이폰듀오' 두 단어 사용")
        return Extracted(is_giveaway=False, is_ended=True)

    def draft_comment(self, title, desc, ex):
        return "이번에 꼭 받고 싶어요. 아이폰듀오 기대됩니다. 보겸 화이팅"


def _yt_mock(router):
    router.get(f"{API}/videos").respond(json={"items": [{
        "id": "YuLq2RdS1Z4", "snippet": {"title": "아이폰듀오 악세서리만 1,000,000원", "description": "보겸TV 보겸s",
                                         "publishedAt": "2026-10-21T06:50:19Z", "channelId": "UCS", "channelTitle": "보겸S"}}]})


CH = {"name": "보겸TV", "community": True, "format_in_video": True, "max_age_days": 14,
      "usual_methods": ["subscribe", "like", "comment"], "tags": ["entertainment"]}


@respx.mock(assert_all_called=False)
def test_collect_community_confirms_recent_real_posts_only(tmp_path, respx_mock):
    _yt_mock(respx_mock)
    conn = db.connect(tmp_path / "t.db")
    posts = community.parse_posts(FX.read_text(encoding="utf-8"), "UC1")
    res = cli.collect_community(conn, YouTubeClient("k", httpx.Client()), CH, "UC1", PostExtractor(),
                                filters={}, subscribe_channels=["UC1", "UCS"], now=NOW, fetch=lambda cid: posts)
    assert len(res["entries"]) == 1  # 3주·1개월 된 게시물은 14일 기준 밖
    entry = res["entries"][0].entry
    assert "[보겸TV 게시물]" in entry.title and entry.target == "게시글(직접 작성) + 연결 영상"
    assert entry.linked and "YuLq2RdS1Z4" in entry.linked[0]
    assert entry.comment_rule.startswith("키워드 보겸, 아이폰듀오")
    (vurl, v), = res["video_events"]
    row = conn.execute("SELECT * FROM events WHERE source_url = ?", (vurl,)).fetchone()
    assert row["video_id"] == "YuLq2RdS1Z4" and row["channel_id"] == "UCS" and row["host"] == "보겸S"
    assert json.loads(row["requirements"])["subscribe_channels"] == ["UC1", "UCS"]
    # 두 번째 실행에서는 이미 본 게시물이라 다시 알리지 않는다
    again = cli.collect_community(conn, YouTubeClient("k", httpx.Client()), CH, "UC1", PostExtractor(),
                                  filters={}, subscribe_channels=[], now=NOW, fetch=lambda cid: posts)
    assert again["entries"] == [] and again["video_events"] == []


def test_collect_community_reports_fetch_failure_without_bypass(tmp_path):
    conn = db.connect(tmp_path / "t.db")

    def blocked(cid):
        raise httpx.HTTPStatusError("429", request=httpx.Request("GET", "http://x"),
                                    response=httpx.Response(429))

    res = cli.collect_community(conn, None, CH, "UC1", PostExtractor(), filters={}, subscribe_channels=[],
                                now=NOW, fetch=blocked)
    assert "HTTPStatusError" in res["error"]
    assert "0건" in cli.collect_community(conn, None, CH, "UC1", PostExtractor(), filters={},
                                         subscribe_channels=[], now=NOW, fetch=lambda c: [])["error"]


class FakeTG:
    chat_id = "42"

    def __init__(self):
        self.sent, self._id = [], 500

    def send(self, text, buttons=None, reply_to=None):
        self._id += 1
        self.sent.append((self._id, text, buttons))
        return self._id

    def clear_buttons(self, mid):
        pass

    def answer_callback(self, *a, **k):
        pass


@respx.mock(assert_all_called=False)
def test_collect_end_to_end_sends_digest_manual_draft_and_format_request(tmp_path, respx_mock):
    respx_mock.get(f"{API}/channels").respond(json={"items": [{
        "id": "UC1", "contentDetails": {"relatedPlaylists": {"uploads": "UU1"}}}]})
    _yt_mock(respx_mock)
    conn = db.connect(tmp_path / "t.db")
    tg, sent = FakeTG(), []
    posts = community.parse_posts(FX.read_text(encoding="utf-8"), "UC1")
    chans = [{**CH, "handle": "@x", "last_format": "지난 양식"}]
    cli.collect(conn, YouTubeClient("k", httpx.Client()), chans, {"include": []}, sent.append,
                PostExtractor(), tg, community_fetch=lambda cid: posts)
    digest_msg = next(m for m in sent if m.startswith("<유튜브>"))
    assert "댓글 위치: 게시글(직접 작성) + 연결 영상" in digest_msg and "연결 영상: 아이폰듀오 악세서리만" in digest_msg
    texts = [t for _, t, _ in tg.sent]
    manual = next(t for t in texts if "복사해" in t)
    assert "https://www.youtube.com/post/UgkxPOST1" in manual and "검수" in manual
    fmt = next(t for t in tg.sent if "말로 안내" in t[1])
    assert "지난 양식" in fmt[1] and fmt[2][0][0].startswith("⏭")  # 영상 쪽은 사용자에게 양식을 묻는다
    statuses = {r["source_url"]: r["status"] for r in conn.execute("SELECT source_url, status FROM events")}
    assert statuses["https://www.youtube.com/watch?v=YuLq2RdS1Z4"] == "awaiting_format"


# ---- 이미 쓴 댓글 검수 ----
def test_review_comment_detects_missing_keywords_and_lines():
    ok = approval.review_comment("보겸 형 감사합니다\n아이폰듀오 기대돼요", ["보겸", "아이폰듀오"], 2)
    assert ok["ok"]
    bad = approval.review_comment("보겸 형 선물 감사합니다", ["보겸", "아이폰듀오"], 2)
    assert not bad["ok"] and bad["missing"] == ["아이폰듀오"] and bad["lines"] == 1
    assert "아이폰듀오" in bad["fixed"] and len(bad["fixed"].split("\n")) >= 2
    assert bad["fixed"].startswith("보겸 형 선물 감사합니다")  # 기존 내용은 보존


def _event_with_rules(tmp_path, entered=False):
    conn = db.connect(tmp_path / "t.db")
    db.add_event(conn, source="youtube_post", source_url="https://www.youtube.com/post/P", title="t",
                 host="보겸TV", matched=[], raw_text="")
    eid = db.event_id_by_url(conn, "https://www.youtube.com/post/P")
    conn.execute("UPDATE events SET requirements=? WHERE id=?",
                 (json.dumps({"keywords": ["보겸", "아이폰듀오"], "min_lines": 2}), eid))
    db.set_draft(conn, eid, "초안", 777)
    if entered:
        db.add_entry(conn, eid, "comment", "cmt9")
    conn.commit()
    return conn, eid


def _reply(text, to):
    return {"update_id": 1, "message": {"chat": {"id": 42}, "text": text, "reply_to_message": {"message_id": to}}}


def test_review_reply_flags_wrong_format_and_proposes_fix(tmp_path):
    conn, eid = _event_with_rules(tmp_path)
    tg = FakeTG()
    approval.handle_update(conn, tg, None, _reply("검수\n보겸 선물 주세요", 777), gap_state={}, gap_seconds=0)
    text, buttons = tg.sent[-1][1], tg.sent[-1][2]
    assert "❌" in text and "빠진 키워드: 아이폰듀오" in text and "줄 수 부족" in text and "수정 제안" in text
    assert buttons is None  # 직접 쓴 댓글은 버튼 없이 수동 수정 안내
    assert "⋮" in text


def test_review_reply_accepts_correct_comment(tmp_path):
    conn, eid = _event_with_rules(tmp_path)
    tg = FakeTG()
    approval.handle_update(conn, tg, None, _reply("검수: 보겸님 감사해요\n아이폰듀오 받고싶어요", 777),
                           gap_state={}, gap_seconds=0)
    assert tg.sent[-1][1].startswith("✅")


def test_review_without_known_format_asks_for_format_first(tmp_path):
    conn, eid = _event_with_rules(tmp_path)
    conn.execute("UPDATE events SET requirements='{}' WHERE id=?", (eid,))
    conn.commit()
    tg = FakeTG()
    approval.handle_update(conn, tg, None, _reply("검수 아무 댓글", 777), gap_state={}, gap_seconds=0)
    assert "양식" in tg.sent[-1][1] and "검수할 수 없어요" in tg.sent[-1][1]


class FakeUser:
    def __init__(self):
        self.updated = []

    def update_comment(self, cid, text):
        self.updated.append((cid, text))


def test_bot_posted_comment_gets_fix_button_that_updates_it(tmp_path):
    conn, eid = _event_with_rules(tmp_path, entered=True)
    tg, user = FakeTG(), FakeUser()
    approval.handle_update(conn, tg, user, _reply("검수 보겸 한 줄", 777), gap_state={}, gap_seconds=0)
    assert tg.sent[-1][2] == [("✏️ 수정 적용", f"fix:{eid}")]
    cb = {"update_id": 2, "callback_query": {"id": "c", "data": f"fix:{eid}",
                                              "message": {"message_id": 9, "chat": {"id": 42}}}}
    approval.handle_update(conn, tg, user, cb, gap_state={}, gap_seconds=0)
    assert user.updated and user.updated[0][0] == "cmt9" and "아이폰듀오" in user.updated[0][1]
    assert tg.sent[-1][1].startswith("✅")


def test_do_post_subscribes_all_listed_channels(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    db.add_event(conn, source="youtube", source_url="https://y/v", title="t", host="보겸S", matched=[], raw_text="")
    db.update_event(conn, "https://y/v", status="awaiting_approval", entry_methods="subscribe,comment",
                    video_id="v1", channel_id="UCS",
                    requirements=json.dumps({"subscribe_channels": ["UC1", "UCS"]}))
    eid = db.event_id_by_url(conn, "https://y/v")
    db.set_draft(conn, eid, "댓글", 1)

    class U:
        def __init__(self):
            self.subs = []

        def subscribe(self, cid):
            self.subs.append(cid)
            return True

        def comment(self, v, t):
            return "c1"

    u = U()
    assert approval.do_post(conn, u, eid).startswith("✅")
    assert sorted(u.subs) == ["UC1", "UCS"]
