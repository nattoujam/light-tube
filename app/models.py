from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class Video:
    id: str
    title: str
    channel: str
    upload_date: datetime
    url: str
    viewed: bool = False
    started_at: Optional[datetime] = None
