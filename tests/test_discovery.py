import httpx
import respx

from giveaway import cli, db, discover
from giveaway.collectors.youtube import API, YouTubeClient
from giveaway.extract import Extracted
from giveaway.rank import score
from datetime import datetime, timezone

CFG = {"enabled": True, "queries": ["구독자 이벤트 증정", "리뷰 후 증정 이벤트"], "max_queries_per_run": 8,
       "category_id": "28", "min_subscribers": 100, "max_subscribers": 0, "lookback_days": 7}


def _mock(router, *, subs=None, comments=3):
    """검색 → 영상 3개(채널 A·B·C), 채널 구독자 수."""
    router.get(f"{API}/search").respond(json={"items": [
        {"id": {"videoId": "vA"}}, {"id": {"videoId": "vB"}}, {"id": {"videoId": "vC"}}]})
    items = [{"id": v, "snippet": {"title": f"이어폰 리뷰 {v} 증정 이벤트", "description": "댓글 이벤트 https://forms.gle/x",
                                   "publishedAt": "2999-01-01T00:00:00Z", "channelId": ch, "channelTitle": name},
              "statistics": {"commentCount": str(comments), "viewCount": "1000"}}
             for v, ch, name in (("vA", "UCa", "작은채널"), ("vB", "UCb", "중간채널"), ("vC", "UCc", "스팸채널"))]
    router.get(f"{API}/videos").respond(json={"items": items})
    subs = subs or {"UCa": 1200, "UCb": 50000, "UCc": 20}
    router.get(f"{API}/channels").respond(json={"items": [
        {"id": k, "statistics": {"subscriberCount": str(v)}} for k, v in subs.items()]})


@respx.mock(assert_all_called=False)
def test_run_discovery_filters_by_subscribers_and_sorts_small_first(tmp_path, respx_mock):
    _mock(respx_mock)
    conn = db.connect(tmp_path / "t.db")
    found = discover.run_discovery(conn, YouTubeClient("k", httpx.Client()), CFG,
                                   published_after="2026-10-20T00:00:00Z", exclude_channel_ids=set())
    assert [v.channel_id for v in found] == ["UCa", "UCb"]  # 구독자 20명짜리 스팸 제외, 작은 채널 먼저
    assert found[0].subscribers == 1200 and found[0].comment_count == 3


@respx.mock(assert_all_called=False)
def test_discovery_skips_configured_channels_and_seen_videos(tmp_path, respx_mock):
    _mock(respx_mock)
    conn = db.connect(tmp_path / "t.db")
    db.add_event(conn, source="youtube", source_url="https://www.youtube.com/watch?v=vA", title="t", host="h",
                 matched=[], raw_text="")
    found = discover.run_discovery(conn, YouTubeClient("k", httpx.Client()), CFG,
                                   published_after="2026-10-20T00:00:00Z", exclude_channel_ids={"UCb"})
    assert found == []  # vA는 이미 봤고, vB는 설정한 채널, vC는 구독자 미달


@respx.mock(assert_all_called=False)
def test_max_subscribers_excludes_big_channels(tmp_path, respx_mock):
    _mock(respx_mock)
    conn = db.connect(tmp_path / "t.db")
    found = discover.run_discovery(conn, YouTubeClient("k", httpx.Client()), {**CFG, "max_subscribers": 10000},
                                   published_after="x", exclude_channel_ids=set())
    assert [v.channel_id for v in found] == ["UCa"]


class AiExtractor:
    def extract(self, text, **kw):
        return Extracted(is_giveaway=True, form_url="https://forms.gle/x", product="무선 이어폰",
                         entry_methods=["comment"], category="it")


@respx.mock(assert_all_called=False)
def test_collect_reports_discovered_channel_with_reach_and_starts_watching(tmp_path, respx_mock):
    _mock(respx_mock)
    respx_mock.get(f"{API}/playlistItems").respond(json={"items": []})
    respx_mock.get(f"{API}/commentThreads").respond(json={"items": []})
    conn = db.connect(tmp_path / "t.db")
    sent = []
    stats = cli.collect(conn, YouTubeClient("k", httpx.Client()), [], {"include": ["이벤트", "증정"], "exclude": []},
                        sent.append, AiExtractor(), None, discovery=CFG)
    assert stats["discovered_candidates"] == 2 and stats["new"] == 2
    msg = next(m for m in sent if m.startswith("<유튜브>"))
    assert "경쟁: 구독자 1,200 · 댓글 3개 · 🔭 새로 발견한 채널" in msg
    assert "구독자 5.0만" in msg
    assert dict(db.meta_items(conn, "watch:")) == {"watch:UCa": "작은채널", "watch:UCb": "중간채널"}


