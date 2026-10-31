"""텔레그램으로 보낼 묶음 메시지 형식."""
from dataclasses import dataclass, field
from datetime import date

LIMIT = 3800  # 텔레그램 4096자 제한 여유

# AI 분류가 없을 때의 키워드 분류 (앞쪽 분류가 우선)
KEYWORDS = [
    ("it", ["그래픽카드", "rtx", "지포스", "라데온", "ssd", "hdd", "메인보드", "cpu", "램", "모니터",
            "마우스", "노트북", "맥북", "컴퓨터", "pc", "케이스", "파워", "쿨러", "공유기", "스마트폰", "휴대폰",
            "핸드폰", "갤럭시", "아이폰", "폴드", "플립", "태블릿", "아이패드", "이어폰", "이어버드", "버즈", "에어팟",
            "헤드폰", "헤드셋", "스피커", "사운드바", "tv", "가전", "충전기", "보조배터리", "카메라", "게이밍",
            "스마트워치", "워치", "청소기", "에어컨", "가습기", "제습기", "공기청정기", "에어프라이어", "세탁기",
            "건조기", "냉장고", "식기세척기", "전자레인지", "밥솥", "블렌더", "선풍기", "정수기", "안마기",
            "드라이기", "면도기", "스타일러", "프로젝터", "웹캠", "마이크", "usb", "허브", "체험단"]),
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


TOPIC_MIN_LEN = 3  # '램'·'tv'처럼 짧은 단어는 다른 낱말 안에 섞여 오차단하므로 차단어로 쓰지 않는다


def topic_words(text: str) -> list[str]:
    """제품 분류 어휘(KEYWORDS) 중 텍스트에 든 것. 관심없음 누르면 이 단어로 관련 이벤트를 막는다."""
    lowered = text.lower()
    return [w for _, words in KEYWORDS for w in words if len(w) >= TOPIC_MIN_LEN and w in lowered]


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
    reach: str = ""                # 구독자·댓글 수(경쟁 정도)
    discovered: bool = False       # 검색으로 새로 발견한 채널
    target: str = ""               # 댓글을 달 곳(게시글/영상/둘 다)
    linked: list[str] = field(default_factory=list)  # 게시물에 연결된 영상 "제목 — URL"


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
        if e.reach:
            lines.append(f"경쟁: {e.reach}" + (" · 🔭 새로 발견한 채널(앞으로 자동 감시)" if e.discovered else ""))
        lines.append(f"링크: {e.url}")
        if e.apply_link:
            lines.append(f"응모: {e.apply_link}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def format_entered(rows: list[dict], today: date) -> str:
    """응모한 이벤트와 결과 발표일 기록(알림 하단에 붙인다). rows: title, announce_at, deadline."""
    if not rows:
        return ""
    lines = [f"📝 응모한 이벤트 ({len(rows)}건)"]
    for r in rows:
        when = r["announce_at"]
        if when:
            try:
                left = (date.fromisoformat(when[:10]) - today).days
                when += " (오늘)" if left == 0 else f" (D-{left})" if left > 0 else " (발표 지남 — 당첨 확인!)"
            except ValueError:
                pass
        else:
            when = "미정" + (f" (마감 {r['deadline']})" if r["deadline"] else "")
        lines.append(f"• {r['title'][:50]}\n  결과 발표: {when}")
    return "\n".join(lines)


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
