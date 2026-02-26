from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class Video:
    id: str # Internal ID (or video_id for backward compatibility)
    title: str
    channel: str
    upload_date: datetime
    url: str
    viewed: bool = False
    started_at: Optional[datetime] = None
    platform: Optional[str] = None
    channel_id: Optional[int] = None
    video_id: Optional[str] = None
    created_at: Optional[datetime] = None

@dataclass
class Channel:
    id: Optional[int]
    platform: str
    name: str
    external_id: str
    created_at: datetime
