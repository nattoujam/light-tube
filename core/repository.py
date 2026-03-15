from typing import List, Optional, Any
from datetime import datetime
from app.models import Video, Channel
from app.storage import VideoStorage
from .platform.base import RemoteVideo
from .video_fetcher import VideoFetcher, ChannelResolver

class Repository:
    def __init__(self, storage: VideoStorage, video_fetcher: Optional[VideoFetcher] = None, channel_resolver: Optional[ChannelResolver] = None):
        self.storage = storage
        self.video_fetcher = video_fetcher
        self.channel_resolver = channel_resolver

    def sync_channel(self, channel: Channel, fetch_type: str = "recent", **kwargs: Any) -> int:
        """
        Fetch and save videos for a channel.
        fetch_type can be "recent" or "history".
        """
        if not self.video_fetcher:
            raise RuntimeError("VideoFetcher not initialized")

        if fetch_type == "recent":
            rvs = self.video_fetcher.fetch_recent(channel.platform, channel.external_id, limit=kwargs.get('limit', 50))
        elif fetch_type == "history":
            rvs = self.video_fetcher.fetch_history(channel.platform, channel.external_id,
                                                   published_before=kwargs.get('published_before'),
                                                   limit=kwargs.get('limit', 50))
        else:
            return 0

        return self.save_remote_videos(channel, rvs)

    def resolve_and_save_channel(self, platform: str, name: str, sync: bool = True) -> Channel:
        """
        Resolve channel external ID, save to DB, and optionally sync videos.
        """
        if not self.channel_resolver:
            raise RuntimeError("ChannelResolver not initialized")

        external_id = self.channel_resolver.resolve(platform, name)
        channel_id = self.save_channel(platform, name, external_id)

        channel = Channel(
            id=channel_id,
            platform=platform,
            name=name,
            external_id=external_id,
            created_at=datetime.now()
        )

        if sync:
            self.sync_channel(channel, fetch_type="recent", limit=50)

        return channel

    def save_channel(self, platform: str, name: str, external_id: str) -> int:
        return self.storage.save_channel(platform, name, external_id)

    def save_remote_videos(self, channel: Channel, remote_videos: List[RemoteVideo]):
        added_count = 0
        for rv in remote_videos:
            video = Video(
                id=f"{channel.platform}:{rv.video_id}", # Unique ID for internal storage
                title=rv.title,
                channel=channel,
                upload_date=rv.published_at,
                url=rv.watch_url,
                platform=channel.platform,
                channel_id=channel.id,
                video_id=rv.video_id,
                created_at=datetime.now()
            )
            # add_video uses INSERT OR IGNORE and returns the number of inserted rows (0 or 1)
            added_count += self.storage.add_video(video)
        return added_count

    def get_latest_video_date(self, channel_id: int) -> Optional[datetime]:
        return self.storage.get_latest_video_date(channel_id)

    def get_oldest_video_date(self, channel_id: int) -> Optional[datetime]:
        return self.storage.get_oldest_video_date(channel_id)
