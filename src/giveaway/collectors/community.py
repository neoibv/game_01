"""유튜브 채널 커뮤니티(게시물) 탭 읽기.

공식 API가 없어 채널의 /posts 페이지(공개)에 담긴 ytInitialData를 읽는다. 구조가 바뀌거나 차단되면
게시물 0건으로 나오므로 호출하는 쪽에서 실패로 처리한다(우회하지 않는다).
"""
import json
import re
from dataclasses import dataclass, field

import httpx

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0 Safari/537.36")
VIDEO_URL = re.compile(r"(?:[?&]v=|/shorts/|youtu\.be/)([\w-]{11})")
AGE_UNITS = {"초": 0, "분": 0, "시간": 0, "일": 1, "주": 7, "개월": 30, "달": 30, "년": 365,
             "second": 0, "minute": 0, "hour": 0, "day": 1, "week": 7, "month": 30, "year": 365}


@dataclass
class Post:
    post_id: str
    channel_id: str
    text: str
    age_days: float | None
    edited: bool = False
    video_ids: list[str] = field(default_factory=list)

    @property
    def url(self) -> str:
        return f"https://www.youtube.com/post/{self.post_id}"


def parse_age_days(label: str) -> float | None:
    """'4일 전(수정됨)', '3주 전', '1개월 전', '5 hours ago' → 대략의 일수. 모르면 None."""
    m = re.search(r"(\d+)\s*(초|분|시간|일|주|개월|달|년)\s*전", label) or \
        re.search(r"(\d+)\s*(second|minute|hour|day|week|month|year)s?\s*ago", label, re.I)
    if not m:
        return None
    return float(int(m.group(1)) * AGE_UNITS[m.group(2).lower()])


def _walk(node, key: str, out: list) -> None:
    if isinstance(node, dict):
        if key in node:
            out.append(node[key])
        for v in node.values():
            _walk(v, key, out)
    elif isinstance(node, list):
        for v in node:
            _walk(v, key, out)


def parse_posts(html: str, channel_id: str) -> list[Post]:
    m = re.search(r"var ytInitialData = (\{.*?\});</script>", html, re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return []
    raw: list[dict] = []
    _walk(data, "backstagePostRenderer", raw)
    posts, seen = [], set()
    for p in raw:
        post_id = p.get("postId")
        if not post_id or post_id in seen:
            continue
        seen.add(post_id)
        runs = (p.get("contentText") or {}).get("runs", [])
        text = "".join(r.get("text", "") for r in runs)
        # 본문의 링크 텍스트는 '...'로 잘려 보이므로 실제 URL(navigationEndpoint)에서 영상 ID를 읽는다.
        vids: list[str] = []
        for r in runs:
            url = (((r.get("navigationEndpoint") or {}).get("commandMetadata") or {})
                   .get("webCommandMetadata") or {}).get("url", "")
            hit = VIDEO_URL.search(url)
            if hit and hit.group(1) not in vids:
                vids.append(hit.group(1))
        attached: list[str] = []
        _walk(p.get("backstageAttachment", {}), "videoId", attached)
        vids += [v for v in attached if v not in vids]
        when = "".join(r.get("text", "") for r in (p.get("publishedTimeText") or {}).get("runs", []))
        posts.append(Post(post_id=post_id, channel_id=channel_id, text=text, age_days=parse_age_days(when),
                          edited="수정됨" in when or "edited" in when.lower(), video_ids=vids))
    return posts


def fetch_posts(channel_id: str, client: httpx.Client | None = None) -> list[Post]:
    http = client or httpx.Client(timeout=30, follow_redirects=True)
    http.cookies.set("CONSENT", "YES+1", domain=".youtube.com")  # 동의 화면 건너뛰기용(공개 페이지 읽기)
    http.cookies.set("SOCS", "CAI", domain=".youtube.com")
    resp = http.get(f"https://www.youtube.com/channel/{channel_id}/posts",
                    headers={"User-Agent": UA, "Accept-Language": "ko-KR,ko;q=0.9"})
    resp.raise_for_status()
    return parse_posts(resp.text, channel_id)
