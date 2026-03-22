from typing import List, Optional
from datetime import datetime
from app.models import Video, Channel
from app.storage import VideoStorage
from .platform.base import RemoteVideo

class Repository:
    def __init__(self, storage: VideoStorage):
        self.storage = storage

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

    def get_new_videos(self, limit: int = 100) -> List[Video]:
        return self.storage.get_new_videos(limit)

    def add_video(self, video: Video) -> int:
        return self.storage.add_video(video)

    def update_video(self, video: Video) -> None:
        self.storage.update_video(video)

    def get_videos_by_channel(self, channel_id: int, limit: int = 100) -> List[Video]:
        return self.storage.get_videos_by_channel(channel_id, limit)

    def get_channels(self) -> List[Channel]:
        return self.storage.get_channels()

    def get_channel_by_id(self, channel_id: int) -> Optional[Channel]:
        return self.storage.get_channel_by_id(channel_id)

    def delete_channel(self, channel_id: int) -> None:
        self.storage.delete_channel(channel_id)

    def select_next_video(self, current_id: Optional[str] = None, last_id: Optional[str] = None) -> Optional[Video]:
        return self.storage.select_next_video(current_id, last_id)
