from datetime import timedelta

import httpx
import pytest
import respx

from giveaway import cli, db, digest
from giveaway.collectors.youtube import API, YouTubeClient
from giveaway.extract import Extracted

from test_collect import CHANNELS, FILTERS


def test_classify_priorities():
    assert digest.classify("RTX 5060 그래픽카드 증정") == "it"
    assert digest.classify("신생아 기저귀 세트") == "baby"
    assert digest.classify("스타벅스 기프티콘 100명") == "gift_travel"
    assert digest.classify("행운의 추첨") == "other"
    assert digest.classify("출산 준비 가습기 체험단") == "it"  # IT가 우선


def test_format_youtube_matches_requested_layout():
    text = digest.format_youtube([
        digest.YtEntry("잇섭", "신형 SSD 리뷰", "삼성 990 PRO 2TB", "2026-11-05", "https://y/v1",
                       apply_link="https://forms.gle/a")])
    assert text.splitlines()[0] == "<유튜브> 이벤트 확정 (1건)"
    assert "영상제목: [잇섭] 신형 SSD 리뷰" in text
    assert "제품: 삼성 990 PRO 2TB" in text
    assert "이벤트 기한: 2026-11-05" in text
    assert "링크: https://y/v1" in text and "응모: https://forms.gle/a" in text


def test_format_youtube_unknown_fields_and_order_by_score():
    text = digest.format_youtube([
        digest.YtEntry("A", "낮은점수", "", "", "https://y/1", score=10),
        digest.YtEntry("B", "높은점수", "키보드", "2026-11-01", "https://y/2", score=90)])
    assert text.index("높은점수") < text.index("낮은점수")
    assert "제품: 미상" in text and "이벤트 기한: 미상" in text


def test_format_sites_groups_by_tier_and_skips_empty_tiers():
    text = digest.format_sites([
        digest.SiteEntry("jupjup", "스타벅스 쿠폰", "쿠폰", "2026-11-03", "https://u/1", "gift_travel", 50),
        digest.SiteEntry("danawa", "그래픽카드 룰렛", "RTX", "", "https://u/2", "it", 40, manual=True),
        digest.SiteEntry("eventskr", "SSD 이벤트", "SSD", "", "https://u/3", "it", 80)])
    assert text.index("1순위") < text.index("3순위") and "2순위" not in text
    assert text.index("SSD 이벤트") < text.index("그래픽카드 룰렛")  # 같은 순위에서는 점수순
    assert "⚠️직접 응모" in text


def test_split_message_respects_limit_and_keeps_all_text():
    blocks = [f"블록{i} " + "가" * 500 for i in range(20)]
    chunks = digest.split_message("\n\n".join(blocks), limit=1500)
    assert all(len(c) <= 1500 for c in chunks) and len(chunks) > 1
    assert "".join(chunks).count("블록") == 20


def _two_videos(router, comments):
    router.get(f"{API}/channels").respond(json={"items": [{
        "id": "UC1", "contentDetails": {"relatedPlaylists": {"uploads": "UU1"}}}]})
    router.get(f"{API}/playlistItems").respond(json={"items": [
        {"contentDetails": {"videoId": v, "videoPublishedAt": "2999-01-01T00:00:00Z"}} for v in ("v1", "v2")]})
    router.get(f"{API}/videos").respond(json={"items": [
        {"id": v, "snippet": {"title": f"영상{v}", "description": "증정 이벤트",
                              "publishedAt": "2999-01-01T00:00:00Z"}} for v in ("v1", "v2")]})
    router.get(f"{API}/commentThreads").respond(json={"items": [
        {"snippet": {"topLevelComment": {"snippet": {"authorChannelId": {"value": f"U{i}"},
                                                      "textDisplay": c}}}} for i, c in enumerate(comments)]})


class Ex:
    def __init__(self, *results):
        self.results, self.calls = list(results), []

    def extract(self, text, **kw):
        self.calls.append(kw)
        return self.results.pop(0) if len(self.results) > 1 else self.results[0]


@respx.mock(assert_all_called=False)
def test_all_youtube_events_are_sent_as_one_message(tmp_path, respx_mock):
    _two_videos(respx_mock, [])
    conn = db.connect(tmp_path / "t.db")
    sent = []
    real = Extracted(is_giveaway=True, form_url="https://forms.gle/a", product="마우스")
    cli.collect(conn, YouTubeClient("k", httpx.Client()), CHANNELS, FILTERS, sent.append, Ex(real))
    event_msgs = [m for m in sent if m.startswith("<유튜브>")]
    assert len(event_msgs) == 1 and "(2건)" in event_msgs[0]
    assert event_msgs[0].count("영상제목:") == 2


