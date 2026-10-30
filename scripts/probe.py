"""개발용 진단(임시): 실제 커뮤니티 게시물 + 실제 AI로 collect_community 판정과 초안, 검수를 확인한다(DB·텔레그램 미사용)."""
import json
import os
import tempfile
from pathlib import Path

import httpx

from giveaway import approval, db
from giveaway.cli import collect_community
from giveaway.collectors import community
from giveaway.collectors.youtube import YouTubeClient
from giveaway.extract import Extractor

yt = YouTubeClient(os.environ["YOUTUBE_API_KEY"], httpx.Client(timeout=60))
api = Extractor(os.environ["ANTHROPIC_API_KEY"])
conn = db.connect(Path(tempfile.mkdtemp()) / "t.db")
for name, cid in (("보겸TV", "UCu9BCtGIEr73LXZsKmoujKw"), ("보겸S", "UCCJ2b2lJE7M77cSuSHLcMOQ")):
    ch = {"name": name, "community": True, "format_in_video": True, "max_age_days": 200,
          "usual_methods": ["subscribe", "like", "comment"], "tags": []}
    print(f"\n######## {name}")
    posts = community.fetch_posts(cid)
    print("게시물", len(posts), [(p.post_id[-6:], p.age_days, p.video_ids) for p in posts])
    res = collect_community(conn, yt, ch, cid, api, filters={"exclude_signup_required": True},
                            subscribe_channels=["UCu9BCtGIEr73LXZsKmoujKw", "UCCJ2b2lJE7M77cSuSHLcMOQ"])
    print("오류:", res["error"], "| 확정", len(res["entries"]), "| 영상이벤트", len(res["video_events"]))
    for c in res["entries"]:
        e, ex = c.entry, c.ex
        print(f"\n--- 확정: {e.title}\n  제품={e.product!r} 기한={e.deadline!r} 위치={e.target!r} 규칙={e.comment_rule!r}")
        print(f"  steps={e.steps} membership={e.membership!r} linked={e.linked}")
        print(f"  methods={ex.entry_methods} keywords={ex.required_keywords} min_lines={ex.comment_min_lines} target={ex.comment_target}")
        try:
            d = api.draft_comment(e.title, c.description, ex)
            print("  초안:", repr(d))
            print("  검수(초안):", approval.review_comment(d, ex.required_keywords, ex.comment_min_lines)["ok"])
            print("  검수(내가 쓴 한 줄 댓글):", approval.review_comment("보겸님 선물 감사합니다", ex.required_keywords, ex.comment_min_lines))
        except Exception as e2:  # noqa: BLE001
            print("  초안 실패:", e2)
    skipped = conn.execute("SELECT title, status FROM events WHERE source='youtube_post' AND status='skipped'").fetchall()
    print("\n제외된 게시물:", [(r["title"][:28]) for r in skipped])
