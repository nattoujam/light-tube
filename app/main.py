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
from core.video_fetcher import VideoFetcher, PlatformFactory, ChannelResolver
from core.repository import Repository

class VideoPlayerApp:
    def __init__(self, stdscr: Any):
        self.storage = VideoStorage('videos.db')
        self.app_state = AppState()
        self.player = MpvPlayer()
        self.ui = Tui(stdscr)
        self.stdscr = stdscr

        # New components from upstream
        self.factory = PlatformFactory('config.yml')
        self.video_fetcher = VideoFetcher(self.factory)
        self.repository = Repository(self.storage)
        self.channel_resolver = ChannelResolver(self.factory)

    def initialize_data(self) -> None:
        # Use compat property 'videos' or just check if any record exists
        if not self.storage.get_new_videos(1):
            self.storage.add_video(Video("1", "Big Buck Bunny", "Blender", datetime(2023, 1, 1), "http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"))
            self.storage.add_video(Video("2", "Elephants Dream", "Blender", datetime(2023, 1, 2), "http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ElephantsDream.mp4"))
            self.storage.add_video(Video("3", "Tears of Steel", "Blender", datetime(2023, 1, 3), "http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/TearsOfSteel.mp4"))

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
        current_id = None
        if self.app_state.now_playing:
            current_id = self.app_state.now_playing.id
        elif self.app_state.state == State.LAUNCHING and self.app_state.selected_video:
            current_id = self.app_state.selected_video.id

        self.app_state.next_video = self.storage.select_next_video(
                                                current_id=current_id,
                                                last_id=self.app_state.last_played_video.id if self.app_state.last_played_video else None)

    def _process_mpv_events(self) -> None:
        if self.app_state.state != State.PLAYING:
            return

        exit_code = self.player.poll_exit_code()
        if exit_code is not None:
            self.mark_video_as_viewed(self.app_state.now_playing)

            if exit_code == MPV_EXIT_CODE_NEXT:
                self.app_state.handle_event(Event.MPV_EXITED)
                if self.app_state.next_video:
                    self.app_state.handle_event(Event.NEXT, video=self.app_state.next_video)
            else:
                self.app_state.handle_event(Event.MPV_EXITED)

            self.refresh_app_state()

    def _process_background_updates(self) -> None:
        if self.app_state.state != State.UPDATING:
            return

        if self.app_state.busy_until and datetime.now() >= self.app_state.busy_until:
            added_total = 0
            channels = self.storage.get_channels()
            for channel in channels:
                try:
                    added = self._sync_channel_videos(channel, fetch_type="recent", limit=50)
                    added_total += added
                except Exception as e:
                    self.app_state.handle_event(Event.UPDATE_FAILED, error=str(e))
                    self.app_state.busy_until = None
                    return

            self.app_state.handle_event(Event.UPDATE_SUCCEEDED, added_count=added_total)
            self.app_state.busy_until = None
            self.refresh_app_state()

    def update_background_status(self) -> None:
        self._process_mpv_events()
        self._process_background_updates()

    def handle_state_actions(self) -> None:
        if self.app_state.state == State.LAUNCHING:
            video = self.app_state.selected_video
            if video:
                try:
                    pid = self.player.play(video)
                    self.app_state.handle_event(Event.MPV_SPAWNED, pid=pid, video=video)
                    self.refresh_app_state()
                except Exception as e:
                    self.app_state.handle_event(Event.MPV_SPAWN_FAILED, error=str(e))
            else:
                self.app_state.handle_event(Event.MPV_SPAWN_FAILED, error="Video not found")

    def _mark_and_transition(self, event: Event, **kwargs: Any) -> None:
        self.mark_video_as_viewed(self.app_state.now_playing)
        self.app_state.handle_event(event, **kwargs)
        self.refresh_app_state()

    def _get_selected_video(self) -> Optional[Video]:
        videos = self.app_state.get_filtered_videos()
        if 0 <= self.app_state.selected_idx < len(videos):
            return videos[self.app_state.selected_idx]
        return None

    def _sync_channel_videos(self, channel: Any, fetch_type: str = "recent", **kwargs: Any) -> int:
        """
        Fetch and save videos for a channel.
        fetch_type can be "recent" or "history".
        """
        if fetch_type == "recent":
            rvs = self.video_fetcher.fetch_recent(channel.platform, channel.external_id, limit=kwargs.get('limit', 50))
        elif fetch_type == "history":
            rvs = self.video_fetcher.fetch_history(channel.platform, channel.external_id,
                                                   published_before=kwargs.get('published_before'),
                                                   limit=kwargs.get('limit', 50))
        else:
            return 0

        return self.repository.save_remote_videos(channel.id, channel.platform, channel.name, rvs)

    def _handle_history_update(self, video: Video) -> None:
        if not video.channel_id:
            return

        channel = self.storage.get_channel_by_id(video.channel_id)
        if not channel:
            return

        self.app_state.handle_event(Event.HISTORY_UPDATE)
        self.ui.render(self.app_state)
        try:
            oldest_date = self.repository.get_oldest_video_date(video.channel_id)
            added = self._sync_channel_videos(channel, fetch_type="history", published_before=oldest_date, limit=50)
            self.app_state.handle_event(Event.UPDATE_SUCCEEDED, added_count=added)
            self.refresh_app_state()
        except Exception as e:
            self.app_state.handle_event(Event.UPDATE_FAILED, error=str(e))

    def _run_registration_flow(self) -> None:
        self.ui.render(self.app_state)
        try:
            platform_key = self.ui.get_input_string("  入力: ", self.ui.height // 2 - 2, self.ui.width // 2 - 20)
            if not platform_key:
                 self.app_state.handle_event(Event.BACK_TO_UI)
                 return

            platform_name = "youtube"
            self.ui.render(self.app_state)

            channel_name = self.ui.get_input_string("  入力: ", self.ui.height // 2 + 1, self.ui.width // 2 - 20)

            if channel_name:
                self.app_state.handle_event(Event.UPDATE_STARTED)
                self.ui.render(self.app_state)

                external_id = self.channel_resolver.resolve(platform_name, channel_name)
                channel_id = self.repository.save_channel(platform_name, channel_name, external_id)

                # Wrap it in a channel-like object for sync_channel_videos
                from dataclasses import dataclass
                @dataclass
                class DummyChannel:
                    id: int
                    platform: str
                    name: str
                    external_id: str

                dummy_channel = DummyChannel(channel_id, platform_name, channel_name, external_id)
                self._sync_channel_videos(dummy_channel, fetch_type="recent", limit=50)

                self.app_state.handle_event(Event.REGISTRATION_SUCCEEDED)
                self.refresh_app_state()
            else:
                self.app_state.handle_event(Event.BACK_TO_UI)
        except Exception as e:
            self.app_state.handle_event(Event.REGISTRATION_FAILED, error=str(e))

    def handle_input(self) -> bool:
        running = True
        keys = []
        while True:
            try:
                k = self.stdscr.getch()
                if k == -1:
                    break
                keys.append(k)
            except:
                break

        if not keys:
            return running

        if any(k == ord('q') for k in keys):
            self.player.stop()
            return False

        key = keys[-1]

        if key == ord('h'):
            self.app_state.handle_event(Event.HELP_TOGGLE)
        elif key == ord('j') or key == curses.KEY_DOWN:
            self.app_state.handle_event(Event.CURSOR_DOWN)
        elif key == ord('k') or key == curses.KEY_UP:
            self.app_state.handle_event(Event.CURSOR_UP)
        elif key == ord('\t'):
            self.app_state.handle_event(Event.TAB_NEXT)
            self.refresh_app_state()
        elif key == ord('\n') or key == curses.KEY_ENTER:
            video = self._get_selected_video()
            if video:
                self._mark_and_transition(Event.PLAY_SELECTED, video=video)
        elif key == ord('n'):
            if self.app_state.next_video:
                self._mark_and_transition(Event.NEXT, video=self.app_state.next_video)
            else:
                self._mark_and_transition(Event.NEXT)
        elif key == ord('s'):
            self.player.stop()
            self._mark_and_transition(Event.STOP)
        elif key == ord('b'):
            self.app_state.handle_event(Event.BACK_TO_UI)
            self.refresh_app_state()
        elif key == ord('u'):
            if self.app_state.state != State.UPDATING:
                self.app_state.handle_event(Event.UPDATE)
                self.app_state.busy_until = datetime.now() + timedelta(milliseconds=100)
        elif key == ord('i'):
            video = self._get_selected_video()
            if video:
                self._handle_history_update(video)
        elif key == ord('a'):
            if self.app_state.state != State.REGISTER:
                self.app_state.handle_event(Event.REGISTER)
                self.app_state.error_message = None

        if self.app_state.state == State.REGISTER:
            self._run_registration_flow()
        elif key == ord('r'):
            self.app_state.handle_event(Event.RANDOM_REFRESH)
            self.refresh_app_state()

        return running

def main(stdscr: Any) -> None:
    if curses.has_colors():
        curses.start_color()
        curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)

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
