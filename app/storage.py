import json
import os
from datetime import datetime
from typing import List, Optional
from .models import Video

class VideoStorage:
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.videos: List[Video] = []
        self.load()

    def load(self) -> None:
        if not os.path.exists(self.filepath):
            self.videos = []
            return

        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.videos = [
                    Video(
                        id=v['id'],
                        title=v['title'],
                        channel=v['channel'],
                        upload_date=datetime.fromisoformat(v['upload_date']),
                        url=v['url'],
                        viewed=v.get('viewed', False),
                        started_at=datetime.fromisoformat(v['started_at']) if v.get('started_at') else None
                    )
                    for v in data
                ]
        except (json.JSONDecodeError, KeyError, ValueError):
            self.videos = []

    def save(self) -> None:
        data = [
            {
                'id': v.id,
                'title': v.title,
                'channel': v.channel,
                'upload_date': v.upload_date.isoformat(),
                'url': v.url,
                'viewed': v.viewed,
                'started_at': v.started_at.isoformat() if v.started_at else None
            }
            for v in self.videos
        ]
        with open(self.filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def add_video(self, video: Video) -> None:
        if not any(v.id == video.id for v in self.videos):
            self.videos.append(video)

    def get_video_by_id(self, video_id: str) -> Optional[Video]:
        for v in self.videos:
            if v.id == video_id:
                return v
        return None

    def update_video(self, video: Video) -> None:
        for i, v in enumerate(self.videos):
            if v.id == video.id:
                self.videos[i] = video
                break
