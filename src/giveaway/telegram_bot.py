import httpx

API = "https://api.telegram.org"
MAX_LEN = 4096


def send_message(token: str, chat_id: str, text: str, client: httpx.Client | None = None) -> None:
    c = client or httpx.Client(timeout=20)
    resp = c.post(
        f"{API}/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text[:MAX_LEN], "disable_web_page_preview": False},
    )
    resp.raise_for_status()
