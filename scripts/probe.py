"""개발용 진단(임시): 실제 YouTube 검색+AI로 발견 기능이 어떤 채널/영상을 찾는지 확인한다(DB·텔레그램 미사용)."""
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import yaml

from giveaway import db, discover
from giveaway.cli import _decide, analyze_video, _gather_comments
from giveaway.collectors.youtube import YouTubeClient
from giveaway.detect import detect, load_filters
from giveaway.extract import Extractor

cfg = yaml.safe_load(Path("config/discovery.yaml").read_text(encoding="utf-8"))
filters = load_filters(Path("config/filters.yaml"))
yt = YouTubeClient(os.environ["YOUTUBE_API_KEY"], httpx.Client(timeout=60))
api = Extractor(os.environ["ANTHROPIC_API_KEY"])
conn = db.connect(Path(tempfile.mkdtemp()) / "t.db")
after = (datetime.now(timezone.utc) - timedelta(days=cfg["lookback_days"])).strftime("%Y-%m-%dT%H:%M:%SZ")

counts = {q: len(yt.search_videos(q, after, cfg.get("category_id", ""))) for q in cfg["queries"]}
print("쿼리별 결과 수:", counts)
found = discover.run_discovery(conn, yt, cfg, published_after=after, exclude_channel_ids=set())
print(f"\n발견 후보(IT 키워드·구독자 범위 통과) {len(found)}개")
cands = [v for v in found if detect(v.text, filters).is_candidate]
print(f"이벤트 키워드 후보 {len(cands)}개 → AI 판정(상위 18개)\n")
tally = {}
for v in cands[:18]:
    pinned, others = _gather_comments(yt, v.video_id, v.channel_id, False)
    v.pinned_comment = pinned
    try:
        ex = analyze_video(api, text=v.text, title=v.title, published_at=v.published_at, pinned=pinned,
                           comments=others, ch={"name": v.channel_name, "tags": ["it"]})
    except Exception as e:  # noqa: BLE001
        print("추출 실패:", e)
        continue
    d = _decide(ex, v.text, filters)
    if d != "skipped" and ex.category != "it":
        d = "skipped(비IT)"
    tally[d] = tally.get(d, 0) + 1
    print(f"[{d:13}] 구독자 {v.subscribers} 댓글 {v.comment_count} | {v.channel_name} | {v.title[:46]}")
    if d == "confirmed":
        print(f"      제품={ex.product!r} 기한={ex.deadline!r} 방법={ex.entry_methods} 링크={ex.form_url!r} 유사댓글={ex.many_similar_entries} 가입조건={ex.requires_purchase_or_signup}")
print("\n판정 집계:", tally)
