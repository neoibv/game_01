"""개발용 진단(임시): search.list가 왜 0건인지 파라미터 조합별로 확인한다."""
import os
from datetime import datetime, timedelta, timezone

import httpx

KEY = os.environ["YOUTUBE_API_KEY"]
http = httpx.Client(timeout=60)
now = datetime.now(timezone.utc)
after7 = (now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
after30 = (now - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
print("now:", now.isoformat(), "after7:", after7)


def run(label, **params):
    base = {"part": "snippet", "type": "video", "maxResults": 10, "key": KEY}
    r = http.get("https://www.googleapis.com/youtube/v3/search", params={**base, **params})
    try:
        data = r.json()
    except Exception:  # noqa: BLE001
        print(label, "HTTP", r.status_code, r.text[:200])
        return
    if "error" in data:
        print(label, "ERROR", data["error"].get("code"), data["error"].get("message", "")[:200])
        return
    items = data.get("items", [])
    print(f"{label}: {len(items)}건 (total {data.get('pageInfo', {}).get('totalResults')})",
          [(i["snippet"]["channelTitle"][:10], i["snippet"]["title"][:22]) for i in items[:3]])


for q in ["이벤트", "구독자 이벤트 증정", "구독자 이벤트 증정 댓글 이어폰"]:
    print(f"\n## q={q!r}")
    run("A 현재설정(7일,cat28,KR,ko,date)", q=q, publishedAfter=after7, videoCategoryId="28",
        regionCode="KR", relevanceLanguage="ko", order="date")
    run("B 카테고리 없음", q=q, publishedAfter=after7, regionCode="KR", relevanceLanguage="ko", order="date")
    run("C 지역·언어 없음", q=q, publishedAfter=after7, videoCategoryId="28", order="date")
    run("D 날짜 제한 없음", q=q, videoCategoryId="28", regionCode="KR", relevanceLanguage="ko", order="date")
    run("E 관련도순+30일", q=q, publishedAfter=after30, regionCode="KR", relevanceLanguage="ko", order="relevance")
