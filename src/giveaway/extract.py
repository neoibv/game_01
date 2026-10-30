"""설명란/댓글 텍스트에서 경품 이벤트 정보를 구조화한다 (Claude tool use)."""
from dataclasses import dataclass, field

import httpx

API_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-haiku-5-5"
TOOL_NAME = "record_giveaway"

SCHEMA = {
    "type": "object",
    "properties": {
        "is_giveaway": {"type": "boolean", "description": "시청자가 응모할 수 있는 진행 중인 경품/증정 이벤트가 있는가"},
        "is_ended": {"type": "boolean", "description": "이미 종료됐거나 당첨자 발표만 있는 글인가"},
        "prize": {"type": "string", "description": "경품 이름과 수량. 없으면 빈 문자열"},
        "prize_value_est": {"type": "integer", "description": "경품 총 추정 가치(원). 모르면 0"},
        "entry_methods": {
            "type": "array",
            "description": "응모를 위해 해야 하는 모든 행동을 빠짐없이(예: 구독+좋아요+댓글+구글폼이면 네 개 모두). 댓글을 달아야 하면 반드시 comment 포함",
            "items": {"type": "string", "enum": ["comment", "subscribe", "like", "google_form", "form", "click", "sns_share", "other"]},
        },
        "entry_steps": {
            "type": "array", "items": {"type": "string"},
            "description": "응모 절차를 순서대로 한 줄씩(예: '채널 구독', '좋아요', '댓글: 영상 보고 느낀 점', '구글폼 작성'). 최대 6개",
        },
        "requires_purchase_or_signup": {
            "type": "boolean",
            "description": "응모에 외부 서비스 회원가입, 상품 구매, 앱 설치, 통신사 가입·개통, 유료 결제 같은 조건이 있는가. 채널 구독·좋아요·댓글·구글폼 작성은 해당 없음",
        },
        "signup_condition": {"type": "string", "description": "위 조건의 내용 한 줄. 없으면 빈 문자열"},
        "entry_format": {
            "type": "string",
            "description": "댓글/응모 양식 요약(예: '보겸으로 3행시', '사연 + 참여합니다'). 본문에 명시되어 있거나, 영상에서 안내하는 채널이면 시청자 댓글의 공통 양식에서 추정. 모르면 빈 문자열",
        },
        "format_confidence": {
            "type": "string", "enum": ["high", "low", "none"],
            "description": "entry_format의 확실성. high=본문에 명시, low=시청자 댓글 패턴에서 추정, none=알 수 없음",
        },
        "required_keywords": {"type": "array", "items": {"type": "string"}, "description": "댓글에 반드시 넣어야 하는 문구/해시태그"},
        "comment_prompt": {"type": "string", "description": "댓글로 답해야 하는 질문/주제. 없으면 빈 문자열"},
        "form_url": {"type": "string", "description": "응모/참여용 링크(구글폼, 이벤트 페이지 등) 중 본문에 실제로 적힌 URL. 영상·채널·SNS 홍보 링크는 제외. 없으면 빈 문자열"},
        "many_similar_entries": {"type": "boolean", "description": "시청자 댓글 중 여러 개가 같은 양식/문구(질문 답변 형식, 같은 해시태그, '참여합니다' 등)로 달려 있어 실제 응모가 진행 중으로 보이는가. 일반 감상 댓글이 대부분이면 false. 댓글이 주어지지 않았으면 false"},
        "product": {"type": "string", "description": "경품 제품명(브랜드+모델). 없으면 빈 문자열"},
        "category": {"type": "string", "enum": ["it", "baby", "gift_travel", "other"],
                     "description": "경품 분류. it=PC부품·전자기기·가전·스마트기기, baby=아기용품·출산준비용품, gift_travel=기프티콘·상품권·여행·숙박, other=그 외"},
        "deadline": {"type": "string", "description": "응모 마감 YYYY-MM-DD 또는 YYYY-MM-DDTHH:MM. 모르면 빈 문자열"},
        "announce_at": {"type": "string", "description": "당첨 발표일 YYYY-MM-DD. 모르면 빈 문자열"},
        "announce_where": {"type": "string", "description": "당첨 발표 장소(커뮤니티 탭, 고정 댓글 등)"},
        "macro_banned": {"type": "boolean", "description": "매크로/자동 응모 금지 또는 부정 참여 시 당첨 취소 문구가 있는가"},
        "needs_login_or_captcha": {"type": "boolean", "description": "외부 사이트 로그인/본인인증/캡차가 필요한가"},
    },
    "required": ["is_giveaway", "is_ended"],
}

SYSTEM = (
    "너는 한국 유튜브 영상 설명란/고정 댓글, 또는 이벤트 모음 사이트 목록 항목에서 경품 이벤트 정보를 추출하는 도구다. "
    "텍스트에 없는 내용을 추측하지 말고, 모르면 빈 값으로 둔다. 응모에 필요한 행동(구독·좋아요·댓글·폼 제출 등)은 "
    "하나도 빠뜨리지 않고 entry_methods와 entry_steps에 적는다. 마감일이 오늘 날짜보다 이전이면 is_ended=true다. 영상 속 협찬 제품 소개나 "
    "단순 구독 요청, 공모전·설문조사·체험단 모집만 있는 글은 경품 이벤트가 아니다(경품 추첨이 함께 명시된 경우만 해당). 반드시 record_giveaway 도구로만 답한다."
)


