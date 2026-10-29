import httpx

from ..models import Video

API = "https://www.googleapis.com/youtube/v3"


class YouTubeClient:
    def __init__(self, api_key: str, client: httpx.Client | None = None):
        self.api_key = api_key
        self.http = client or httpx.Client(timeout=30)

    def _get(self, path: str, **params) -> dict:
        resp = self.http.get(f"{API}/{path}", params={**params, "key": self.api_key})
        resp.raise_for_status()
        return resp.json()

    def resolve_channel(self, name: str, handle: str = "") -> tuple[str, str] | None:
        """(channel_id, uploads_playlist_id). handle이 있으면 1 unit, 없으면 검색(100 unit)."""
        if handle:
            data = self._get("channels", part="contentDetails", forHandle=handle)
        else:
            found = self._get("search", part="snippet", type="channel", q=name, maxResults=1)
            if not found.get("items"):
                return None
            data = self._get("channels", part="contentDetails",
                             id=found["items"][0]["snippet"]["channelId"])
        items = data.get("items") or []
        if not items:
            return None
        return items[0]["id"], items[0]["contentDetails"]["relatedPlaylists"]["uploads"]

    def recent_video_ids(self, uploads_playlist: str, published_after: str) -> list[str]:
        data = self._get("playlistItems", part="contentDetails",
                         playlistId=uploads_playlist, maxResults=50)
        return [
            i["contentDetails"]["videoId"]
            for i in data.get("items", [])
            if i["contentDetails"].get("videoPublishedAt", "") >= published_after
        ]

    def videos(self, video_ids: list[str], channel_name: str) -> list[Video]:
        out: list[Video] = []
        for i in range(0, len(video_ids), 50):
            data = self._get("videos", part="snippet", id=",".join(video_ids[i:i + 50]))
            for item in data.get("items", []):
                s = item["snippet"]
                out.append(Video(item["id"], channel_name, s["title"],
                                 s.get("description", ""), s["publishedAt"]))
        return out

    def pinned_comment(self, video_id: str, channel_id: str) -> str:
        """채널 주인이 쓴 댓글 중 상단(relevance) 노출된 것. 댓글이 막힌 영상은 빈 문자열."""
        try:
            data = self._get("commentThreads", part="snippet", videoId=video_id,
                             order="relevance", maxResults=5, textFormat="plainText")
        except httpx.HTTPStatusError:
            return ""
        for t in data.get("items", []):
            top = t["snippet"]["topLevelComment"]["snippet"]
            if top.get("authorChannelId", {}).get("value") == channel_id:
                return top.get("textDisplay", "")
        return ""
