from typing import Dict
from datetime import datetime
import yaml
from .platform.base import PlatformBase
from .platform.platform_a import PlatformA
from .platform.platform_b import PlatformB

class PlatformFactory:
    def __init__(self, config_path: str):
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)

    def get_platform(self, platform_name: str) -> PlatformBase:
        if platform_name == "platform_a":
            api_key = self.config["platform_a"]["api_key"]
            return PlatformA(api_key)
        elif platform_name == "platform_b":
            base_url = self.config["platform_b"]["base_url"]
            return PlatformB(base_url)
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
