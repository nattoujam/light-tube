import unittest
from datetime import datetime
from app.models import Video
from app.state import State, AppState
from app.events import Event

class TestCore(unittest.TestCase):
    def test_video_creation(self):
        now = datetime.now()
        video = Video(
            id="test-id",
            title="Test Title",
            channel="Test Channel",
            upload_date=now,
            url="http://example.com/video"
        )
        self.assertEqual(video.id, "test-id")
        self.assertEqual(video.title, "Test Title")
        self.assertFalse(video.viewed)

    def test_app_state_initialization(self):
        state = AppState()
        self.assertEqual(state.state, State.BOOT)
        self.assertEqual(state.current_tab, "New")
        self.assertIsNone(state.now_playing)

    def test_event_enum(self):
        self.assertEqual(Event.PLAY_SELECTED.name, "PLAY_SELECTED")
        self.assertEqual(Event.MPV_EXITED.name, "MPV_EXITED")

if __name__ == "__main__":
    unittest.main()
