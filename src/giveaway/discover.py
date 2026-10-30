"""설정한 채널 밖의 IT 유튜버(구독자 적은 곳 포함)를 이벤트 키워드 검색으로 찾는다."""
from . import db
from .collectors.youtube import YouTubeClient
from .models import Video


def run_discovery(conn, yt: YouTubeClient, cfg: dict, *, published_after: str,
                  exclude_channel_ids: set[str]) -> list[Video]:
    """검색(쿼리당 100 unit) → 새 영상만 → 구독자 수 범위 필터. 구독자 적은 순으로 돌려준다(당첨 확률)."""
    ids: list[str] = []
    for q in cfg.get("queries", [])[: cfg.get("max_queries_per_run", 8)]:
        for vid in yt.search_videos(q, published_after, cfg.get("category_id", "")):
            if vid not in ids:
                ids.append(vid)
    ids = [v for v in ids if not db.url_exists(conn, f"https://www.youtube.com/watch?v={v}")]
    if not ids:
        return []
    wanted = set(ids)
    videos = [v for v in yt.videos(ids) if v.video_id in wanted and v.channel_id not in exclude_channel_ids]
    subs = yt.channel_subscribers(sorted({v.channel_id for v in videos}))
    lo, hi = cfg.get("min_subscribers", 0), cfg.get("max_subscribers", 0)
    out = []
    for v in videos:
        n = subs.get(v.channel_id)
        v.subscribers, v.subscribers_known = n, v.channel_id in subs
        if n is not None and (n < lo or (hi and n > hi)):
            continue
        out.append(v)
    out.sort(key=lambda v: (v.subscribers is None, v.subscribers or 0))
    return out
