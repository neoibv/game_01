"""텔레그램으로 보낼 묶음 메시지 형식."""
from dataclasses import dataclass, field

LIMIT = 3800  # 텔레그램 4096자 제한 여유

TIER_TITLES = {
    1: "🥇 1순위 — IT·전자기기",
    2: "🥈 2순위 — 아기·출산용품",
    3: "🥉 3순위 — 기프티콘·여행·기타",
}
CATEGORY_TIER = {"it": 1, "baby": 2, "gift_travel": 3, "other": 3}

# AI 분류가 없을 때의 키워드 분류 (앞쪽 분류가 우선)
KEYWORDS = [
    ("it", ["그래픽카드", "rtx", "지포스", "라데온", "ssd", "hdd", "메인보드", "cpu", "램", "모니터",
            "키보드", "마우스", "노트북", "컴퓨터", "pc", "케이스", "파워", "쿨러", "공유기", "스마트폰",
            "갤럭시", "아이폰", "태블릿", "이어폰", "헤드폰", "스피커", "tv", "가전", "충전기", "보조배터리",
            "카메라", "게이밍", "스마트워치", "청소기", "에어컨", "가습기", "체험단"]),
    ("baby", ["아기", "유아", "아가", "출산", "임산부", "임신", "신생아", "기저귀", "분유", "육아",
              "젖병", "유모차", "카시트", "태교"]),
    ("gift_travel", ["기프티콘", "상품권", "쿠폰", "커피", "스타벅스", "치킨", "여행", "숙박", "호텔",
                     "항공", "리조트", "입장권", "네이버페이"]),
]


def classify(text: str, default: str = "other") -> str:
    lowered = text.lower()
    for category, words in KEYWORDS:
        if any(w in lowered for w in words):
            return category
    return default


def tier_of(category: str) -> int:
    return CATEGORY_TIER.get(category, 3)


@dataclass
class YtEntry:
    channel: str
    title: str
    product: str
    deadline: str
    url: str
    apply_link: str = ""
    score: int = 0
    steps: list[str] = field(default_factory=list)
    entry_format: str = ""
    format_inferred: bool = False  # 시청자 댓글 패턴으로 추정한 양식(영상 말미 확인 필요)
    condition: str = ""            # 가입·구매 등 조건(제외 설정을 껐을 때만 표시됨)
    comment_rule: str = ""         # 댓글 필수 키워드·최소 줄 수
    membership: str = ""           # 채널 멤버십 필수/우대 여부 표시
    video_check: bool = False      # 양식·멤버십이 영상에서만 안내되는 채널
    target: str = ""               # 댓글을 달 곳(게시글/영상/둘 다)
    linked: list[str] = field(default_factory=list)  # 게시물에 연결된 영상 "제목 — URL"


@dataclass
class SiteEntry:
    source: str
    title: str
    prize: str
    deadline: str
    url: str
    category: str = "other"
    score: int = 0
    manual: bool = False  # 로그인/매크로 금지 등으로 직접 응모해야 함


def format_youtube(entries: list[YtEntry]) -> str:
    blocks = [f"<유튜브> 이벤트 확정 ({len(entries)}건)"]
    for i, e in enumerate(sorted(entries, key=lambda x: -x.score), 1):
        lines = [f"{i}) 영상제목: [{e.channel}] {e.title}",
                 f"제품: {e.product or '미상'}",
                 f"이벤트 기한: {e.deadline or '미상'}"]
        if e.steps:
            lines.append("응모 방법: " + " → ".join(e.steps))
        if e.entry_format:
            lines.append(f"응모양식: {e.entry_format}" + (" (댓글 패턴으로 추정 — 영상 말미에서 확인!)" if e.format_inferred else ""))
        if e.video_check:
            lines.append("🎬 영상 말미에서 확인: 댓글 양식 · 멤버십 가입 여부 (양식은 답장으로 알려주시면 초안을 만들어 드려요)")
        if e.target:
            lines.append(f"댓글 위치: {e.target}")
        if e.comment_rule:
            lines.append(f"댓글 조건: {e.comment_rule}")
        for v in e.linked:
            lines.append(f"연결 영상: {v}")
        if e.membership:
            lines.append(f"💳 멤버십: {e.membership}")
        if e.condition:
            lines.append(f"⚠️ 조건: {e.condition}")
        lines.append(f"링크: {e.url}")
        if e.apply_link:
            lines.append(f"응모: {e.apply_link}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def format_sites(entries: list[SiteEntry]) -> str:
    blocks = [f"[사이트 이벤트] 총 {len(entries)}건"]
    for tier in (1, 2, 3):
        group = sorted((e for e in entries if tier_of(e.category) == tier), key=lambda x: -x.score)
        if not group:
            continue
        lines = [f"{TIER_TITLES[tier]} ({len(group)})"]
        for e in group:
            detail = " · ".join(p for p in (f"경품: {e.prize}" if e.prize else "",
                                            f"마감: {e.deadline}" if e.deadline else "") if p)
            lines.append(f"• {e.title}" + (" ⚠️직접 응모" if e.manual else ""))
            if detail:
                lines.append(f"  {detail}")
            lines.append(f"  {e.url}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def split_message(text: str, limit: int = LIMIT) -> list[str]:
    """빈 줄 단위로 나눠 한 메시지가 limit를 넘지 않게 한다. 한 블록이 너무 길면 줄 단위로 자른다."""
    chunks, current = [], ""
    for block in text.split("\n\n"):
        while len(block) > limit:
            cut = block.rfind("\n", 0, limit)
            cut = cut if cut > 0 else limit
            chunks.append(block[:cut])
            block = block[cut:].lstrip("\n")
        if current and len(current) + 2 + len(block) > limit:
            chunks.append(current)
            current = block
        else:
            current = f"{current}\n\n{block}" if current else block
    if current:
        chunks.append(current)
    return chunks
