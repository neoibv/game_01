import httpx

API = "https://api.telegram.org"
MAX_LEN = 4096


class Telegram:
    def __init__(self, token: str, chat_id: str, client: httpx.Client | None = None):
        self.token = token
        self.chat_id = str(chat_id)
        self.http = client or httpx.Client(timeout=30)

    def _call(self, method: str, **payload) -> dict:
        resp = self.http.post(f"{API}/bot{self.token}/{method}", json=payload)
        resp.raise_for_status()
        return resp.json()["result"]

    def send(self, text: str, buttons: list[tuple[str, str]] | None = None,
             reply_to: int | None = None) -> int:
        """buttons: [(라벨, callback_data)]. 반환: message_id."""
        payload = {"chat_id": self.chat_id, "text": text[:MAX_LEN]}
        if buttons:
            payload["reply_markup"] = {"inline_keyboard": [[
                {"text": label, "callback_data": data} for label, data in buttons]]}
        if reply_to:
            payload["reply_to_message_id"] = reply_to
        return self._call("sendMessage", **payload)["message_id"]

    def get_updates(self, offset: int | None) -> list[dict]:
        payload = {"timeout": 0, "allowed_updates": ["message", "callback_query"]}
        if offset is not None:
            payload["offset"] = offset
        return self._call("getUpdates", **payload)

    def answer_callback(self, callback_id: str, text: str = "") -> None:
        self._call("answerCallbackQuery", callback_query_id=callback_id, text=text[:200])

    def clear_buttons(self, message_id: int) -> None:
        self._call("editMessageReplyMarkup", chat_id=self.chat_id, message_id=message_id,
                   reply_markup={"inline_keyboard": []})


def send_message(token: str, chat_id: str, text: str, client: httpx.Client | None = None) -> None:
    Telegram(token, chat_id, client).send(text)
