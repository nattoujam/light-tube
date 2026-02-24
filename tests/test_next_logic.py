import pytest
from datetime import datetime, timedelta
from app.models import Video
from app.next_logic import select_next_video, get_related_videos

@pytest.fixture
def videos():
    base_date = datetime(2023, 1, 1)
    return [
        Video("1", "V1", "ChA", base_date, "url1"),
        Video("2", "V2", "ChA", base_date + timedelta(days=1), "url2"),
        Video("3", "V3", "ChB", base_date + timedelta(days=2), "url3"),
        Video("4", "V4", "ChA", base_date - timedelta(days=1), "url4", viewed=True),
    ]

def test_related_logic(videos):
    target = videos[0] # ChA, 2023-01-01
    related = get_related_videos(videos, target)

    # Same channel is ChA: V2, V4
    assert len(related) == 2
    # V2 is unviewed, V4 is viewed. Unviewed first.
    assert related[0].id == "2"
    assert related[1].id == "4"

def test_select_next_priority_related(videos):
    # If playing V1, next should be related unviewed (V2)
    next_v = select_next_video(videos, current_video_id="1")
    assert next_v.id == "2"

def test_select_next_priority_new_unviewed(videos):
    # If playing V3 (ChB), no related unviewed in ChB.
    # Should pick Newest unviewed (V2 is 01-02, V1 is 01-01).
    next_v = select_next_video(videos, current_video_id="3")
    assert next_v.id == "2"

def test_exclude_current_and_last(videos):
    # Current V1, Last V2. Candidates V3, V4.
    # V3 is unviewed.
    next_v = select_next_video(videos, current_video_id="1", last_video_id="2")
    assert next_v.id == "3"

def test_random_fallback():
    videos = [
        Video("1", "V1", "ChA", datetime.now(), "url1", viewed=True),
        Video("2", "V2", "ChB", datetime.now(), "url2", viewed=True),
    ]
    # Both viewed, no current playing. Should pick one (random).
    next_v = select_next_video(videos)
    assert next_v is not None
    assert next_v.id in ["1", "2"]
