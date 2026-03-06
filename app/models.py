from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class Video:
    id: str # Internal ID (usually platform:video_id)
    title: str
    channel_id: int
    upload_date: datetime
    url: str
    viewed: bool = False
    started_at: Optional[datetime] = None
    video_id: Optional[str] = None
    created_at: Optional[datetime] = None
    # The following are typically populated via JOIN from channels table
    channel: str = ""
    platform: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "upload_date": self.upload_date.isoformat(),
            "url": self.url,
            "viewed": 1 if self.viewed else 0,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "channel_id": self.channel_id,
            "video_id": self.video_id,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

@dataclass
class Channel:
    id: Optional[int]
    platform: str
    name: str
    external_id: str
    created_at: datetime
