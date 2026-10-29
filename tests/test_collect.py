import httpx
import respx

from giveaway import db
from giveaway.cli import collect
from giveaway.collectors.youtube import API, YouTubeClient

FILTERS = {"include": ["이벤트", "증정"], "exclude": []}
CHANNELS = [{"name": "잇섭", "handle": "@ITSub"}]


def _mock(router, *, description, pinned=None):
    router.get(f"{API}/channels").respond(json={"items": [{
        "id": "UC1", "contentDetails": {"relatedPlaylists": {"uploads": "UU1"}}}]})
    router.get(f"{API}/playlistItems").respond(json={"items": [
        {"contentDetails": {"videoId": "v1", "videoPublishedAt": "2999-01-01T00:00:00Z"}}]})
    router.get(f"{API}/videos").respond(json={"items": [{
        "id": "v1", "snippet": {"title": "리뷰", "description": description,
                                "publishedAt": "2999-01-01T00:00:00Z"}}]})
    comments = [] if pinned is None else [{"snippet": {"topLevelComment": {"snippet": {
        "authorChannelId": {"value": "UC1"}, "textDisplay": pinned}}}}]
    router.get(f"{API}/commentThreads").respond(json={"items": comments})


@respx.mock(assert_all_called=False)
def test_event_in_description_notifies_once(tmp_path, respx_mock):
    _mock(respx_mock, description="댓글 이벤트! 추첨 증정 https://forms.gle/abc")
    conn = db.connect(tmp_path / "t.db")
    sent = []
    yt = YouTubeClient("k", httpx.Client())
    s1 = collect(conn, yt, CHANNELS, FILTERS, sent.append)
    assert s1["new"] == 1
    assert any("잇섭" in m and "v1" in m for m in sent)
    sent.clear()
    s2 = collect(conn, yt, CHANNELS, FILTERS, sent.append)
    assert s2["new"] == 0 and sent == []


@respx.mock(assert_all_called=False)
def test_event_only_in_pinned_comment(tmp_path, respx_mock):
    _mock(respx_mock, description="평범한 설명", pinned="구독자 증정 이벤트 진행중 https://forms.gle/xyz")
    conn = db.connect(tmp_path / "t.db")
    s = collect(conn, YouTubeClient("k", httpx.Client()), CHANNELS, FILTERS, lambda m: None)
    assert s["new"] == 1


@respx.mock(assert_all_called=False)
def test_non_event_video_ignored(tmp_path, respx_mock):
    _mock(respx_mock, description="평범한 설명", pinned=None)
    conn = db.connect(tmp_path / "t.db")
    s = collect(conn, YouTubeClient("k", httpx.Client()), CHANNELS, FILTERS, lambda m: None)
    assert s["new"] == 0
