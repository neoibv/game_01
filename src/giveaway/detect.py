from pathlib import Path

import yaml

from .models import Detection


def load_filters(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def detect(text: str, filters: dict) -> Detection:
    lowered = text.lower()
    matched = [k for k in filters["include"] if k.lower() in lowered]
    excluded = [k for k in filters.get("exclude", []) if k.lower() in lowered]
    # 제외어가 있어도 다른 포함어가 남으면 후보로 둔다(종료 안내 영상에 새 이벤트가 같이 있을 수 있음).
    # 제외어 구문에 포함된 단어만으로 걸린 경우는 후보에서 뺀다.
    if excluded:
        stripped = lowered
        for k in excluded:
            stripped = stripped.replace(k.lower(), "")
        matched = [k for k in filters["include"] if k.lower() in stripped]
    return Detection(matched=matched, excluded=excluded)


def excluded_topic(text: str, filters: dict | None) -> str:
    """제외 분야(exclude_topics)에 걸리는 첫 단어를 돌려준다. 없으면 빈 문자열."""
    lowered = (text or "").lower()
    for word in (filters or {}).get("exclude_topics", []):
        if word.lower() in lowered:
            return word
    return ""


def blocked_topic(filters: dict | None, *parts: str) -> str:
    """사용자가 '관심없음'으로 막은 단어(blocked_topics)가 든 첫 단어. 제목·제품·경품처럼 짧은 글에만 쓴다."""
    lowered = "\n".join(p or "" for p in parts).lower()
    return next((w for w in (filters or {}).get("blocked_topics", []) if w.lower() in lowered), "")
