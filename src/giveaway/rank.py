from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
DIFFICULTY = {"click": 0, "subscribe": 1, "like": 1, "comment": 2, "google_form": 3, "form": 3, "sns_share": 4, "other": 4}


def parse_deadline(value: str) -> datetime | None:
    """날짜만 있으면 그날 23:59:59 KST로 본다."""
    if not value:
        return None
    try:
        if len(value) == 10:
            return datetime.fromisoformat(value).replace(hour=23, minute=59, second=59, tzinfo=KST)
        dt = datetime.fromisoformat(value)
        return dt if dt.tzinfo else dt.replace(tzinfo=KST)
    except ValueError:
        return None


def score(*, tags: list[str], prize_value_est: int, entry_methods: list[str],
          deadline: str, now: datetime) -> int:
    s = 0
    if "it" in tags:
        s += 30
    s += min(prize_value_est // 20000, 30)  # 60만원 이상이면 30점 상한
    hardest = max((DIFFICULTY.get(m, 4) for m in entry_methods), default=2)
    s += 20 - hardest * 4
    dl = parse_deadline(deadline)
    if dl:
        left = (dl - now).total_seconds() / 3600
        if 0 < left <= 24:
            s += 20
        elif left <= 72:
            s += 10
    return max(0, min(s, 100))
