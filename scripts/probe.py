"""개발용 진단(임시): 지정한 보겸 영상에 실제 추출기를 돌려 판정 결과를 출력한다."""
import os
from datetime import datetime, timezone

from giveaway.cli import _gather_comments, apply_channel_defaults
from giveaway.collectors.youtube import YouTubeClient
from giveaway.extract import Extractor

yt = YouTubeClient(os.environ["YOUTUBE_API_KEY"])
ex_api = Extractor(os.environ["ANTHROPIC_API_KEY"])
CH = {"usual_methods": ["subscribe", "like"], "usual_steps": ["구독", "좋아요", "알림 설정"]}
today = datetime.now(timezone.utc).date().isoformat()

for vid in ["xgUfFBs8Ulw", "so_WXtECMs4", "whcLKbyCrqs", "7mWwou2_bBA"]:
    v = yt.videos([vid], "보겸TV")[0]
    # 채널 ID는 영상 소유자: 고정댓글 판별용
    import httpx
    cid = httpx.get("https://www.googleapis.com/youtube/v3/videos",
                    params={"part": "snippet", "id": vid, "key": os.environ["YOUTUBE_API_KEY"]}).json()["items"][0]["snippet"]["channelId"]
    pinned, others = _gather_comments(yt, vid, cid, True)
    v.pinned_comment = pinned
    both = [c for c in others if "보겸" in c and "아이폰듀오" in c and len([x for x in c.split("\n") if x.strip()]) >= 2]
    multi = [c for c in others if len([x for x in c.split("\n") if x.strip()]) >= 2]
    print(f"\n=== {v.title} ({v.published_at[:10]}) {vid}")
    print(f"댓글 {len(others)}개 / 2줄이상 {len(multi)} / '보겸'+'아이폰듀오'+2줄 {len(both)} / 고정댓글 {bool(pinned)}")
    try:
        ex = ex_api.extract(v.text, title=v.title, published_at=v.published_at, today=today,
                            comments=others, format_in_video=True)
    except Exception as e:  # noqa: BLE001
        print("추출 실패:", e)
        continue
    if ex.is_giveaway:
        apply_channel_defaults(ex, CH)
    for k in ("is_giveaway", "is_ended", "many_similar_entries", "product", "prize", "deadline", "entry_methods",
              "entry_steps", "required_keywords", "comment_min_lines", "entry_format", "format_confidence",
              "membership", "requires_purchase_or_signup", "signup_condition", "comment_prompt"):
        print(f"  {k}: {getattr(ex, k)}")
    if ex.is_giveaway:
        try:
            print("  초안:", repr(ex_api.draft_comment(v.title, v.description, ex)))
        except Exception as e:  # noqa: BLE001
            print("  초안 실패:", e)
