"""개발용 진단(임시): 노트북·스마트폰·모니터·가전 쿼리별 검색 결과 수와 샘플."""
import os
from datetime import datetime, timedelta, timezone

import httpx

KEY = os.environ["YOUTUBE_API_KEY"]
http = httpx.Client(timeout=60)
after = (datetime.now(timezone.utc) - timedelta(days=14)).strftime("%Y-%m-%dT%H:%M:%SZ")
QUERIES = ["노트북 이벤트", "노트북 증정", "노트북 추첨", "구독자 이벤트 노트북",
           "스마트폰 이벤트", "스마트폰 증정", "휴대폰 이벤트", "갤럭시 이벤트", "아이폰 이벤트",
           "모니터 이벤트", "모니터 증정", "구독자 이벤트 모니터",
           "가전 이벤트", "가전 증정", "청소기 이벤트", "공기청정기 이벤트", "에어프라이어 이벤트", "로봇청소기 이벤트",
           "태블릿 이벤트", "아이패드 이벤트", "이어폰 이벤트", "구독자 이벤트 가전"]
for q in QUERIES:
    r = http.get("https://www.googleapis.com/youtube/v3/search", params={
        "part": "snippet", "type": "video", "q": q, "order": "date", "maxResults": 50, "publishedAfter": after,
        "regionCode": "KR", "relevanceLanguage": "ko", "key": KEY}).json()
    items = r.get("items", [])
    print(f"{q!r}: {len(items)}건", [(i["snippet"]["channelTitle"][:8], i["snippet"]["title"][:24]) for i in items[:3]])
