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
from .next_logic import select_next_video
from core.video_fetcher import VideoFetcher, PlatformFactory, ChannelResolver
from core.repository import Repository

def initialize_data(storage: VideoStorage) -> None:
    # Use compat property 'videos' or just check if any record exists
    if not storage.get_new_videos(1):
        storage.add_video(Video("1", "Big Buck Bunny", "Blender", datetime(2023, 1, 1), "http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"))
        storage.add_video(Video("2", "Elephants Dream", "Blender", datetime(2023, 1, 2), "http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ElephantsDream.mp4"))
        storage.add_video(Video("3", "Tears of Steel", "Blender", datetime(2023, 1, 3), "http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/TearsOfSteel.mp4"))
        # storage.save() is no-op now

def mark_video_as_viewed(storage: VideoStorage, video: Optional[Video]) -> None:
    if video:
        video.viewed = True
        storage.update_video(video)

def refresh_app_state(app_state: AppState, storage: VideoStorage) -> None:
    # Refresh display videos
    app_state.handle_event(Event.CACHE_LOADED, videos=get_display_videos(storage, app_state))

    # Update next video cache
    # If we are launching a video, we should consider it as the "current" one to find what follows it
    current_id = None
    if app_state.now_playing:
        current_id = app_state.now_playing.id
    elif app_state.state == State.LAUNCHING and app_state.selected_video:
        current_id = app_state.selected_video.id

    app_state.next_video = select_next_video(storage,
                                            current_video_id=current_id,
                                            last_video_id=app_state.last_played_video.id if app_state.last_played_video else None)

def get_display_videos(storage: VideoStorage, app_state: AppState) -> List[Video]:
    if app_state.current_tab == "New":
        return storage.get_new_videos(100)
    elif app_state.current_tab == "Random":
        return storage.get_random_videos(100)
    elif app_state.current_tab == "Related":
        if app_state.last_played_video:
            return storage.get_related_videos(app_state.last_played_video.id, 100)
        return []
    return []

def update_background_status(app_state: AppState, player: MpvPlayer, storage: VideoStorage) -> None:
    if app_state.state == State.PLAYING:
        exit_code = player.poll_exit_code()
        if exit_code is not None:
            mark_video_as_viewed(storage, app_state.now_playing)

            if exit_code == MPV_EXIT_CODE_NEXT:
                app_state.handle_event(Event.MPV_EXITED)
                if app_state.next_video:
                    app_state.handle_event(Event.NEXT, video=app_state.next_video)
            else:
                app_state.handle_event(Event.MPV_EXITED)

            # Refresh display videos to show viewed status
            refresh_app_state(app_state, storage)

    if app_state.state == State.UPDATING:
        if app_state.busy_until and datetime.now() >= app_state.busy_until:
            app_state.handle_event(Event.UPDATE_SUCCEEDED, added_count=0)
            app_state.busy_until = None
            # Refresh current display after update
            refresh_app_state(app_state, storage)

def handle_input(stdscr: Any, app_state: AppState, player: MpvPlayer, storage: VideoStorage) -> bool:
    running = True

    if key == -1:
        return running

    if key == ord('q'):
        player.stop()
        running = False
    elif key == ord('h'):
        app_state.handle_event(Event.HELP_TOGGLE)
    elif key == ord('j') or key == curses.KEY_DOWN:
        app_state.handle_event(Event.CURSOR_DOWN)
    elif key == ord('k') or key == curses.KEY_UP:
        app_state.handle_event(Event.CURSOR_UP)
    elif key == ord('\t'):
        app_state.handle_event(Event.TAB_NEXT)
        refresh_app_state(app_state, storage)
    elif key == ord('\n') or key == curses.KEY_ENTER:
        videos = app_state.get_filtered_videos()
        if 0 <= app_state.selected_idx < len(videos):
            mark_video_as_viewed(storage, app_state.now_playing)
            video = videos[app_state.selected_idx]
            app_state.handle_event(Event.PLAY_SELECTED, video=video)
            refresh_app_state(app_state, storage)
    elif key == ord('n'):
        mark_video_as_viewed(storage, app_state.now_playing)
        if app_state.next_video:
            app_state.handle_event(Event.NEXT, video=app_state.next_video)
        refresh_app_state(app_state, storage)
    elif key == ord('s'):
        mark_video_as_viewed(storage, app_state.now_playing)
        player.stop()
        app_state.handle_event(Event.STOP)
        refresh_app_state(app_state, storage)
    elif key == ord('b'):
        app_state.handle_event(Event.BACK_TO_UI)
        refresh_app_state(app_state, storage)
    elif key == ord('u'):
        if app_state.state != State.UPDATING:
            app_state.handle_event(Event.UPDATE)
            app_state.busy_until = datetime.now() + timedelta(seconds=1)
    elif key == ord('r'):
        app_state.handle_event(Event.RANDOM_REFRESH)
        refresh_app_state(app_state, storage)

    return running

def handle_state_actions(app_state: AppState, player: MpvPlayer, storage: VideoStorage) -> None:
    if app_state.state == State.LAUNCHING:
        video = app_state.selected_video
        if video:
            try:
                pid = player.play(video)
                app_state.handle_event(Event.MPV_SPAWNED, pid=pid, video=video)
                # Refresh state to update next_video after now_playing is set
                refresh_app_state(app_state, storage)
            except Exception as e:
                app_state.handle_event(Event.MPV_SPAWN_FAILED, error=str(e))
        else:
            app_state.handle_event(Event.MPV_SPAWN_FAILED, error="Video not found")

def main(stdscr: Any) -> None:
    # Setup
    if curses.has_colors():
        curses.start_color()
        curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)

    storage = VideoStorage('videos.db')
    initialize_data(storage)

    factory = PlatformFactory('config.yml')
    video_fetcher = VideoFetcher(factory)
    repository = Repository(storage)
    channel_resolver = ChannelResolver(factory)

    app_state = AppState()
    # Initial load
    refresh_app_state(app_state, storage)

    player = MpvPlayer()
    ui = Tui(stdscr)
    stdscr.nodelay(True)

    running = True

    while running:
        update_background_status(app_state, player, storage)
        ui.render(app_state)
        running = handle_input(stdscr, app_state, player, storage)
        handle_state_actions(app_state, player, storage)
        time.sleep(0.05)

def run() -> None:
    curses.wrapper(main)

if __name__ == "__main__":
    run()