@respx.mock(assert_all_called=False)
def test_watched_channels_are_scanned_on_next_run(tmp_path, respx_mock):
    respx_mock.get(f"{API}/search").respond(json={"items": []})
    uploads = respx_mock.get(f"{API}/playlistItems").respond(json={"items": [
        {"contentDetails": {"videoId": "vW", "videoPublishedAt": "2999-01-01T00:00:00Z"}}]})
    respx_mock.get(f"{API}/videos").respond(json={"items": [{
        "id": "vW", "snippet": {"title": "증정 이벤트 진행", "description": "https://forms.gle/y",
                                "publishedAt": "2999-01-01T00:00:00Z", "channelId": "UCa", "channelTitle": "작은채널"},
        "statistics": {"commentCount": "12"}}]})
    respx_mock.get(f"{API}/commentThreads").respond(json={"items": []})
    conn = db.connect(tmp_path / "t.db")
    db.set_meta(conn, "watch:UCa", "작은채널")
    sent = []
    cli.collect(conn, YouTubeClient("k", httpx.Client()), [], {"include": ["이벤트"], "exclude": []},
                sent.append, AiExtractor(), None, discovery={**CFG, "queries": []})
    assert uploads.calls.last.request.url.params["playlistId"] == "UUa"  # UC → UU
    assert any("작은채널" in m and "vW" in m for m in sent)


@respx.mock(assert_all_called=False)
def test_non_it_videos_are_filtered_before_ai(tmp_path, respx_mock):
    respx_mock.get(f"{API}/search").respond(json={"items": [{"id": {"videoId": "vX"}}, {"id": {"videoId": "vY"}}]})
    respx_mock.get(f"{API}/videos").respond(json={"items": [
        {"id": "vX", "snippet": {"title": "화장품 나눔 이벤트", "description": "구독자 이벤트", "publishedAt": "2999-01-01T00:00:00Z",
                                 "channelId": "UCx", "channelTitle": "뷰티"}, "statistics": {}},
        {"id": "vY", "snippet": {"title": "키보드 리뷰", "description": "구독자 이벤트 증정", "publishedAt": "2999-01-01T00:00:00Z",
                                 "channelId": "UCy", "channelTitle": "IT리뷰"}, "statistics": {}}]})
    respx_mock.get(f"{API}/channels").respond(json={"items": [
        {"id": "UCx", "statistics": {"subscriberCount": "5000"}}, {"id": "UCy", "statistics": {"subscriberCount": "5000"}}]})
    conn = db.connect(tmp_path / "t.db")
    found = discover.run_discovery(conn, YouTubeClient("k", httpx.Client()), CFG, published_after="x",
                                   exclude_channel_ids=set())
    assert [v.video_id for v in found] == ["vY"]


@respx.mock(assert_all_called=False)
def test_discovered_event_outside_allowed_category_is_dropped_after_ai(tmp_path, respx_mock):
    _mock(respx_mock)
    respx_mock.get(f"{API}/commentThreads").respond(json={"items": []})
    conn = db.connect(tmp_path / "t.db")

    class Beauty(AiExtractor):
        def extract(self, text, **kw):
            return Extracted(is_giveaway=True, form_url="https://forms.gle/x", category="other")

    sent = []
    stats = cli.collect(conn, YouTubeClient("k", httpx.Client()), [], {"include": ["이벤트", "증정"], "exclude": []},
                        sent.append, Beauty(), None, discovery=CFG)
    assert stats["new"] == 0 and stats["skipped"] == 2 and not any(m.startswith("<유튜브>") for m in sent)


def test_discovery_disabled_does_nothing(tmp_path):
    conn = db.connect(tmp_path / "t.db")

    class Boom:
        def __getattr__(self, name):
            raise AssertionError("검색하면 안 됨")

    stats = cli.collect(conn, Boom(), [], {"include": []}, lambda m: None, AiExtractor(), None,
                        discovery={"enabled": False, "queries": ["x"]})
    assert stats["videos"] == 0


def test_fewer_comments_means_better_odds_in_score():
    now = datetime(2026, 11, 1, tzinfo=timezone.utc)
    kw = dict(tags=["it"], prize_value_est=100000, entry_methods=["comment"], deadline="", now=now)
    assert score(**kw, comment_count=20) > score(**kw, comment_count=5000) > score(**kw, comment_count=50000)
    assert score(**kw) == score(**kw, comment_count=5000)  # 정보 없으면 중립
