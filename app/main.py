import curses
import time
from datetime import datetime, timedelta
from typing import Optional, Any, List
from .state import AppState, State
from .events import Event
from .models import Video, Channel
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
            # Create a dummy channel for initial data
            channel_id = self.storage.save_channel("sample", "Blender", "blender_id")
            channel = Channel(id=channel_id, platform="sample", name="Blender", external_id="blender_id", created_at=datetime.now())

            self.storage.add_video(Video("1", "Big Buck Bunny", channel, datetime(2023, 1, 1), "http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4", platform="sample", channel_id=channel_id))
            self.storage.add_video(Video("2", "Elephants Dream", channel, datetime(2023, 1, 2), "http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ElephantsDream.mp4", platform="sample", channel_id=channel_id))
            self.storage.add_video(Video("3", "Tears of Steel", channel, datetime(2023, 1, 3), "http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/TearsOfSteel.mp4", platform="sample", channel_id=channel_id))

    def mark_video_as_viewed(self, video: Optional[Video]) -> None:
        if video:
            video.viewed = True
            self.storage.update_video(video)

    def get_display_videos(self) -> List[Video]:
        # Based on sidebar selection
        channel = self.app_state.highlighted_channel
        if channel:
            # Newest videos from this channel
            return self.storage._fetch_all_videos_by_channel(channel.id, 100)
        else:
            # "All Videos" -> Newest 100 videos
            return self.storage.get_new_videos(100)

    def _get_active_video_id(self) -> Optional[str]:
        if self.app_state.now_playing:
            return self.app_state.now_playing.id
        elif self.app_state.state == State.LAUNCHING and self.app_state.selected_video:
            return self.app_state.selected_video.id
        return None

    def refresh_app_state(self) -> None:
        # Refresh display videos and channels
        videos = self.get_display_videos()
        channels = self.storage.get_channels()
        self.app_state.handle_event(Event.CACHE_LOADED, videos=videos, channels=channels)

        # Update next video cache
        current_id = self._get_active_video_id()

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
        return self.app_state.highlighted_video

    def _get_selected_channel(self) -> Optional[Channel]:
        return self.app_state.highlighted_channel

    def _sync_channel_videos(self, channel: Channel, fetch_type: str = "recent", **kwargs: Any) -> int:
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

        return self.repository.save_remote_videos(channel, rvs)

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
            # Step 1: Platform selection (Single key)
            self.stdscr.nodelay(False)
            key = self.stdscr.getch()
            self.stdscr.nodelay(True)

            if key == ord('b') or key == 27: # 'b' or ESC
                self.app_state.handle_event(Event.BACK_TO_UI)
                return

            # For now, only 'y' (YouTube) is supported
            if key != ord('y'):
                self.app_state.handle_event(Event.BACK_TO_UI)
                return

            platform_name = "youtube"
            self.ui.render(self.app_state)

            # Step 2: Channel Name input
            channel_name = self.ui.get_input_string("  入力: ", self.ui.height // 2 + 1, self.ui.width // 2 - 20)

            if channel_name:
                self.app_state.handle_event(Event.UPDATE_STARTED)
                self.ui.render(self.app_state)

                external_id = self.channel_resolver.resolve(platform_name, channel_name)
                channel_id = self.repository.save_channel(platform_name, channel_name, external_id)

                # Use Channel model for sync_channel_videos
                channel = Channel(
                    id=channel_id,
                    platform=platform_name,
                    name=channel_name,
                    external_id=external_id,
                    created_at=datetime.now()
                )
                self._sync_channel_videos(channel, fetch_type="recent", limit=50)

                self.app_state.handle_event(Event.REGISTRATION_SUCCEEDED)
                self.refresh_app_state()
            else:
                self.app_state.handle_event(Event.BACK_TO_UI)
        except Exception as e:
            self.app_state.handle_event(Event.REGISTRATION_FAILED, error=str(e))

    def _on_key_help(self) -> None:
        self.app_state.handle_event(Event.HELP_TOGGLE)

    def _on_key_down(self) -> None:
        from .state import FocusArea
        self.app_state.handle_event(Event.CURSOR_DOWN)
        if self.app_state.focus_area == FocusArea.SIDEBAR:
            self.refresh_app_state()

    def _on_key_up(self) -> None:
        from .state import FocusArea
        self.app_state.handle_event(Event.CURSOR_UP)
        if self.app_state.focus_area == FocusArea.SIDEBAR:
            self.refresh_app_state()

    def _on_key_left(self) -> None:
        self.app_state.handle_event(Event.CURSOR_LEFT)

    def _on_key_right(self) -> None:
        from .state import FocusArea
        if self.app_state.focus_area == FocusArea.SIDEBAR:
            self.app_state.handle_event(Event.CURSOR_RIGHT)
            self.app_state.selected_idx = 0
            self.refresh_app_state()

    def _on_key_tab(self) -> None:
        from .state import FocusArea
        # We can keep tab for cycling or remove it
        is_switching_to_main = self.app_state.focus_area == FocusArea.SIDEBAR
        self.app_state.handle_event(Event.TAB_NEXT)
        if is_switching_to_main:
            self.app_state.selected_idx = 0
        self.refresh_app_state()

    def _on_key_play(self) -> None:
        from .state import FocusArea
        if self.app_state.focus_area == FocusArea.SIDEBAR:
            # Switch to main area
            self.app_state.handle_event(Event.CURSOR_RIGHT)
            self.app_state.selected_idx = 0
            self.refresh_app_state()
            return

        video = self._get_selected_video()
        if video:
            self._mark_and_transition(Event.PLAY_SELECTED, video=video)

    def _on_key_next(self) -> None:
        if self.app_state.current_tab == "Channels":
            return
        if self.app_state.next_video:
            self._mark_and_transition(Event.NEXT, video=self.app_state.next_video)
        else:
            self._mark_and_transition(Event.NEXT)

    def _on_key_stop(self) -> None:
        self.player.stop()
        self._mark_and_transition(Event.STOP)

    def _on_key_back(self) -> None:
        self.app_state.handle_event(Event.BACK_TO_UI)
        self.refresh_app_state()

    def _on_key_update(self) -> None:
        if self.app_state.state != State.UPDATING:
            self.app_state.handle_event(Event.UPDATE)
            self.app_state.busy_until = datetime.now() + timedelta(milliseconds=100)

    def _on_key_history(self) -> None:
        video = self._get_selected_video()
        if video:
            self._handle_history_update(video)

    def _on_key_add(self) -> None:
        from .state import FocusArea
        if self.app_state.focus_area != FocusArea.SIDEBAR:
            return
        if self.app_state.state != State.REGISTER:
            self.app_state.handle_event(Event.REGISTER_CHANNEL)
            self.app_state.error_message = None
            self._run_registration_flow()

    def _on_key_delete(self) -> None:
        from .state import FocusArea
        if self.app_state.focus_area != FocusArea.SIDEBAR:
            return
        if self.app_state.sidebar_idx == 0: # "All Videos" cannot be deleted
            return
        self.app_state.handle_event(Event.DELETE_CHANNEL)

    def _on_key_random(self) -> None:
        self.app_state.handle_event(Event.RANDOM_REFRESH)
        self.refresh_app_state()

    def handle_input(self) -> bool:
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
            return True

        if any(k == ord('q') for k in keys):
            self.player.stop()
            return False

        key = keys[-1]

        # Handle keys specifically for confirmation state
        if self.app_state.state == State.CONFIRM_DELETE:
            if key == ord('y'):
                channel = self._get_selected_channel()
                if channel:
                    self.storage.delete_channel(channel.id)
                    self.refresh_app_state()
                self.app_state.handle_event(Event.BACK_TO_UI)
                return True
            elif key == ord('n') or key == ord('b'):
                self.app_state.handle_event(Event.BACK_TO_UI)
                return True
            return True

        # Dispatcher map for key actions
        action_map = {
            ord('?'): self._on_key_help,
            ord('j'): self._on_key_down,
            curses.KEY_DOWN: self._on_key_down,
            ord('k'): self._on_key_up,
            curses.KEY_UP: self._on_key_up,
            ord('h'): self._on_key_left,
            curses.KEY_LEFT: self._on_key_left,
            ord('l'): self._on_key_right,
            curses.KEY_RIGHT: self._on_key_right,
            ord('\t'): self._on_key_tab,
            ord('\n'): self._on_key_play,
            curses.KEY_ENTER: self._on_key_play,
            ord('n'): self._on_key_next,
            ord('s'): self._on_key_stop,
            ord('b'): self._on_key_back,
            ord('u'): self._on_key_update,
            ord('i'): self._on_key_history,
            ord('a'): self._on_key_add,
            ord('d'): self._on_key_delete,
            ord('r'): self._on_key_random,
        }

        handler = action_map.get(key)
        if handler:
            handler()

        return True

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
