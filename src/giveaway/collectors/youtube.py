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

    def videos(self, video_ids: list[str], channel_name: str = "") -> list[Video]:
        out: list[Video] = []
        for i in range(0, len(video_ids), 50):
            data = self._get("videos", part="snippet", id=",".join(video_ids[i:i + 50]))
            for item in data.get("items", []):
                s = item["snippet"]
                out.append(Video(item["id"], channel_name or s.get("channelTitle", ""), s["title"],
                                 s.get("description", ""), s["publishedAt"],
                                 channel_id=s.get("channelId", "")))
        return out

    def comments(self, video_id: str, channel_id: str, order: str = "relevance") -> tuple[str, list[str]]:
        """(채널 주인이 쓴 댓글, 그 외 댓글들). order는 relevance(인기순) 또는 time(최신순). 댓글이 막힌 영상은 ("", [])."""
        try:
            data = self._get("commentThreads", part="snippet", videoId=video_id,
                             order=order, maxResults=50, textFormat="plainText")
        except httpx.HTTPStatusError:
            return "", []
        pinned, others = "", []
        for t in data.get("items", []):
            top = t["snippet"]["topLevelComment"]["snippet"]
            text = top.get("textDisplay", "")
            if not pinned and top.get("authorChannelId", {}).get("value") == channel_id:
                pinned = text
            else:
                others.append(text)
        return pinned, others

    def pinned_comment(self, video_id: str, channel_id: str) -> str:
        return self.comments(video_id, channel_id)[0]
