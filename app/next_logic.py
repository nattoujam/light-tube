import random
from typing import List, Optional
from .models import Video

def get_related_videos(videos: List[Video], target_video: Video) -> List[Video]:
    """
    MVP Related logic: Same channel, close upload date.
    Prioritizes unviewed videos.
    """
    related = [
        v for v in videos
        if v.id != target_video.id and v.channel == target_video.channel
    ]
    # Sort by proximity to target_video.upload_date
    related.sort(key=lambda x: abs((x.upload_date - target_video.upload_date).total_seconds()))

    # Prioritize unviewed within related
    unviewed = [v for v in related if not v.viewed]
    viewed = [v for v in related if v.viewed]
    return unviewed + viewed

def select_next_video(
    all_videos: List[Video],
    current_video_id: Optional[str] = None,
    last_video_id: Optional[str] = None
) -> Optional[Video]:
    """
    Next playback selection rules (Section 8).
    """
    exclude_ids = set()
    if current_video_id:
        exclude_ids.add(current_video_id)
    if last_video_id:
        exclude_ids.add(last_video_id)

    candidates = [v for v in all_videos if v.id not in exclude_ids]
    if not candidates:
        return None

    current_video = next((v for v in all_videos if v.id == current_video_id), None)

    # 1. Related (Unviewed)
    if current_video:
        related = get_related_videos(candidates, current_video)
        unviewed_related = [v for v in related if not v.viewed]
        if unviewed_related:
            return unviewed_related[0]

    # 2. Same channel unviewed (newest first)
    if current_video:
        same_channel_unviewed = [
            v for v in candidates
            if v.channel == current_video.channel and not v.viewed
        ]
        if same_channel_unviewed:
            same_channel_unviewed.sort(key=lambda x: x.upload_date, reverse=True)
            return same_channel_unviewed[0]

    # 3. New tab unviewed (all unviewed, newest first)
    new_unviewed = [v for v in candidates if not v.viewed]
    if new_unviewed:
        new_unviewed.sort(key=lambda x: x.upload_date, reverse=True)
        return new_unviewed[0]

    # 4. Related (Viewed) as fallback before random
    if current_video:
        related = get_related_videos(candidates, current_video)
        if related:
            return related[0]

    # 5. Random (fallback)
    return random.choice(candidates)
