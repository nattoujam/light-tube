import unittest
from datetime import datetime
from app.models import Video
from app.state import State, AppState

class TestCore(unittest.TestCase):
    def test_video_creation(self):
        now = datetime.now()
        video = Video(
            id="test-id",
            title="Test Title",
            channel_id=1,
            upload_date=now,
            url="http://example.com/video"
        )
        # デフォルト値の確認など、非自明な部分のみを残す
        self.assertFalse(video.viewed)
        self.assertIsNone(video.started_at)

    def test_app_state_initialization(self):
        state = AppState()
        # 初期状態が正しく設定されていることを確認
        self.assertEqual(state.state, State.BOOT)
        self.assertEqual(state.current_tab, "New")
        self.assertIsNone(state.now_playing)
        self.assertIsNone(state.mpv_pid)

if __name__ == "__main__":
    unittest.main()
