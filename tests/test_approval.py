from datetime import datetime, timezone

import httpx
import respx

from giveaway import approval, db
from giveaway.enter.youtube import API, TOKEN_URL, YouTubeUser
from giveaway.extract import API_URL, Extracted, Extractor


class FakeTG:
    chat_id = "42"

    def __init__(self):
        self.sent, self.cleared, self.answered, self._id = [], [], [], 100

    def send(self, text, buttons=None, reply_to=None):
        self._id += 1
        self.sent.append((self._id, text, buttons))
        return self._id

    def clear_buttons(self, message_id):
        self.cleared.append(message_id)

    def answer_callback(self, cid, text=""):
        self.answered.append((cid, text))

    def get_updates(self, offset):
        return self.updates


class FakeYT:
    def __init__(self, fail=None):
        self.calls, self.fail = [], fail

    def subscribe(self, cid):
        self.calls.append(("subscribe", cid))
        return True

    def like(self, vid):
        self.calls.append(("like", vid))

    def comment(self, vid, text):
        if self.fail:
            raise self.fail
        self.calls.append(("comment", vid, text))
        return "cmt1"


class FakeExtractor:
    def draft_comment(self, title, desc, ex):
        return "정말 기대되는 제품이에요"


def _setup(tmp_path, methods="subscribe,like,comment", deadline="2999-01-01"):
    conn = db.connect(tmp_path / "t.db")
    db.add_event(conn, source="youtube", source_url="https://y/v1", title="리뷰", host="잇섭",
                 matched=["이벤트"], raw_text="")
    db.update_event(conn, "https://y/v1", status="notified", entry_methods=methods,
                    deadline=deadline, video_id="v1", channel_id="UC1")
    return conn, db.event_id_by_url(conn, "https://y/v1")


def _propose(conn, tg, eid):
    ex = Extracted(is_giveaway=True, entry_methods=["comment"])
    assert approval.propose(conn, tg, FakeExtractor(), eid, "리뷰", "설명", ex)


def _cb(data, msg_id, chat=42):
    return {"update_id": 1, "callback_query": {"id": "c1", "data": data,
            "message": {"message_id": msg_id, "chat": {"id": chat}}}}


def test_proposable_rules():
    assert approval.proposable(Extracted(entry_methods=["comment"]))
    assert approval.proposable(Extracted(entry_methods=["comment", "google_form"]))  # 폼이 함께 있어도 초안
    assert not approval.proposable(Extracted(entry_methods=["google_form"]))


def test_propose_sends_draft_with_buttons_and_sets_status(tmp_path):
    conn, eid = _setup(tmp_path)
    tg = FakeTG()
    _propose(conn, tg, eid)
    msg_id, text, buttons = tg.sent[0]
    assert "정말 기대되는 제품이에요" in text and buttons[0][1] == f"post:{eid}"
    assert db.get_event(conn, eid)["status"] == "awaiting_approval"


def test_post_button_subscribes_likes_comments_and_records(tmp_path):
    conn, eid = _setup(tmp_path)
    tg, yt = FakeTG(), FakeYT()
    _propose(conn, tg, eid)
    approval.handle_update(conn, tg, yt, _cb(f"post:{eid}", 101), gap_state={}, gap_seconds=0)
    assert [c[0] for c in yt.calls] == ["subscribe", "like", "comment"]
    assert db.get_event(conn, eid)["status"] == "entered" and db.has_entry(conn, eid, "comment")
    assert 101 in tg.cleared


def test_double_press_does_not_comment_twice(tmp_path):
    conn, eid = _setup(tmp_path)
    tg, yt = FakeTG(), FakeYT()
    _propose(conn, tg, eid)
    for _ in range(2):
        approval.handle_update(conn, tg, yt, _cb(f"post:{eid}", 101), gap_state={}, gap_seconds=0)
    assert [c[0] for c in yt.calls].count("comment") == 1


def test_wrong_chat_is_ignored(tmp_path):
    conn, eid = _setup(tmp_path)
    tg, yt = FakeTG(), FakeYT()
    _propose(conn, tg, eid)
    approval.handle_update(conn, tg, yt, _cb(f"post:{eid}", 101, chat=999), gap_state={}, gap_seconds=0)
    assert yt.calls == [] and db.get_event(conn, eid)["status"] == "awaiting_approval"


def test_skip_button(tmp_path):
    conn, eid = _setup(tmp_path)
    tg, yt = FakeTG(), FakeYT()
    _propose(conn, tg, eid)
    approval.handle_update(conn, tg, yt, _cb(f"skip:{eid}", 101), gap_state={}, gap_seconds=0)
    assert db.get_event(conn, eid)["status"] == "skipped" and yt.calls == []