@respx.mock(assert_all_called=False)
def test_similar_comments_count_as_evidence_and_are_passed_to_extractor(tmp_path, respx_mock):
    _two_videos(respx_mock, ["참여합니다 #이벤트", "참여합니다 #이벤트"])
    conn = db.connect(tmp_path / "t.db")
    sent = []
    ex = Ex(Extracted(is_giveaway=True, many_similar_entries=True))
    cli.collect(conn, YouTubeClient("k", httpx.Client()), CHANNELS, FILTERS, sent.append, ex)
    assert ex.calls[0]["comments"] == ["참여합니다 #이벤트", "참여합니다 #이벤트"]
    assert any(m.startswith("<유튜브>") for m in sent)


@respx.mock(assert_all_called=False)
def test_no_evidence_goes_pending_then_confirms_when_participation_appears(tmp_path, respx_mock):
    _two_videos(respx_mock, [])
    conn = db.connect(tmp_path / "t.db")
    sent = []
    yt = YouTubeClient("k", httpx.Client())
    unsure = Extracted(is_giveaway=True)  # 링크도 참여 댓글도 없음
    s = cli.collect(conn, yt, CHANNELS, FILTERS, sent.append, Ex(unsure))
    assert s["pending"] == 2 and not any(m.startswith("<유튜브>") for m in sent)
    # 이후 댓글이 달리면 확정
    respx_mock.get(f"{API}/commentThreads").respond(json={"items": []})
    now_real = Extracted(is_giveaway=True, many_similar_entries=True, product="키보드")
    s2 = cli.collect(conn, yt, CHANNELS, FILTERS, sent.append, Ex(now_real))
    assert s2["new"] == 2
    assert [m for m in sent if m.startswith("<유튜브>")][0].count("제품: 키보드") == 2
    assert {r["status"] for r in conn.execute("SELECT status FROM events")} == {"notified"}


@respx.mock(assert_all_called=False)
def test_stale_pending_is_dropped(tmp_path, respx_mock):
    _two_videos(respx_mock, [])
    conn = db.connect(tmp_path / "t.db")
    yt = YouTubeClient("k", httpx.Client())
    cli.collect(conn, yt, CHANNELS, FILTERS, lambda m: None, Ex(Extracted(is_giveaway=True)))
    old = (cli._now() - timedelta(hours=cli.PENDING_HOURS + 1)).strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("UPDATE events SET first_seen_at = ?", (old,))
    conn.commit()
    cli.collect(conn, yt, CHANNELS, FILTERS, lambda m: None, Ex(Extracted(is_giveaway=True)))
    assert {r["status"] for r in conn.execute("SELECT status FROM events")} == {"skipped"}


@respx.mock(assert_all_called=False)
def test_failed_bundle_restores_pending_and_deletes_new(tmp_path, respx_mock):
    _two_videos(respx_mock, [])
    conn = db.connect(tmp_path / "t.db")
    yt = YouTubeClient("k", httpx.Client())
    cli.collect(conn, yt, CHANNELS, FILTERS, lambda m: None, Ex(Extracted(is_giveaway=True)))
    conn.execute("UPDATE events SET status='pending'")  # 위 실행은 보류 2건

    def boom(_):
        raise RuntimeError("telegram down")

    real = Extracted(is_giveaway=True, form_url="https://forms.gle/a")
    with pytest.raises(RuntimeError):
        cli.collect(conn, yt, CHANNELS, FILTERS, boom, Ex(real))
    assert {r["status"] for r in conn.execute("SELECT status FROM events")} == {"pending"}


def test_no_ai_requires_external_link(tmp_path):
    assert cli._decide(None, "증정 이벤트 https://forms.gle/a") == "confirmed"
    assert cli._decide(None, "증정 이벤트 https://www.youtube.com/watch?v=1") == "skipped"
    assert cli._decide(None, "증정 이벤트") == "skipped"


