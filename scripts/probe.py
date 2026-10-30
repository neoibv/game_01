"""개발용 진단: 저장된 유튜브 이벤트의 판정 내용과, 보겸 채널 영상의 설명/고정댓글/자막 접근 가능 여부를 출력한다.
공개 영상 정보만 출력한다(개인정보 없음)."""
import os
import sys
from pathlib import Path

from giveaway import db
from giveaway.collectors.youtube import YouTubeClient

conn = db.connect(Path("data/giveaways.db"))

print("=== 저장된 유튜브 이벤트 ===")
for r in conn.execute("SELECT * FROM events WHERE source='youtube' ORDER BY id"):
    print(f"[{r['status']}] {r['host']} | {r['title'][:50]}\n   methods={r['entry_methods']} macro_banned={r['macro_banned']} "
          f"deadline={r['deadline']} product={r['product']} prize={(r['prize'] or '')[:40]}\n   req={r['requirements']}\n   {r['source_url']}")

yt = YouTubeClient(os.environ["YOUTUBE_API_KEY"])
try:
    from youtube_transcript_api import YouTubeTranscriptApi
except ImportError:
    YouTubeTranscriptApi = None


def transcript(video_id: str):
    if YouTubeTranscriptApi is None:
        return None, "라이브러리 없음"
    try:
        if hasattr(YouTubeTranscriptApi, "get_transcript"):
            items = YouTubeTranscriptApi.get_transcript(video_id, languages=["ko", "en"])
            return [(i["start"], i["text"]) for i in items], ""
        fetched = YouTubeTranscriptApi().fetch(video_id, languages=["ko", "en"])
        return [(s.start, s.text) for s in fetched], ""
    except Exception as e:  # noqa: BLE001
        return None, f"{type(e).__name__}: {str(e)[:200]}"


for name in ("보겸TV", "보겸S"):
    cached = db.get_meta(conn, f"channel:{name}")
    print(f"\n=== {name} === cached={bool(cached)}")
    if not cached:
        continue
    channel_id, uploads = cached.split("|")
    ids = yt.recent_video_ids(uploads, "2000-01-01T00:00:00Z")[:8]
    for v in yt.videos(ids, name):
        pinned, others = yt.comments(v.video_id, channel_id)
        print(f"\n--- {v.title} ({v.published_at}) {v.url}")
        print("설명:", v.description[:300].replace("\n", " / "))
        print("고정댓글:", pinned[:300].replace("\n", " / "))
        print("상위댓글 샘플:", [c[:60] for c in others[:5]])
        segs, err = transcript(v.video_id)
        if segs is None:
            print("자막: 실패 ->", err)
        else:
            tail = segs[-25:]
            print(f"자막: {len(segs)}줄, 마지막 구간:", " ".join(t for _, t in tail)[:600].replace("\n", " "))
