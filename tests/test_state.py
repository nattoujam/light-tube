import pytest
from datetime import datetime
from app.state import AppState, State
from app.events import Event
from app.models import Video

@pytest.fixture
def sample_video():
    return Video("1", "Title", "Channel", datetime.now(), "http://example.com")

def test_boot_to_browse():
    state = AppState()
    assert state.state == State.BOOT
    state.handle_event(Event.CACHE_LOADED, videos=[])
    assert state.state == State.BROWSE

def test_browse_to_launching(sample_video):
    state = AppState(state=State.BROWSE, display_videos=[sample_video])
    state.handle_event(Event.PLAY_SELECTED, video=sample_video)
    assert state.state == State.LAUNCHING
    assert state.selected_video == sample_video

def test_launching_to_playing(sample_video):
    state = AppState(state=State.LAUNCHING, selected_video=sample_video)
    state.handle_event(Event.MPV_SPAWNED, pid=1234, video=sample_video)
    assert state.state == State.PLAYING
    assert state.mpv_pid == 1234
    assert state.now_playing == sample_video

def test_playing_to_afterplay(sample_video):
    state = AppState(state=State.PLAYING, now_playing=sample_video, mpv_pid=1234)
    state.handle_event(Event.MPV_EXITED)
    assert state.state == State.AFTER_PLAY
    assert state.last_played_video == sample_video
    assert state.last_played_video_id == sample_video.id
    assert state.now_playing is None

def test_launching_error():
    state = AppState(state=State.LAUNCHING)
    state.handle_event(Event.MPV_SPAWN_FAILED, error="mpv not found")
    assert state.state == State.ERROR
    assert state.error_message == "mpv not found"

def test_updating_flow():
    state = AppState(state=State.BROWSE)
    state.handle_event(Event.UPDATE)
    assert state.state == State.UPDATING
    state.handle_event(Event.UPDATE_SUCCEEDED, added_count=5)
    assert state.state == State.BROWSE
    assert "+5件" in state.update_status
