from dataclasses import dataclass, field


@dataclass
class Video:
    video_id: str
    channel_name: str
    title: str
    description: str
    published_at: str
    pinned_comment: str = ""
    channel_id: str = ""

    @property
    def url(self) -> str:
        return f"https://www.youtube.com/watch?v={self.video_id}"

    @property
    def text(self) -> str:
        return "\n".join(p for p in (self.title, self.description, self.pinned_comment) if p)


@dataclass
class Detection:
    matched: list[str] = field(default_factory=list)
    excluded: list[str] = field(default_factory=list)

    @property
    def is_candidate(self) -> bool:
        return bool(self.matched)
