from abc import ABC, abstractmethod
from typing import List, Tuple
from datetime import datetime
from dataclasses import dataclass

@dataclass
class RemoteVideo:
    video_id: str
    title: str
    published_at: datetime
    watch_url: str

class PlatformBase(ABC):
    @abstractmethod
    def resolve_external_id(self, name: str) -> str:
        """Resolves channel name to external ID."""
        pass

    @abstractmethod
    def fetch_videos(self, external_id: str, limit: int = 50, published_before: datetime = None) -> List[RemoteVideo]:
        """Fetches videos from the platform."""
        pass
