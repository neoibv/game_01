"""이벤트 모음 사이트 목록 페이지 파서. 로그인 없이 읽을 수 있는 목록만 다룬다."""
import html
import json
import re
from dataclasses import dataclass
from datetime import date

import httpx

UA = "giveaway-hunter/0.1 (+https://github.com/neoibv/game_01)"


@dataclass
class SiteItem:
    source: str          # danawa | jupjup | eventskr
    url: str
    title: str
    host: str = ""
    category: str = ""
    prize: str = ""
    deadline: str = ""   # YYYY-MM-DD 또는 ""

    @property
    def text(self) -> str:
        parts = [("제목", self.title), ("주최", self.host), ("분류", self.category),
                 ("경품", self.prize), ("마감", self.deadline)]
        return "\n".join(f"{k}: {v}" for k, v in parts if v)


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def _month_day_to_iso(month: int, day: int, today: date) -> str:
    year = today.year
    try:
        d = date(year, month, day)
    except ValueError:
        return ""
    if (today - d).days > 30:  # 12월에 보는 1월 마감 같은 연도 넘김
        d = date(year + 1, month, day)
    return d.isoformat()


def parse_eventskr(page: str, today: date, base: str = "https://events.kr/") -> list[SiteItem]:
    items = []
    for row in re.findall(r'<tr class="event-list-row">(.*?)</tr>', page, re.S):
        link = re.search(r'href="(event\.php\?id=\d+)"', row)
        title = re.search(r'<strong class="event-title-text"[^>]*>(.*?)</strong>', row, re.S)
        if not link or not title:
            continue
        host = re.search(r'class="[^"]*event-host[^"]*">\[?(.*?)\]?</span>', row, re.S)
        cat = re.search(r'class="category-badge">(.*?)</span>', row, re.S)
        prize = re.search(r'class="prize-tooltip">(.*?)</span>', row, re.S)
        dl = re.search(r"마감:\s*(\d{1,2})/(\d{1,2})", row)
        items.append(SiteItem(
            source="eventskr", url=base + link.group(1), title=_clean(title.group(1)),
            host=_clean(host.group(1)) if host else "",
            category=_clean(cat.group(1)) if cat else "",
            prize=_clean(prize.group(1)) if prize else "",
            deadline=_month_day_to_iso(int(dl.group(1)), int(dl.group(2)), today) if dl else ""))
    return items


def parse_jupjup(page: str) -> list[SiteItem]:
    items = []
    for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', page, re.S):
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        for block in data if isinstance(data, list) else [data]:
            if block.get("@type") != "ItemList":
                continue
            for el in block.get("itemListElement", []):
                host, _, prize = (el.get("description") or "").partition(" · ")
                prize = "" if prize.strip() == "확인 필요" else prize.strip()
                items.append(SiteItem(source="jupjup", url=el["url"], title=el["name"],
                                      host=host.strip(), prize=prize))
    return items


def parse_danawa(page: str) -> list[SiteItem]:
    items, seen = [], set()
    for li in re.findall(r"<li[^>]*>(.*?)</li>", page, re.S):
        link = re.search(r'href="(https://event\.danawa\.com/[A-Za-z0-9_]+)"', li)
        title = re.search(r'class="event_banner_title">(.*?)</div>', li, re.S)
        if not link or not title or link.group(1) in seen:
            continue
        seen.add(link.group(1))
        badge = re.search(r'class="event_banner_badge">(.*?)</div>', li, re.S)
        items.append(SiteItem(source="danawa", url=link.group(1), title=_clean(title.group(1)),
                              host="다나와", category=_clean(badge.group(1)) if badge else ""))
    return items


SOURCES = {
    "eventskr": ("https://events.kr/", lambda page, today: parse_eventskr(page, today)),
    "jupjup": ("https://jupjup.app/", lambda page, today: parse_jupjup(page)),
    "danawa": ("https://event.danawa.com/", lambda page, today: parse_danawa(page)),
}


def fetch_all(today: date, client: httpx.Client | None = None,
              enabled: list[str] | None = None) -> tuple[list[SiteItem], list[str]]:
    """(items, 실패한 소스 목록). 한 소스가 실패해도 나머지는 계속한다."""
    http = client or httpx.Client(timeout=30, follow_redirects=True, headers={"User-Agent": UA})
    items, failed = [], []
    for name, (url, parser) in SOURCES.items():
        if enabled is not None and name not in enabled:
            continue
        try:
            resp = http.get(url)
            resp.raise_for_status()
            parsed = parser(resp.text, today)
            if not parsed:
                failed.append(f"{name}(0건 — 페이지 구조 변경 의심)")
            items.extend(parsed)
        except httpx.HTTPError as e:
            failed.append(f"{name}({e.__class__.__name__})")
    return items, failed
