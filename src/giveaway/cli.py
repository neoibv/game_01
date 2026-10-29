import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from . import db, state, telegram_bot
from .collectors.youtube import YouTubeClient
from .detect import detect, load_filters

ROOT = Path(__file__).resolve().parents[2]
LOOKBACK_FIRST_RUN_DAYS = 30
MAX_NOTIFY_PER_RUN = 20


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def format_alert(video, matched: list[str]) -> str:
    snippet = video.pinned_comment or video.description
    return (
        f"🎁 [{video.channel_name}] 이벤트 후보\n{video.title}\n"
        f"키워드: {', '.join(matched)}\n\n{snippet[:300]}\n\n{video.url}"
    )


def collect(conn, yt: YouTubeClient, channels: list[dict], filters: dict,
            notify) -> dict:
    last_run = db.get_meta(conn, "last_collect_at")
    published_after = last_run or _iso(_now() - timedelta(days=LOOKBACK_FIRST_RUN_DAYS))
    stats = {"channels": 0, "videos": 0, "new": 0, "unresolved": []}
    notified = 0

    for ch in channels:
        cached = db.get_meta(conn, f"channel:{ch['name']}")
        if cached:
            channel_id, uploads = cached.split("|")
        else:
            resolved = yt.resolve_channel(ch["name"], ch.get("handle", ""))
            if not resolved:
                stats["unresolved"].append(ch["name"])
                continue
            channel_id, uploads = resolved
            db.set_meta(conn, f"channel:{ch['name']}", f"{channel_id}|{uploads}")
            notify(f"📺 채널 확정: {ch['name']} → https://www.youtube.com/channel/{channel_id}\n"
                   "다른 채널이면 알려주세요.")
        stats["channels"] += 1

        ids = yt.recent_video_ids(uploads, published_after)
        for video in yt.videos(ids, ch["name"]):
            stats["videos"] += 1
            det = detect(video.text, filters)
            if not det.is_candidate:
                video.pinned_comment = yt.pinned_comment(video.video_id, channel_id)
                det = detect(video.text, filters)
            if not det.is_candidate:
                continue
            is_new = db.add_event(conn, source="youtube", source_url=video.url,
                                  title=video.title, host=video.channel_name,
                                  matched=det.matched, raw_text=video.text)
            if is_new:
                stats["new"] += 1
                if notified < MAX_NOTIFY_PER_RUN:
                    notify(format_alert(video, det.matched))
                    db.mark_notified(conn, video.url)
                    notified += 1

    if stats["unresolved"]:
        notify("⚠️ 채널을 찾지 못함: " + ", ".join(stats["unresolved"]))
    db.set_meta(conn, "last_collect_at", _iso(_now()))
    return stats


def _env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        sys.exit(f"환경변수 {name} 가 필요합니다")
    return value


def cmd_collect(args) -> None:
    channels = yaml.safe_load((ROOT / "config/channels.yaml").read_text(encoding="utf-8"))["channels"]
    filters = load_filters(ROOT / "config/filters.yaml")
    token, chat = _env("TELEGRAM_BOT_TOKEN"), _env("TELEGRAM_CHAT_ID")
    conn = db.connect(Path(args.db))
    stats = collect(conn, YouTubeClient(_env("YOUTUBE_API_KEY")), channels, filters,
                    lambda text: telegram_bot.send_message(token, chat, text))
    print(stats)


def cmd_state(args) -> None:
    key = _env("STATE_KEY")
    src, dst = Path(args.src), Path(args.dst)
    (state.encrypt_file if args.action == "encrypt" else state.decrypt_file)(src, dst, key)


def main() -> None:
    p = argparse.ArgumentParser(prog="giveaway")
    sub = p.add_subparsers(required=True)
    c = sub.add_parser("collect")
    c.add_argument("--db", default="data/giveaways.db")
    c.set_defaults(func=cmd_collect)
    s = sub.add_parser("state")
    s.add_argument("action", choices=["encrypt", "decrypt"])
    s.add_argument("src")
    s.add_argument("dst")
    s.set_defaults(func=cmd_state)
    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
