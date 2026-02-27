from typing import Dict
from datetime import datetime
import yaml
from .platform.base import PlatformBase
from .platform.youtube import YouTube

class PlatformFactory:
    def __init__(self, config_path: str):
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)

    def get_platform(self, platform_name: str) -> PlatformBase:
        if platform_name == "youtube":
            api_key = self.config["youtube"]["api_key"]
            return YouTube(api_key)
        else:
            raise ValueError(f"Unknown platform: {platform_name}")

class ChannelResolver:
    def __init__(self, factory: PlatformFactory):
        self.factory = factory

    def resolve(self, platform_name: str, name: str) -> str:
        platform = self.factory.get_platform(platform_name)
        return platform.resolve_external_id(name)

class VideoFetcher:
    def __init__(self, factory: PlatformFactory):
        self.factory = factory

    def fetch_recent(self, platform_name: str, external_id: str, limit: int = 50):
        platform = self.factory.get_platform(platform_name)
        return platform.fetch_videos(external_id, limit=limit)

    def fetch_history(self, platform_name: str, external_id: str, published_before: datetime, limit: int = 50):
        platform = self.factory.get_platform(platform_name)
        return platform.fetch_videos(external_id, limit=limit, published_before=published_before)
