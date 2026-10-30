"""개발용 진단(임시): 보겸 채널의 커뮤니티(게시물) 탭을 GitHub Actions에서 읽을 수 있는지 확인한다."""
import json
import re
import sys
from pathlib import Path

import httpx

from giveaway import db

conn = db.connect(Path("data/giveaways.db"))
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0 Safari/537.36")


def walk(node, key, out):
    if isinstance(node, dict):
        if key in node:
            out.append(node[key])
        for v in node.values():
            walk(v, key, out)
    elif isinstance(node, list):
        for v in node:
            walk(v, key, out)


for name in ("보겸TV", "보겸S"):
    cached = db.get_meta(conn, f"channel:{name}")
    channel_id = cached.split("|")[0]
    url = f"https://www.youtube.com/channel/{channel_id}/posts"
    print(f"\n=== {name} {url}")
    try:
        r = httpx.get(url, headers={"User-Agent": UA, "Accept-Language": "ko-KR,ko;q=0.9"},
                      cookies={"CONSENT": "YES+1", "SOCS": "CAI"}, follow_redirects=True, timeout=30)
    except Exception as e:  # noqa: BLE001
        print("요청 실패:", type(e).__name__, e)
        continue
    print("HTTP", r.status_code, "final:", str(r.url)[:100], "len", len(r.text))
    m = re.search(r"var ytInitialData = (\{.*?\});</script>", r.text, re.S)
    if not m:
        print("ytInitialData 없음. 앞부분:", r.text[:300].replace("\n", " "))
        print("consent 페이지?", "consent.youtube.com" in str(r.url) or "Before you continue" in r.text)
        continue
    data = json.loads(m.group(1))
    posts = []
    walk(data, "backstagePostRenderer", posts)
    print("게시물 수:", len(posts))
    for p in posts[:8]:
        runs = (p.get("contentText") or {}).get("runs", [])
        text = "".join(x.get("text", "") for x in runs).replace("\n", " / ")
        when = "".join(x.get("text", "") for x in (p.get("publishedTimeText") or {}).get("runs", []))
        links = []
        for x in runs:
            u = (((x.get("navigationEndpoint") or {}).get("commandMetadata") or {}).get("webCommandMetadata") or {}).get("url")
            if u:
                links.append(u)
        vids = []
        walk(p.get("backstageAttachment", {}), "videoId", vids)
        print(f"- [{when}] {text[:220]}\n    링크={links[:3]} 첨부영상={vids[:2]} 댓글수={((p.get('actionButtons') or {}).get('commentActionButtonsRenderer') or {}).get('replyButton', {}).get('buttonRenderer', {}).get('text', {}).get('simpleText', '')}")
sys.exit(0)
