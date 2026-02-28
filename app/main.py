import curses
import time
from datetime import datetime, timedelta
from typing import Optional, Any, List
from .state import AppState, State
from .events import Event
from .models import Video
from .storage import VideoStorage
from .player import MpvPlayer, MPV_EXIT_CODE_NEXT
from .ui import Tui

class VideoPlayerApp:
    def __init__(self, stdscr: Any):
        self.storage = VideoStorage('videos.db')
        self.app_state = AppState()
        self.player = MpvPlayer()
        self.ui = Tui(stdscr)
        self.stdscr = stdscr

    def initialize_data(self) -> None:
        # Use compat property 'videos' or just check if any record exists
        if not self.storage.get_new_videos(1):
            self.storage.add_video(Video("1", "Big Buck Bunny", "Blender", datetime(2023, 1, 1), "http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"))
            self.storage.add_video(Video("2", "Elephants Dream", "Blender", datetime(2023, 1, 2), "http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ElephantsDream.mp4"))
            self.storage.add_video(Video("3", "Tears of Steel", "Blender", datetime(2023, 1, 3), "http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/TearsOfSteel.mp4"))
            # storage.save() is no-op now

    def mark_video_as_viewed(self, video: Optional[Video]) -> None:
        if video:
            video.viewed = True
            self.storage.update_video(video)

    def get_display_videos(self) -> List[Video]:
        if self.app_state.current_tab == "New":
            return self.storage.get_new_videos(100)
        elif self.app_state.current_tab == "Random":
            return self.storage.get_random_videos(100)
        elif self.app_state.current_tab == "Related":
            if self.app_state.last_played_video:
                return self.storage.get_related_videos(self.app_state.last_played_video.id, 100)
            return []
        return []

    def refresh_app_state(self) -> None:
        # Refresh display videos
        self.app_state.handle_event(Event.CACHE_LOADED, videos=self.get_display_videos())

        # Update next video cache
        # If we are launching a video, we should consider it as the "current" one to find what follows it
        current_id = None
        if self.app_state.now_playing:
            current_id = self.app_state.now_playing.id
        elif self.app_state.state == State.LAUNCHING and self.app_state.selected_video:
            current_id = self.app_state.selected_video.id

        self.app_state.next_video = self.storage.select_next_video(
                                                current_id=current_id,
                                                last_id=self.app_state.last_played_video.id if self.app_state.last_played_video else None)

    def update_background_status(self) -> None:
        if self.app_state.state == State.PLAYING:
            exit_code = self.player.poll_exit_code()
            if exit_code is not None:
                self.mark_video_as_viewed(self.app_state.now_playing)

                if exit_code == MPV_EXIT_CODE_NEXT:
                    self.app_state.handle_event(Event.MPV_EXITED)
                    if self.app_state.next_video:
                        self.app_state.handle_event(Event.NEXT, video=self.app_state.next_video)
                else:
                    self.app_state.handle_event(Event.MPV_EXITED)

                # Refresh display videos to show viewed status
                self.refresh_app_state()

        if self.app_state.state == State.UPDATING:
            if self.app_state.busy_until and datetime.now() >= self.app_state.busy_until:
                self.app_state.handle_event(Event.UPDATE_SUCCEEDED, added_count=0)
                self.app_state.busy_until = None
                # Refresh current display after update
                self.refresh_app_state()

    def handle_state_actions(self) -> None:
        if self.app_state.state == State.LAUNCHING:
            video = self.app_state.selected_video
            if video:
                try:
                    pid = self.player.play(video)
                    self.app_state.handle_event(Event.MPV_SPAWNED, pid=pid, video=video)
                    # Refresh state to update next_video after now_playing is set
                    self.refresh_app_state()
                except Exception as e:
                    self.app_state.handle_event(Event.MPV_SPAWN_FAILED, error=str(e))
            else:
                self.app_state.handle_event(Event.MPV_SPAWN_FAILED, error="Video not found")

    def _mark_and_transition(self, event: Event, **kwargs: Any) -> None:
        """
        現在の動画を視聴済みとしてマークし、イベントを発行し、状態をリフレッシュする共通パターン。
        """
        self.mark_video_as_viewed(self.app_state.now_playing)
        self.app_state.handle_event(event, **kwargs)
        self.refresh_app_state()

    def handle_input(self) -> bool:
        running = True
        try:
            key = self.stdscr.getch()
        except:
            key = -1

        if key == -1:
            return running

        if key == ord('q'):
            self.player.stop()
            running = False
        elif key == ord('h'):
            self.app_state.handle_event(Event.HELP_TOGGLE)
        elif key == ord('j') or key == curses.KEY_DOWN:
            self.app_state.handle_event(Event.CURSOR_DOWN)
        elif key == ord('k') or key == curses.KEY_UP:
            self.app_state.handle_event(Event.CURSOR_UP)
        elif key == ord('\t'):
            self.app_state.handle_event(Event.TAB_NEXT)
            self.refresh_app_state()
        elif key == ord('\n') or key == curses.KEY_ENTER:
            videos = self.app_state.get_filtered_videos()
            if 0 <= self.app_state.selected_idx < len(videos):
                video = videos[self.app_state.selected_idx]
                self._mark_and_transition(Event.PLAY_SELECTED, video=video)
        elif key == ord('n'):
            if self.app_state.next_video:
                self._mark_and_transition(Event.NEXT, video=self.app_state.next_video)
            else:
                self._mark_and_transition(Event.NEXT) # Handle no next video if needed
        elif key == ord('s'):
            self.player.stop()
            self._mark_and_transition(Event.STOP)
        elif key == ord('b'):
            self.app_state.handle_event(Event.BACK_TO_UI)
            self.refresh_app_state()
        elif key == ord('u'):
            if self.app_state.state != State.UPDATING:
                self.app_state.handle_event(Event.UPDATE)
                self.app_state.busy_until = datetime.now() + timedelta(seconds=1)
        elif key == ord('r'):
            self.app_state.handle_event(Event.RANDOM_REFRESH)
            self.refresh_app_state()

        return running


def main(stdscr: Any) -> None:
    app = VideoPlayerApp(stdscr)
    app.initialize_data()
    app.refresh_app_state()

    stdscr.nodelay(True)
    running = True

    while running:
        app.update_background_status()
        app.ui.render(app.app_state)
        running = app.handle_input()
        app.handle_state_actions()
        time.sleep(0.05)

def run() -> None:
    curses.wrapper(main)

if __name__ == "__main__":
    run()