@dataclass
class Extracted:
    is_giveaway: bool = False
    is_ended: bool = False
    prize: str = ""
    prize_value_est: int = 0
    entry_methods: list[str] = field(default_factory=list)
    required_keywords: list[str] = field(default_factory=list)
    comment_prompt: str = ""
    form_url: str = ""
    entry_steps: list[str] = field(default_factory=list)
    requires_purchase_or_signup: bool = False
    signup_condition: str = ""
    entry_format: str = ""
    format_confidence: str = "none"
    many_similar_entries: bool = False
    product: str = ""
    category: str = "other"
    deadline: str = ""
    announce_at: str = ""
    announce_where: str = ""
    macro_banned: bool = False
    needs_login_or_captcha: bool = False

    @classmethod
    def from_dict(cls, d: dict) -> "Extracted":
        known = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**known)

    @property
    def is_real_event(self) -> bool:
        """진행 중인 경품 이벤트이고, 응모 링크가 있거나 시청자들이 같은 양식으로 참여 중일 때만 확정."""
        return self.is_giveaway and not self.is_ended and (bool(self.form_url) or self.many_similar_entries)

    @property
    def undecided(self) -> bool:
        """이벤트처럼 보이지만 아직 응모 링크/참여 댓글 근거가 없음(막 올라온 영상일 수 있음)."""
        return self.is_giveaway and not self.is_ended and not self.is_real_event

    @property
    def auto_enterable(self) -> bool:
        """클릭만으로 끝나는 이벤트에 한해 완전 자동 대상."""
        return (self.entry_methods == ["click"] and not self.macro_banned
                and not self.needs_login_or_captcha)


class Extractor:
    def __init__(self, api_key: str, client: httpx.Client | None = None, model: str = MODEL):
        self.api_key = api_key
        self.http = client or httpx.Client(timeout=60)
        self.model = model
        self.errors = 0
        self.last_error = ""

    def _post(self, payload: dict) -> dict:
        """API 오류는 응답 본문(원인)을 포함한 메시지로 올린다. httpx 기본 메시지에는 본문이 없다."""
        resp = self.http.post(API_URL, headers={"x-api-key": self.api_key,
                                                "anthropic-version": "2023-06-01"}, json=payload)
        if resp.status_code >= 400:
            self.errors += 1
            self.last_error = f"HTTP {resp.status_code}: {resp.text[:300]}"
            raise RuntimeError(self.last_error)
        return resp.json()

    def extract(self, text: str, *, title: str, published_at: str, today: str,
                comments: list[str] | None = None, format_in_video: bool = False) -> Extracted:
        comment_block = ""
        if format_in_video:
            comment_block += (
                "\n\n[채널 특성] 이 채널은 응모 방법을 영상 말미(음성)에서 영상마다 다르게 안내하고, 그 내용은 설명란에 "
                "없는 경우가 많다. 설명/고정댓글에 '영상에서 말씀드리는 응모양식' 같은 문구가 있거나 다수의 시청자 댓글이 "
                "같은 양식(예: '보겸으로 N행시', '사연+참여합니다')을 따르면 진행 중인 이벤트로 본다. 그 경우 댓글들의 공통 "
                "양식을 entry_format에 요약하고 format_confidence는 low로 한다. 일반 감상·응원 댓글뿐이면 이벤트가 아니다.")
        if comments:
            lines = "\n".join(f"- {c[:160]}" for c in comments[:40])
            comment_block += f"\n\n--- 시청자 댓글 {min(len(comments), 40)}개 ---\n{lines}"
        data = self._post({
            "model": self.model,
            "max_tokens": 1024,
            "system": SYSTEM,
            "tools": [{"name": TOOL_NAME, "description": "추출 결과 기록", "input_schema": SCHEMA}],
            "tool_choice": {"type": "tool", "name": TOOL_NAME},
            "messages": [{"role": "user", "content": (
                f"오늘 날짜: {today}\n영상 제목: {title}\n게시일: {published_at}\n\n"
                f"--- 본문 ---\n{text[:6000]}{comment_block}")}],
        })
        for block in data.get("content", []):
            if block.get("type") == "tool_use" and block.get("name") == TOOL_NAME:
                return Extracted.from_dict(block["input"])
        raise ValueError("tool_use 블록이 응답에 없음")


DRAFT_SYSTEM = (
    "너는 유튜브 이벤트에 응모하는 시청자의 댓글을 대신 써주는 도구다. 한국어로 1~3문장, "
    "영상 내용과 이벤트 질문에 진짜로 답하는 자연스러운 댓글을 쓴다. 광고처럼 보이거나 "
    "다른 댓글과 똑같아 보이는 상투구, 과한 이모지는 피한다. 필수 문구가 있으면 그대로 포함한다. "
    "댓글 본문만 출력한다."
)


def _draft_prompt(video_title: str, description: str, ex: "Extracted") -> str:
    return (f"영상 제목: {video_title}\n이벤트 댓글 주제: {ex.comment_prompt or '(지정 없음 — 영상 감상 한마디)'}\n"
            f"댓글 양식: {ex.entry_format or '(지정 없음)'}\n"
            f"필수 문구: {', '.join(ex.required_keywords) or '(없음)'}\n\n영상 설명:\n{description[:2000]}")


def _draft_comment(self: "Extractor", video_title: str, description: str, ex: "Extracted") -> str:
    data = self._post({"model": self.model, "max_tokens": 400, "system": DRAFT_SYSTEM,
                       "messages": [{"role": "user", "content": _draft_prompt(video_title, description, ex)}]})
    text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text").strip()
    if not text:
        raise ValueError("빈 댓글 초안")
    # 모델이 필수 문구를 빠뜨리면 덧붙인다.
    missing = [k for k in ex.required_keywords if k not in text]
    return (text + " " + " ".join(missing)).strip() if missing else text


Extractor.draft_comment = _draft_comment