def test_reply_edits_draft_and_posts_edited_text(tmp_path):
    conn, eid = _setup(tmp_path, methods="comment")
    tg, yt = FakeTG(), FakeYT()
    _propose(conn, tg, eid)
    reply = {"update_id": 2, "message": {"chat": {"id": 42}, "text": "내가 고친 댓글",
                                         "reply_to_message": {"message_id": 101}}}
    approval.handle_update(conn, tg, yt, reply, gap_state={}, gap_seconds=0)
    new_id = tg.sent[-1][0]
    approval.handle_update(conn, tg, yt, _cb(f"post:{eid}", new_id), gap_state={}, gap_seconds=0)
    assert ("comment", "v1", "내가 고친 댓글") in yt.calls


def test_expired_deadline_blocks_post(tmp_path):
    conn, eid = _setup(tmp_path, deadline="2020-01-01")
    tg, yt = FakeTG(), FakeYT()
    _propose(conn, tg, eid)
    msg = approval.do_post(conn, yt, eid, now=datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert "마감" in msg and yt.calls == [] and db.get_event(conn, eid)["status"] == "expired"


def test_failed_comment_keeps_retry_possible(tmp_path):
    conn, eid = _setup(tmp_path, methods="comment")
    tg = FakeTG()
    _propose(conn, tg, eid)
    err = httpx.HTTPStatusError("x", request=httpx.Request("POST", "http://x"),
                                response=httpx.Response(403, text="forbidden"))
    msg = approval.do_post(conn, FakeYT(fail=err), eid)
    assert msg.startswith("❌") and db.get_event(conn, eid)["status"] == "awaiting_approval"
    assert approval.do_post(conn, FakeYT(), eid).startswith("✅")


def test_poll_advances_offset(tmp_path):
    conn, eid = _setup(tmp_path)
    tg, yt = FakeTG(), FakeYT()
    tg.updates = [{"update_id": 7, "message": {"chat": {"id": 1}, "text": "hi"}}]
    assert approval.poll(conn, tg, yt) == 1
    assert db.get_meta(conn, "tg_offset") == "8"


@respx.mock
def test_youtube_user_calls():
    respx.post(TOKEN_URL).respond(json={"access_token": "AT"})
    c = respx.post(f"{API}/commentThreads").respond(json={"id": "cmt9"})
    dup = respx.post(f"{API}/subscriptions").respond(400, text="subscriptionDuplicate")
    u = YouTubeUser("id", "sec", "rt")
    assert u.comment("v1", "hi") == "cmt9"
    assert c.calls.last.request.headers["authorization"] == "Bearer AT"
    assert u.subscribe("UC1") is False and dup.called


@respx.mock
def test_draft_comment_appends_missing_keywords():
    respx.post(API_URL).respond(json={"content": [{"type": "text", "text": "좋은 영상이에요"}]})
    ex = Extracted(required_keywords=["#잇섭이벤트"])
    text = Extractor("k").draft_comment("t", "d", ex)
    assert text.endswith("#잇섭이벤트")


@respx.mock(assert_all_called=False)
def test_collect_proposes_for_comment_events_only(tmp_path, respx_mock):
    from giveaway.cli import collect
    from giveaway.collectors.youtube import YouTubeClient
    from test_collect import CHANNELS, FILTERS, _mock
    from test_extract_rank import FakeExtractor as FE

    class Both(FE):
        draft_comment = FakeExtractor.draft_comment

    _mock(respx_mock, description="증정 이벤트")
    conn = db.connect(tmp_path / "t.db")
    tg = FakeTG()
    ex = Extracted(is_giveaway=True, entry_methods=["comment"], deadline="2999-01-01",
                   form_url="https://forms.gle/a")
    collect(conn, YouTubeClient("k", httpx.Client()), CHANNELS, FILTERS, lambda m: None,
            Both(ex), tg)
    row = conn.execute("SELECT * FROM events").fetchone()
    assert row["status"] == "awaiting_approval" and row["video_id"] == "v1" and row["channel_id"] == "UC1"
    assert tg.sent and tg.sent[0][2]


def test_draft_notes_warn_about_inferred_format_and_manual_steps(tmp_path):
    conn, eid = _setup(tmp_path)
    tg = FakeTG()
    ex = Extracted(is_giveaway=True, entry_methods=["subscribe", "comment", "google_form"],
                   entry_steps=["구독", "댓글", "구글폼 작성"], form_url="https://forms.gle/a",
                   format_confidence="low", entry_format="보겸으로 3행시")
    assert approval.propose(conn, tg, FakeExtractor(), eid, "리뷰", "설명", ex)
    text, buttons = tg.sent[0][1], tg.sent[0][2]
    assert "추정" in text and "https://forms.gle/a" in text and "구독·좋아요도 함께" in text
    assert buttons  # 게시 버튼은 있음


def test_macro_banned_draft_has_no_buttons_and_no_pending_state(tmp_path):
    conn, eid = _setup(tmp_path)
    tg = FakeTG()
    ex = Extracted(is_giveaway=True, entry_methods=["comment"], macro_banned=True)
    assert approval.propose(conn, tg, FakeExtractor(), eid, "리뷰", "설명", ex)
    assert tg.sent[0][2] is None and "직접 작성" in tg.sent[0][1]
    assert db.get_event(conn, eid)["status"] == "notified" and db.get_draft(conn, eid) is None
