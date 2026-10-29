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
            "items": {"enum": ["comment", "subscribe", "like", "google_form", "form", "click", "sns_share", "other"]},
        },
        "required_keywords": {"type": "array", "items": {"type": "string"}, "description": "댓글에 반드시 넣어야 하는 문구/해시태그"},
        "comment_prompt": {"type": "string", "description": "댓글로 답해야 하는 질문/주제. 없으면 빈 문자열"},
        "form_url": {"type": "string", "description": "응모용 폼 URL. 없으면 빈 문자열"},
        "deadline": {"type": "string", "description": "응모 마감 YYYY-MM-DD 또는 YYYY-MM-DDTHH:MM. 모르면 빈 문자열"},
        "announce_at": {"type": "string", "description": "당첨 발표일 YYYY-MM-DD. 모르면 빈 문자열"},
        "announce_where": {"type": "string", "description": "당첨 발표 장소(커뮤니티 탭, 고정 댓글 등)"},
        "macro_banned": {"type": "boolean", "description": "매크로/자동 응모 금지 또는 부정 참여 시 당첨 취소 문구가 있는가"},
        "needs_login_or_captcha": {"type": "boolean", "description": "외부 사이트 로그인/본인인증/캡차가 필요한가"},
    },
    "required": ["is_giveaway", "is_ended"],
}

SYSTEM = (
    "너는 한국 유튜브 영상 설명란/고정 댓글에서 경품 이벤트 정보를 추출하는 도구다. "
    "텍스트에 없는 내용을 추측하지 말고, 모르면 빈 값으로 둔다. 영상 속 협찬 제품 소개나 "
    "단순 구독 요청은 이벤트가 아니다. 반드시 record_giveaway 도구로만 답한다."
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
    def auto_enterable(self) -> bool:
        """클릭만으로 끝나는 이벤트에 한해 완전 자동 대상."""
        return (self.entry_methods == ["click"] and not self.macro_banned
                and not self.needs_login_or_captcha)


class Extractor:
    def __init__(self, api_key: str, client: httpx.Client | None = None, model: str = MODEL):
        self.api_key = api_key
        self.http = client or httpx.Client(timeout=60)
        self.model = model

    def extract(self, text: str, *, title: str, published_at: str, today: str) -> Extracted:
        resp = self.http.post(
            API_URL,
            headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01"},
            json={
                "model": self.model,
                "max_tokens": 1024,
                "system": SYSTEM,
                "tools": [{"name": TOOL_NAME, "description": "추출 결과 기록", "input_schema": SCHEMA}],
                "tool_choice": {"type": "tool", "name": TOOL_NAME},
                "messages": [{"role": "user", "content": (
                    f"오늘 날짜: {today}\n영상 제목: {title}\n게시일: {published_at}\n\n"
                    f"--- 본문 ---\n{text[:6000]}")}],
            },
        )
        resp.raise_for_status()
        for block in resp.json().get("content", []):
            if block.get("type") == "tool_use" and block.get("name") == TOOL_NAME:
                return Extracted.from_dict(block["input"])
        raise ValueError("tool_use 블록이 응답에 없음")
