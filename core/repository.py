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

    def save_remote_videos(self, channel_id: int, platform: str, channel_name: str, remote_videos: List[RemoteVideo]):
        added_count = 0
        for rv in remote_videos:
            video = Video(
                id=f"{platform}:{rv.video_id}", # Unique ID for internal storage
                title=rv.title,
                channel=channel_name,
                upload_date=rv.published_at,
                url=rv.watch_url,
                platform=platform,
                channel_id=channel_id,
                video_id=rv.video_id,
                created_at=datetime.now()
            )
            # add_video uses INSERT OR IGNORE and returns the number of inserted rows (0 or 1)
            added_count += self.storage.add_video(video)
        return added_count

    def get_latest_video_date(self, channel_id: int) -> Optional[datetime]:
        with self.storage._connection() as conn:
            cursor = conn.execute("SELECT MAX(upload_date) FROM videos WHERE channel_id = ?", (channel_id,))
            row = cursor.fetchone()
            if row and row[0]:
                return datetime.fromisoformat(row[0])
        return None

    def get_oldest_video_date(self, channel_id: int) -> Optional[datetime]:
        with self.storage._connection() as conn:
            cursor = conn.execute("SELECT MIN(upload_date) FROM videos WHERE channel_id = ?", (channel_id,))
            row = cursor.fetchone()
            if row and row[0]:
                return datetime.fromisoformat(row[0])
        return None
