import pytest
from datetime import datetime
from app.state import AppState, State
from app.events import Event
from app.models import Video, Channel

@pytest.fixture
def sample_video():
    channel = Channel(1, "youtube", "Channel", "ext_id", datetime.now())
    return Video("1", "Title", channel, datetime.now(), "http://example.com", "youtube", 1)

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

def test_ui_state_events(sample_video):
    from app.state import FocusArea
    state = AppState(state=State.BROWSE, display_videos=[sample_video, sample_video], focus_area=FocusArea.MAIN)

    # Help toggle
    assert not state.show_help
    state.handle_event(Event.HELP_TOGGLE)
    assert state.show_help
    state.handle_event(Event.HELP_TOGGLE)
    assert not state.show_help

    # Cursor movement
    assert state.selected_idx == 0
    state.handle_event(Event.CURSOR_DOWN)
    assert state.selected_idx == 1
    state.handle_event(Event.CURSOR_DOWN) # Boundary check
    assert state.selected_idx == 1
    state.handle_event(Event.CURSOR_UP)
    assert state.selected_idx == 0
    state.handle_event(Event.CURSOR_UP) # Boundary check
    assert state.selected_idx == 0

def test_area_switch():
    from app.state import FocusArea
    state = AppState(state=State.BROWSE, focus_area=FocusArea.SIDEBAR)
    state.handle_event(Event.TAB_NEXT)
    assert state.focus_area == FocusArea.MAIN
    state.handle_event(Event.TAB_NEXT)
    assert state.focus_area == FocusArea.SIDEBAR