def test_reset_events_keeps_entered_and_awaiting(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    for i, st in enumerate(["notified", "skipped", "entered", "awaiting_approval"]):
        db.add_event(conn, source="youtube", source_url=f"u{i}", title=f"t{i}", host="h",
                     matched=[], raw_text="")
        db.update_event(conn, f"u{i}", status=st)
    db.set_meta(conn, "last_collect_at", "2026-01-01T00:00:00Z")
    assert db.reset_events(conn) == 2
    assert db.get_meta(conn, "last_collect_at") is None
    assert {r["status"] for r in conn.execute("SELECT status FROM events")} == {"entered", "awaiting_approval"}


def test_scheduled_backup_run_is_skipped_when_recent(tmp_path, monkeypatch, capsys):
    import argparse
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "1")
    monkeypatch.setenv("YOUTUBE_API_KEY", "k")
    path = tmp_path / "t.db"
    conn = db.connect(path)
    db.set_meta(conn, "last_collect_at", cli._iso(cli._now() - timedelta(hours=3)))
    conn.close()
    cli.cmd_collect(argparse.Namespace(db=str(path), reset_events=False, skip_if_ran_within_hours=20))
    assert "건너뜀" in capsys.readouterr().out


def test_decide_skips_passed_deadline_and_signup_conditions():
    from datetime import datetime, timezone
    now = datetime(2026, 10, 30, tzinfo=timezone.utc)
    old = Extracted(is_giveaway=True, form_url="https://x", deadline="2026-10-20T23:59")
    assert cli._decide(old, "t", now=now) == "skipped"  # AI가 종료를 놓쳐도 마감일로 거름
    paid = Extracted(is_giveaway=True, form_url="https://x", requires_purchase_or_signup=True,
                     signup_condition="알뜰폰 개통")
    assert cli._decide(paid, "t", {"exclude_signup_required": True}, now) == "skipped"
    assert cli._decide(paid, "t", {"exclude_signup_required": False}, now) == "confirmed"
    ok = Extracted(is_giveaway=True, form_url="https://x", deadline="2026-11-08T23:59")
    assert cli._decide(ok, "t", None, now) == "confirmed"


def test_digest_shows_steps_format_and_condition():
    text = digest.format_youtube([digest.YtEntry(
        "보겸TV", "아이폰 선물", "아이폰18", "", "https://y/1",
        steps=["구독", "댓글", "구글폼"], entry_format="보겸으로 3행시", format_inferred=True,
        condition="알뜰폰 개통")])
    assert "응모 방법: 구독 → 댓글 → 구글폼" in text
    assert "응모양식: 보겸으로 3행시 (댓글 패턴으로 추정" in text and "⚠️ 조건: 알뜰폰 개통" in text


@respx.mock(assert_all_called=False)
def test_format_in_video_channel_is_analyzed_without_keywords(tmp_path, respx_mock):
    respx_mock.get(f"{API}/channels").respond(json={"items": [{
        "id": "UC1", "contentDetails": {"relatedPlaylists": {"uploads": "UU1"}}}]})
    respx_mock.get(f"{API}/playlistItems").respond(json={"items": [
        {"contentDetails": {"videoId": "v1", "videoPublishedAt": "2999-01-01T00:00:00Z"}}]})
    respx_mock.get(f"{API}/videos").respond(json={"items": [{
        "id": "v1", "snippet": {"title": "아이폰 대방출", "description": "보겸TV",
                                "publishedAt": "2999-01-01T00:00:00Z"}}]})
    respx_mock.get(f"{API}/commentThreads").respond(json={"items": [
        {"snippet": {"topLevelComment": {"snippet": {"authorChannelId": {"value": "U1"},
                                                      "textDisplay": "보겸으로 삼행시 참여합니다"}}}}]})
    conn = db.connect(tmp_path / "t.db")
    sent = []
    ex = Ex(Extracted(is_giveaway=True, many_similar_entries=True, product="아이폰18",
                      entry_format="보겸으로 3행시", format_confidence="low", entry_steps=["댓글"]))
    chans = [{"name": "보겸TV", "handle": "@x", "format_in_video": True}]
    cli.collect(conn, YouTubeClient("k", httpx.Client()), chans, FILTERS, sent.append, ex)
    assert ex.calls[0]["format_in_video"] is True
    assert ex.calls[0]["comments"] == ["보겸으로 삼행시 참여합니다"]  # 인기순·최신순 합쳐도 중복 제거
    msg = next(m for m in sent if m.startswith("<유튜브>"))
    assert "응모양식: 보겸으로 3행시 (댓글 패턴으로 추정" in msg


@respx.mock(assert_all_called=False)
def test_ordinary_channel_still_needs_keywords(tmp_path, respx_mock):
    _two_videos(respx_mock, ["그냥 응원합니다"])
    respx_mock.get(f"{API}/videos").respond(json={"items": [
        {"id": "v1", "snippet": {"title": "리뷰", "description": "평범", "publishedAt": "2999-01-01T00:00:00Z"}}]})
    conn = db.connect(tmp_path / "t.db")
    ex = Ex(Extracted(is_giveaway=True, form_url="https://x"))
    cli.collect(conn, YouTubeClient("k", httpx.Client()), CHANNELS, FILTERS, lambda m: None, ex)
    assert ex.calls == []  # 키워드가 없으면 AI를 호출하지 않는다


