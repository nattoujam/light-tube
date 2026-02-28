import pytest
from datetime import datetime, timedelta
from app.models import Video
from app.storage import VideoStorage
import os

@pytest.fixture
def storage():
    db_path = "test_logic.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    s = VideoStorage(db_path)
    base_date = datetime(2023, 1, 1)
    v_list = [
        Video("1", "V1", "ChA", base_date, "url1"),
        Video("2", "V2", "ChA", base_date + timedelta(days=1), "url2"),
        Video("3", "V3", "ChB", base_date + timedelta(days=2), "url3"),
        Video("4", "V4", "ChA", base_date - timedelta(days=1), "url4", viewed=True),
    ]
    for v in v_list:
        s.add_video(v)
    yield s
    if os.path.exists(db_path):
        os.remove(db_path)

def test_related_logic(storage):
    # target ChA, 2023-01-01
    related = storage.get_related_videos(target_id="1")

    # Same channel is ChA: V2, V4
    assert len(related) == 2
    # V2 is unviewed, V4 is viewed. Unviewed first.
    assert related[0].id == "2"
    assert related[1].id == "4"

def test_select_next_priority_related(storage):
    # If playing V1, next should be related unviewed (V2)
    next_v = storage.select_next_video(current_id="1")
    assert next_v.id == "2"

def test_select_next_priority_new_unviewed(storage):
    # If playing V3 (ChB), no related unviewed in ChB.
    # Should pick Newest unviewed (V2 is 01-02, V1 is 01-01).
    next_v = storage.select_next_video(current_id="3")
    assert next_v.id == "2"

def test_exclude_current_and_last(storage):
    # Current V1, Last V2. Candidates V3, V4.
    # V3 is unviewed.
    next_v = storage.select_next_video(current_id="1", last_id="2")
    assert next_v.id == "3"

def test_random_fallback(storage):
    # Both viewed, no current playing. Should pick one (random/stable).
    # Since we use storage from fixture, we might need to clear or use new one
    # but here let's just use what's there.
    # Rule 3 (New tab unviewed) will fail as all are viewed (if we mark them).
    # Rule 5 will pick stable.
    for v in storage.get_new_videos(100):
        v.viewed = True
        storage.update_video(v)

    next_v = storage.select_next_video()
    assert next_v is not None
    assert next_v.id in ["1", "2", "3", "4"]
