from typing import List, Optional
from .models import Video
from .storage import VideoStorage

def get_related_videos(storage: VideoStorage, target_video_id: str) -> List[Video]:
    """
    SQLベースで関連動画を取得します。
    """
    return storage.get_related_videos(target_video_id)

def select_next_video(
    storage: VideoStorage,
    current_video_id: Optional[str] = None,
    last_video_id: Optional[str] = None
) -> Optional[Video]:
    """
    SQLベースで次に再生する動画を選択します。
    """
    return storage.select_next_video(current_video_id, last_video_id)
