"""GitHub Actions 워크플로 실행/조회 (GITHUB_TOKEN, 워크플로에 actions: write 필요).
GITHUB_TOKEN으로 만든 workflow_dispatch는 새 실행을 만들 수 있는 예외라서 이 방식이 동작한다."""
import os

import httpx

API = "https://api.github.com"


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"}


def configured() -> bool:
    return bool(os.environ.get("GH_TOKEN") and os.environ.get("GITHUB_REPOSITORY"))


def dispatch(workflow: str, inputs: dict | None = None, *, ref: str = "main",
             client: httpx.Client | None = None) -> None:
    http = client or httpx.Client(timeout=30)
    resp = http.post(f"{API}/repos/{os.environ['GITHUB_REPOSITORY']}/actions/workflows/{workflow}/dispatches",
                     headers=_headers(os.environ["GH_TOKEN"]), json={"ref": ref, "inputs": inputs or {}})
    resp.raise_for_status()


def active_runs(workflow: str, client: httpx.Client | None = None) -> int:
    """진행 중이거나 대기 중인 실행 수."""
    http = client or httpx.Client(timeout=30)
    total = 0
    for status in ("in_progress", "queued"):
        resp = http.get(f"{API}/repos/{os.environ['GITHUB_REPOSITORY']}/actions/workflows/{workflow}/runs",
                        headers=_headers(os.environ["GH_TOKEN"]), params={"status": status, "per_page": 5})
        resp.raise_for_status()
        total += resp.json().get("total_count", 0)
    return total


def ensure_watcher(minutes: int, client: httpx.Client | None = None) -> str:
    """버튼 응답을 몇 초 안에 처리하는 감시 실행(watch.yml)을 켠다. 이미 있으면 그대로 둔다."""
    if not configured():
        return "토큰 없음"
    try:
        if active_runs("watch.yml", client):
            return "이미 실행 중"
        dispatch("watch.yml", {"minutes": str(minutes)}, client=client)
        return f"{minutes}분 감시 시작"
    except httpx.HTTPError as e:
        return f"감시 시작 실패({type(e).__name__})"
