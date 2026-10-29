"""사용자 OAuth 권한으로 댓글/구독/좋아요. 모두 호출당 50 unit."""
import httpx

TOKEN_URL = "https://oauth2.googleapis.com/token"
API = "https://www.googleapis.com/youtube/v3"


class YouTubeUser:
    def __init__(self, client_id: str, client_secret: str, refresh_token: str,
                 client: httpx.Client | None = None):
        self.client_id, self.client_secret, self.refresh_token = client_id, client_secret, refresh_token
        self.http = client or httpx.Client(timeout=30)
        self._access: str | None = None

    def _headers(self) -> dict:
        if not self._access:
            resp = self.http.post(TOKEN_URL, data={
                "client_id": self.client_id, "client_secret": self.client_secret,
                "refresh_token": self.refresh_token, "grant_type": "refresh_token"})
            resp.raise_for_status()
            self._access = resp.json()["access_token"]
        return {"Authorization": f"Bearer {self._access}"}

    def comment(self, video_id: str, text: str) -> str:
        resp = self.http.post(f"{API}/commentThreads", params={"part": "snippet"},
                              headers=self._headers(),
                              json={"snippet": {"videoId": video_id,
                                                "topLevelComment": {"snippet": {"textOriginal": text}}}})
        resp.raise_for_status()
        return resp.json()["id"]

    def subscribe(self, channel_id: str) -> bool:
        """이미 구독 중이면 False(정상)."""
        resp = self.http.post(f"{API}/subscriptions", params={"part": "snippet"},
                              headers=self._headers(),
                              json={"snippet": {"resourceId": {"kind": "youtube#channel",
                                                               "channelId": channel_id}}})
        if resp.status_code == 400 and "subscriptionDuplicate" in resp.text:
            return False
        resp.raise_for_status()
        return True

    def like(self, video_id: str) -> None:
        resp = self.http.post(f"{API}/videos/rate", params={"id": video_id, "rating": "like"},
                              headers=self._headers())
        resp.raise_for_status()
