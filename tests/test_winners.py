from datetime import datetime, timedelta, timezone

from giveaway import db, winners
from giveaway.cli import remind_and_expire
from giveaway.models import Video

NOW = datetime(2026, 11, 10, tzinfo=timezone.utc)


class FakeUser:
    def __init__(self, replies=()):
        self._replies = list(replies)

    def my_channel(self):
        return "UCme", "@내핸들"

    def replies(self, parent_id):
        return self._replies


class FakeYT:
    def __init__(self, videos=(), pinned=""):
        self._videos, self._pinned = list(videos), pinned

    def recent_video_ids(self, uploads, after):
        return [v.video_id for v in self._videos]

    def videos(self, ids, name):
        return self._videos

    def pinned_comment(self, vid, cid):
        return self._pinned


def _entered(tmp_path, entered_at="2026-11-01 00:00:00", deadline="2026-11-05"):
    conn = db.connect(tmp_path / "t.db")
    db.add_event(conn, source="youtube", source_url="https://y/v1", title="경품 영상", host="잇섭",
                 matched=[], raw_text="")
    db.update_event(conn, "https://y/v1", status="entered", channel_id="UC1", video_id="v1",
                    deadline=deadline)
    eid = db.event_id_by_url(conn, "https://y/v1")
    db.add_entry(conn, eid, "comment", "thread1")
    conn.execute("UPDATE entries SET entered_at = ? WHERE event_id = ?", (entered_at, eid))
    conn.commit()
    db.set_meta(conn, "channel:잇섭", "UC1|UU1")
    return conn


def test_owner_reply_notifies_once(tmp_path):
    conn = _entered(tmp_path)
    user = FakeUser([{"id": "r1", "author_channel_id": "UC1", "text": "당첨 축하드려요!"},
                     {"id": "r2", "author_channel_id": "UCother", "text": "부럽다"}])
    sent = []
    assert winners.check(conn, FakeYT(), user, sent.append, NOW)["replies"] == 1
    assert winners.check(conn, FakeYT(), user, sent.append, NOW)["replies"] == 0
    assert len(sent) == 1 and "당첨 축하" in sent[0]


def test_handle_mention_in_later_video_notifies_once(tmp_path):
    conn = _entered(tmp_path)
    vid = Video("v2", "잇섭", "이벤트 당첨자 발표", "당첨자: @내핸들 님, @other", "2026-11-08T00:00:00Z")
    sent = []
    yt = FakeYT([vid])
    assert winners.check(conn, yt, FakeUser(), sent.append, NOW)["mentions"] == 1
    assert winners.check(conn, yt, FakeUser(), sent.append, NOW)["mentions"] == 0
    assert "v2" in sent[0]


def test_mention_in_pinned_comment_counts(tmp_path):
    conn = _entered(tmp_path)
    vid = Video("v2", "잇섭", "다음 영상", "평범", "2026-11-08T00:00:00Z")
    sent = []
    r = winners.check(conn, FakeYT([vid], pinned="지난 이벤트 당첨자 @내핸들"), FakeUser(), sent.append, NOW)
    assert r["mentions"] == 1


def test_handle_without_announcement_words_is_ignored(tmp_path):
    conn = _entered(tmp_path)
    vid = Video("v2", "잇섭", "리뷰", "협업: @내핸들", "2026-11-08T00:00:00Z")
    assert winners.check(conn, FakeYT([vid]), FakeUser(), lambda m: None, NOW)["mentions"] == 0


def test_closes_after_watch_window(tmp_path):
    conn = _entered(tmp_path, entered_at="2026-09-01 00:00:00")
    assert winners.check(conn, FakeYT(), FakeUser(), lambda m: None, NOW)["closed"] == 1
    assert conn.execute("SELECT status FROM events").fetchone()["status"] == "closed"


def test_entered_events_are_not_expired_by_deadline(tmp_path):
    conn = _entered(tmp_path)
    remind_and_expire(conn, lambda m: None, NOW + timedelta(days=30))
    assert conn.execute("SELECT status FROM events").fetchone()["status"] == "entered"


def test_youtube_user_my_channel_and_replies():
    import respx
    from giveaway.enter.youtube import API, TOKEN_URL, YouTubeUser
    with respx.mock:
        respx.post(TOKEN_URL).respond(json={"access_token": "AT"})
        respx.get(f"{API}/channels").respond(json={"items": [{"id": "UCme", "snippet": {"customUrl": "@내핸들"}}]})
        respx.get(f"{API}/comments").respond(json={"items": [
            {"id": "r1", "snippet": {"authorChannelId": {"value": "UC1"}, "textDisplay": "축하"}}]})
        u = YouTubeUser("i", "s", "r")
        assert u.my_channel() == ("UCme", "@내핸들")
        assert u.replies("t1") == [{"id": "r1", "author_channel_id": "UC1", "text": "축하"}]