def _fmt_ch(**kw):
    return {"format_in_video": True, "usual_methods": ["subscribe", "like", "comment"],
            "usual_steps": ["구독", "좋아요", "알림 설정"], "max_age_days": 14, **kw}


class OneShot:
    def __init__(self, ex):
        self.ex = ex

    def extract(self, *a, **k):
        return self.ex


def test_owner_pinned_comment_counts_as_event_even_if_ai_says_no():
    from datetime import datetime, timezone
    now = datetime(2026, 9, 19, 23, tzinfo=timezone.utc)
    ex = cli.analyze_video(
        OneShot(Extracted(is_giveaway=False, product="아이폰")), text="t", title="대출받아서 싹다사왔습니다",
        published_at="2026-09-19T10:20:16Z", comments=[], ch=_fmt_ch(), now=now,
        pinned="영상에서 말씀드리는 응모양식이 아닐경우 당첨이취소됩니다")
    assert ex.is_giveaway and ex.owner_announced and ex.is_real_event
    assert {"subscribe", "like", "comment"} <= set(ex.entry_methods)
    assert ex.entry_steps[:3] == ["구독", "좋아요", "알림 설정"]


def test_owner_hint_ignored_for_winner_announcement_and_regular_channels():
    from datetime import datetime, timezone
    now = datetime(2026, 9, 20, tzinfo=timezone.utc)
    ended = cli.analyze_video(OneShot(Extracted()), text="t", title="t", published_at="2026-09-19T10:00:00Z",
                              comments=[], ch=_fmt_ch(), now=now, pinned="당첨자 발표! 응모양식 확인")
    assert not ended.is_giveaway
    normal = cli.analyze_video(OneShot(Extracted()), text="t", title="t", published_at="2026-09-19T10:00:00Z",
                               comments=[], ch={}, now=now, pinned="응모양식 확인")
    assert not normal.is_giveaway


def test_format_channel_event_without_deadline_expires_after_max_age():
    from datetime import datetime, timezone
    ex = cli.analyze_video(OneShot(Extracted(is_giveaway=True, many_similar_entries=True)), text="t", title="t",
                           published_at="2026-09-19T10:00:00Z", pinned="", comments=[], ch=_fmt_ch(),
                           now=datetime(2026, 10, 30, tzinfo=timezone.utc))
    assert ex.is_ended and cli._decide(ex, "t") == "skipped"


@respx.mock(assert_all_called=False)
def test_format_channel_event_asks_user_for_format_instead_of_drafting(tmp_path, respx_mock):
    from test_approval import FakeTG
    respx_mock.get(f"{API}/channels").respond(json={"items": [{
        "id": "UC1", "contentDetails": {"relatedPlaylists": {"uploads": "UU1"}}}]})
    respx_mock.get(f"{API}/playlistItems").respond(json={"items": [
        {"contentDetails": {"videoId": "v1", "videoPublishedAt": "2999-01-01T00:00:00Z"}}]})
    respx_mock.get(f"{API}/videos").respond(json={"items": [{
        "id": "v1", "snippet": {"title": "아이폰 대방출", "description": "보겸TV",
                                "publishedAt": "2999-01-01T00:00:00Z"}}]})
    respx_mock.get(f"{API}/commentThreads").respond(json={"items": [
        {"snippet": {"topLevelComment": {"snippet": {"authorChannelId": {"value": "UC1"},
                                                      "textDisplay": "영상에서 말씀드리는 응모양식이 아닐경우 당첨취소"}}}}]})
    conn = db.connect(tmp_path / "t.db")
    tg, sent = FakeTG(), []
    chans = [{"name": "보겸TV", "handle": "@x", "format_in_video": True,
              "usual_methods": ["subscribe", "like", "comment"], "last_format": "지난 양식"}]
    cli.collect(conn, YouTubeClient("k", httpx.Client()), chans, FILTERS, sent.append,
                OneShot(Extracted(is_giveaway=True, entry_methods=["comment"])), tg)
    assert any(m.startswith("<유튜브>") and "영상 말미에서 확인" in m for m in sent)
    request = tg.sent[0][1]
    assert "답장" in request and "지난 양식" in request
    assert conn.execute("SELECT status FROM events").fetchone()["status"] == "awaiting_format"
