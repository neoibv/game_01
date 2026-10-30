"""개발용 진단(임시): 지정한 보겸 영상에 실제 추출 로직(analyze_video)을 돌려 판정 결과를 출력한다."""
import os
from datetime import datetime, timezone

import httpx

from giveaway.cli import _decide, _gather_comments, analyze_video
from giveaway.collectors.youtube import YouTubeClient
from giveaway.extract import Extractor

KEY = os.environ["YOUTUBE_API_KEY"]
yt = YouTubeClient(KEY, httpx.Client(timeout=60))
api = Extractor(os.environ["ANTHROPIC_API_KEY"])
CH = {"format_in_video": True, "usual_methods": ["subscribe", "like", "comment"],
      "usual_steps": ["구독", "좋아요", "알림 설정"], "max_age_days": 14}
# 진단 목적: 오래된 영상도 보도록 '지금' 시각을 영상 게시 직후로 둔다
for vid in ["xgUfFBs8Ulw", "so_WXtECMs4", "whcLKbyCrqs", "7mWwou2_bBA"]:
    v = yt.videos([vid], "보겸TV")[0]
    cid = yt._get("videos", part="snippet", id=vid)["items"][0]["snippet"]["channelId"]
    pinned, others = _gather_comments(yt, vid, cid, True)
    v.pinned_comment = pinned
    pub = datetime.strptime(v.published_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    now = pub.replace(hour=23)  # 게시 당일 기준으로 판정
    print(f"\n=== {v.title} ({v.published_at[:10]}) {vid} | 댓글 {len(others)}개 | 고정댓글 {bool(pinned)}: {pinned[:80]!r}")
    try:
        ex = analyze_video(api, text=v.text, title=v.title, published_at=v.published_at, pinned=pinned,
                           comments=others, ch=CH, now=now)
    except Exception as e:  # noqa: BLE001
        print("추출 실패:", e)
        continue
    print("판정:", _decide(ex, v.text, {"exclude_signup_required": True}, now))
    for k in ("is_giveaway", "is_ended", "owner_announced", "many_similar_entries", "product", "deadline",
              "entry_methods", "entry_steps", "entry_format", "format_confidence", "membership",
              "requires_purchase_or_signup"):
        print(f"  {k}: {getattr(ex, k)}")
