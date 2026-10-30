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
        {"id": "vY", "snippet": {"title": "이어폰 리뷰", "description": "구독자 이벤트 증정", "publishedAt": "2999-01-01T00:00:00Z",
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


# ---- 제외 분야(키보드 등) ----
from giveaway.detect import excluded_topic  # noqa: E402

TOPICS = {"include": ["이벤트", "증정"], "exclude": [], "exclude_topics": ["키보드", "keyboard", "텐키리스"]}


def test_excluded_topic_matches_case_insensitively():
    assert excluded_topic("독거미 키보드 리뷰", TOPICS) == "키보드"
    assert excluded_topic("Mechanical KEYBOARD giveaway", TOPICS) == "keyboard"
    assert excluded_topic("이어폰 증정 이벤트", TOPICS) == ""
    assert excluded_topic("키보드", None) == ""


@respx.mock(assert_all_called=False)
def test_discovery_drops_keyboard_videos_before_ai(tmp_path, respx_mock):
    respx_mock.get(f"{API}/search").respond(json={"items": [{"id": {"videoId": "vK"}}, {"id": {"videoId": "vE"}}]})
    respx_mock.get(f"{API}/videos").respond(json={"items": [
        {"id": "vK", "snippet": {"title": "키보드 리뷰 구독자 이벤트", "description": "", "publishedAt": "2999-01-01T00:00:00Z",
                                 "channelId": "UCk", "channelTitle": "키보드채널"}, "statistics": {}},
        {"id": "vE", "snippet": {"title": "이어폰 리뷰 구독자 이벤트", "description": "", "publishedAt": "2999-01-01T00:00:00Z",
                                 "channelId": "UCe", "channelTitle": "이어폰채널"}, "statistics": {}}]})
    respx_mock.get(f"{API}/channels").respond(json={"items": [
        {"id": "UCk", "statistics": {"subscriberCount": "5000"}}, {"id": "UCe", "statistics": {"subscriberCount": "5000"}}]})
    conn = db.connect(tmp_path / "t.db")
    found = discover.run_discovery(conn, YouTubeClient("k", httpx.Client()), CFG, published_after="x",
                                   exclude_channel_ids=set(), filters=TOPICS)
    assert [v.video_id for v in found] == ["vE"]


@respx.mock(assert_all_called=False)
def test_collect_never_calls_ai_for_excluded_topic_and_drops_ai_flagged_products(tmp_path, respx_mock):
    respx_mock.get(f"{API}/channels").respond(json={"items": [{
        "id": "UC1", "contentDetails": {"relatedPlaylists": {"uploads": "UU1"}}}]})
    respx_mock.get(f"{API}/playlistItems").respond(json={"items": [
        {"contentDetails": {"videoId": v, "videoPublishedAt": "2999-01-01T00:00:00Z"}} for v in ("vK", "vP")]})
    respx_mock.get(f"{API}/videos").respond(json={"items": [
        {"id": "vK", "snippet": {"title": "독거미 키보드 증정 이벤트", "description": "", "publishedAt": "2999-01-01T00:00:00Z",
                                 "channelId": "UC1", "channelTitle": "채널"}, "statistics": {}},
        {"id": "vP", "snippet": {"title": "신제품 리뷰 증정 이벤트", "description": "https://forms.gle/x",
                                 "publishedAt": "2999-01-01T00:00:00Z", "channelId": "UC1", "channelTitle": "채널"}, "statistics": {}}]})
    respx_mock.get(f"{API}/commentThreads").respond(json={"items": []})
    conn = db.connect(tmp_path / "t.db")

    class Calls(AiExtractor):
        def __init__(self):
            self.n = 0

        def extract(self, text, **kw):
            self.n += 1
            return Extracted(is_giveaway=True, form_url="https://forms.gle/x", product="AULA F108 PRO 키보드", category="it")

    ai, sent = Calls(), []
    stats = cli.collect(conn, YouTubeClient("k", httpx.Client()), [{"name": "채널", "handle": "@x"}], TOPICS,
                        sent.append, ai, None)
    assert ai.n == 1  # 제목에 '키보드'가 있는 영상은 AI를 부르지 않는다
    assert stats["excluded_topic"] == 1 and stats["new"] == 0  # 제품이 키보드로 확인된 영상도 제외
    assert not any(m.startswith("<유튜브>") for m in sent)


def test_sites_skip_excluded_topics(tmp_path):
    from giveaway.collectors.sites import SiteItem
    conn = db.connect(tmp_path / "t.db")
    sent = []
    items = [SiteItem("jupjup", "https://j/1", "기계식 키보드 추첨", prize="키보드"),
             SiteItem("jupjup", "https://j/2", "무선 이어폰 추첨", prize="이어폰")]
    stats = cli.collect_sites(conn, items, TOPICS, sent.append, None)
    assert stats["new"] == 1 and "이어폰" in sent[0] and "키보드" not in sent[0]


def test_existing_open_events_on_excluded_topics_are_closed_and_cannot_be_posted(tmp_path):
    from giveaway import approval
    conn = db.connect(tmp_path / "t.db")
    for url, title in (("https://y/k", "독거미 키보드 이벤트"), ("https://y/e", "이어폰 이벤트")):
        db.add_event(conn, source="youtube", source_url=url, title=title, host="h", matched=[], raw_text="")
        db.update_event(conn, url, status="awaiting_approval", video_id="v", entry_methods="comment")
    kid = db.event_id_by_url(conn, "https://y/k")
    db.set_draft(conn, kid, "댓글", 1)
    assert cli.skip_excluded_existing(conn, TOPICS) == 1
    statuses = {r["source_url"]: r["status"] for r in conn.execute("SELECT source_url, status FROM events")}
    assert statuses == {"https://y/k": "skipped", "https://y/e": "awaiting_approval"}
    assert "처리할 수 없는" in approval.do_post(conn, object(), kid)  # 남은 [게시] 버튼도 막힌다


@respx.mock(assert_all_called=False)
def test_quota_error_keeps_partial_results_and_notifies_once(tmp_path, respx_mock):
    calls = {"n": 0}

    def search(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(200, json={"items": [{"id": {"videoId": "vA"}}]})
        return httpx.Response(429, json={"error": {"message": "quota"}})

    respx_mock.get(f"{API}/search").mock(side_effect=search)
    respx_mock.get(f"{API}/videos").respond(json={"items": [{
        "id": "vA", "snippet": {"title": "이어폰 리뷰 증정 이벤트", "description": "https://forms.gle/x",
                                "publishedAt": "2999-01-01T00:00:00Z", "channelId": "UCa", "channelTitle": "작은채널"},
        "statistics": {"commentCount": "3"}}]})
    respx_mock.get(f"{API}/channels").respond(json={"items": [{"id": "UCa", "statistics": {"subscriberCount": "1200"}}]})
    respx_mock.get(f"{API}/commentThreads").respond(json={"items": []})
    conn = db.connect(tmp_path / "t.db")
    sent = []
    yt = YouTubeClient("k", httpx.Client())
    stats = cli.collect(conn, yt, [], {"include": ["이벤트", "증정"], "exclude": []}, sent.append,
                        AiExtractor(), None, discovery=CFG)
    assert stats["new"] == 1 and "429" in stats["discovery_error"]  # 첫 쿼리 결과는 살린다
    warnings = [m for m in sent if "발견 검색" in m]
    assert len(warnings) == 1
    calls["n"] = 0
    cli.collect(conn, yt, [], {"include": ["이벤트", "증정"], "exclude": []}, sent.append, AiExtractor(), None,
                discovery=CFG)
    assert len([m for m in sent if "발견 검색" in m]) == 1  # 같은 원인은 다시 알리지 않는다
