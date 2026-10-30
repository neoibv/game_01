"""개발용 진단(임시): 새 쿼리·키워드로 발견 → AI 판정 결과(분야·제품)를 확인한다(DB·텔레그램 미사용)."""
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import yaml

from giveaway import db, discover
from giveaway.cli import _decide, analyze_video, _gather_comments
from giveaway.collectors.youtube import YouTubeClient
from giveaway.detect import detect, excluded_topic, load_filters
from giveaway.extract import Extractor

cfg = yaml.safe_load(Path("config/discovery.yaml").read_text(encoding="utf-8"))
filters = load_filters(Path("config/filters.yaml"))
yt = YouTubeClient(os.environ["YOUTUBE_API_KEY"], httpx.Client(timeout=60))
api = Extractor(os.environ["ANTHROPIC_API_KEY"])
conn = db.connect(Path(tempfile.mkdtemp()) / "t.db")
after = (datetime.now(timezone.utc) - timedelta(days=cfg["lookback_days"])).strftime("%Y-%m-%dT%H:%M:%SZ")
print("쿼리별:", {q: len(yt.search_videos(q, after, cfg.get("category_id", ""))) for q in cfg["queries"]})
found = discover.run_discovery(conn, yt, cfg, published_after=after, exclude_channel_ids=set(), filters=filters)
cands = [v for v in found if detect(v.text, filters).is_candidate]
print(f"\nIT/가전 키워드 통과·키보드 제외 후보 {len(found)}개, 이벤트 키워드 {len(cands)}개 → AI(상위 26개)\n")
tally = {}
for v in cands[:26]:
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
    if excluded_topic(f"{ex.product} {ex.prize}", filters):
        d = "skipped(제외분야)"
    tally[d] = tally.get(d, 0) + 1
    print(f"[{d:13}] 구독자 {v.subscribers} 댓글 {v.comment_count} | {v.channel_name[:10]} | {v.title[:40]}")
    if d == "confirmed":
        print(f"      제품={ex.product!r} 기한={ex.deadline!r}")
print("\n집계:", tally)
