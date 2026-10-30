"""설정한 채널 밖의 IT 유튜버(구독자 적은 곳 포함)를 이벤트 키워드 검색으로 찾는다."""
import httpx

from . import db, digest
from .detect import excluded_topic
from .collectors.youtube import YouTubeClient
from .models import Video


def run_discovery(conn, yt: YouTubeClient, cfg: dict, *, published_after: str,
                  exclude_channel_ids: set[str], filters: dict | None = None,
                  errors: list[str] | None = None) -> list[Video]:
    """검색(쿼리당 100 unit) → 새 영상만 → 구독자 수 범위 필터. 구독자 적은 순으로 돌려준다(당첨 확률)."""
    ids: list[str] = []
    for q in cfg.get("queries", [])[: cfg.get("max_queries_per_run", 8)]:
        try:
            found = yt.search_videos(q, published_after, cfg.get("category_id", ""))
        except httpx.HTTPStatusError as e:
            # 쿼터/속도 제한(403·429)이면 남은 쿼리도 같은 이유로 실패하니 중단하고, 지금까지 찾은 것만 쓴다
            if errors is not None:
                errors.append(f"검색 중단({e.response.status_code}) '{q}'")
            break
        for vid in found:
            if vid not in ids:
                ids.append(vid)
    ids = [v for v in ids if not db.url_exists(conn, f"https://www.youtube.com/watch?v={v}")]
    if not ids:
        return []
    wanted = set(ids)
    videos = [v for v in yt.videos(ids) if v.video_id in wanted and v.channel_id not in exclude_channel_ids]
    subs = yt.channel_subscribers(sorted({v.channel_id for v in videos}))
    lo, hi = cfg.get("min_subscribers", 0), cfg.get("max_subscribers", 0)
    allowed = set(cfg.get("allowed_categories", ["it"]))
    out = []
    for v in videos:
        # 검색에는 뷰티·생활용품 이벤트도 섞이므로, 제목·설명에 해당 분야 키워드가 있는 영상만 분석한다(AI 비용 절약)
        if allowed and digest.classify(v.text) not in allowed:
            continue
        if excluded_topic(v.text, filters):  # 키보드 등 제외 분야는 AI 호출 전에 거른다
            continue
        n = subs.get(v.channel_id)
        v.subscribers, v.subscribers_known = n, v.channel_id in subs
        if n is not None and (n < lo or (hi and n > hi)):
            continue
        out.append(v)
    out.sort(key=lambda v: (v.subscribers is None, v.subscribers or 0))
    return out[: cfg.get("max_candidates", 40)]
