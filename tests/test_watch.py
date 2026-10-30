import httpx
import respx

from giveaway import cli, ghapi
from giveaway.telegram_bot import API as TG_API, Telegram


class FakeTG:
    chat_id = "42"

    def __init__(self, batches):
        self.batches, self.answered = list(batches), []

    def peek_updates(self, timeout=50):
        return self.batches.pop(0) if self.batches else []

    def answer_callback(self, cid, text=""):
        self.answered.append((cid, text))


def cb(cid, chat=42):
    return {"update_id": 1, "callback_query": {"id": cid, "data": "post:1",
                                                "message": {"message_id": 9, "chat": {"id": chat}}}}


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        self.t += 30.0  # peek 한 번이 30초 걸린다고 가정
        return self.t


def test_watch_dispatches_poll_on_update_and_acks_button_immediately():
    tg, calls = FakeTG([[], [cb("c1")], [cb("c1")], []]), []
    out = cli.watch_loop(tg, minutes=5, dispatch=lambda: calls.append(1), cooldown=240, now=Clock())
    assert out["dispatched"] == 1 and calls == [1]  # 같은 업데이트가 남아 있어도 쿨다운 안에는 다시 깨우지 않는다
    assert tg.answered == [("c1", "접수됨 — 곧 처리됩니다")]  # 로딩 표시는 한 번만 끈다


def test_watch_ignores_other_chats_and_exits_at_deadline():
    tg, calls = FakeTG([[cb("x", chat=999)]]), []
    out = cli.watch_loop(tg, minutes=2, dispatch=lambda: calls.append(1), now=Clock())
    assert calls == [] and out["peeks"] >= 1 and tg.answered == []


def test_watch_wakes_again_after_cooldown_if_updates_remain():
    tg = FakeTG([[cb("a")]] + [[cb("a")]] * 30)
    calls = []
    cli.watch_loop(tg, minutes=30, dispatch=lambda: calls.append(1), cooldown=240, now=Clock())
    assert len(calls) >= 2  # poll이 실패해 업데이트가 안 줄었다면 재시도


@respx.mock
def test_peek_updates_does_not_send_offset_so_nothing_is_acknowledged():
    route = respx.post(f"{TG_API}/botT/getUpdates").respond(json={"ok": True, "result": [{"update_id": 5}]})
    assert Telegram("T", "42", httpx.Client()).peek_updates(10) == [{"update_id": 5}]
    import json
    body = json.loads(route.calls.last.request.read())
    assert "offset" not in body and body["timeout"] == 10


@respx.mock
def test_answer_callback_survives_expired_buttons():
    respx.post(f"{TG_API}/botT/answerCallbackQuery").respond(400, json={"ok": False, "description": "query is too old"})
    Telegram("T", "42", httpx.Client()).answer_callback("c", "x")  # 예외 없이 통과


@respx.mock
def test_ensure_watcher_dispatches_only_when_none_active(monkeypatch):
    monkeypatch.setenv("GH_TOKEN", "t")
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    runs = respx.get("https://api.github.com/repos/o/r/actions/workflows/watch.yml/runs").respond(
        json={"total_count": 0})
    disp = respx.post("https://api.github.com/repos/o/r/actions/workflows/watch.yml/dispatches").respond(204)
    assert ghapi.ensure_watcher(300, httpx.Client()) == "300분 감시 시작"
    import json
    assert disp.called and json.loads(disp.calls.last.request.read())["inputs"] == {"minutes": "300"}
    assert runs.call_count == 2  # in_progress, queued 둘 다 확인
    disp.reset()
    runs.respond(json={"total_count": 1})
    assert ghapi.ensure_watcher(300, httpx.Client()) == "이미 실행 중" and not disp.called


def test_ensure_watcher_is_a_noop_without_github_env(monkeypatch):
    monkeypatch.delenv("GH_TOKEN", raising=False)
    assert ghapi.ensure_watcher(180) == "토큰 없음"


@respx.mock
def test_ensure_watcher_reports_failure_instead_of_raising(monkeypatch):
    monkeypatch.setenv("GH_TOKEN", "t")
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    respx.get("https://api.github.com/repos/o/r/actions/workflows/watch.yml/runs").respond(403)
    assert "실패" in ghapi.ensure_watcher(180, httpx.Client())
