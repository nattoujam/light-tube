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

def update_background_status(app_state: AppState, player: MpvPlayer, storage: VideoStorage, update_finish_time: Optional[datetime], video_fetcher: VideoFetcher, repository: Repository) -> Optional[datetime]:
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
        # Note: In a real app, this should be in a separate thread.
        # But here we do it synchronously for simplicity in this prototype.
        # We only do it once when update_finish_time is set to something in the future.
        if update_finish_time and datetime.now() >= update_finish_time:
            from .ui import Tui # Avoid circular if any, though it's already imported at top
            # We want to make sure the "Updating" status is visible
            # In some cases we might need an explicit render here if we want to be sure
            added_total = 0
            channels = storage.get_channels()
            for channel in channels:
                try:
                    latest_date = repository.get_latest_video_date(channel.id)
                    # For "u" (Update Latest), we just fetch the newest 50.
                    # Duplicate prevention is handled by repository.save_remote_videos.
                    rvs = video_fetcher.fetch_recent(channel.platform, channel.external_id, limit=50)
                    added = repository.save_remote_videos(channel.id, channel.platform, channel.name, rvs)
                    added_total += added
                except Exception as e:
                    app_state.handle_event(Event.UPDATE_FAILED, error=str(e))
                    return None

            app_state.handle_event(Event.UPDATE_SUCCEEDED, added_count=added_total)
            refresh_app_state(app_state, storage)
            return None
    return update_finish_time

def handle_input(stdscr: Any, app_state: AppState, player: MpvPlayer, storage: VideoStorage, ui: Tui, show_help: bool, update_finish_time: Optional[datetime], video_fetcher: VideoFetcher, repository: Repository, channel_resolver: ChannelResolver) -> tuple[bool, bool, Optional[datetime]]:
    running = True
    try:
        key = stdscr.getch()
    except:
        key = -1

    if key == -1:
        return running, show_help, update_finish_time

    if key == ord('q'):
        player.stop()
        running = False
    elif key == ord('h'):
        show_help = not show_help
    elif key == ord('j') or key == curses.KEY_DOWN:
        videos = app_state.get_filtered_videos()
        if ui.selected_idx < len(videos) - 1:
            ui.selected_idx += 1
    elif key == ord('k') or key == curses.KEY_UP:
        if ui.selected_idx > 0:
            ui.selected_idx -= 1
    elif key == ord('\t'):
        app_state.handle_event(Event.TAB_NEXT)
        ui.selected_idx = 0
        refresh_app_state(app_state, storage)
    elif key == ord('\n') or key == curses.KEY_ENTER:
        videos = app_state.get_filtered_videos()
        if 0 <= ui.selected_idx < len(videos):
            mark_video_as_viewed(storage, app_state.now_playing)

            video = videos[ui.selected_idx]
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
            update_finish_time = datetime.now() + timedelta(milliseconds=100)
    elif key == ord('i'):
        # Update history for the current selected channel
        videos = app_state.get_filtered_videos()
        if 0 <= ui.selected_idx < len(videos):
            video = videos[ui.selected_idx]
            if video.channel_id:
                channel = storage.get_channel_by_id(video.channel_id)
                if channel:
                    app_state.handle_event(Event.HISTORY_UPDATE)
                    ui.render(app_state)
                    try:
                        oldest_date = repository.get_oldest_video_date(video.channel_id)
                        # Fetch videos published before the oldest one we have
                        # Use channel.external_id instead of video.video_id
                        rvs = video_fetcher.fetch_history(channel.platform, channel.external_id, published_before=oldest_date, limit=50)
                        added = repository.save_remote_videos(channel.id, channel.platform, channel.name, rvs)
                        app_state.handle_event(Event.UPDATE_SUCCEEDED, added_count=added)
                        refresh_app_state(app_state, storage)
                    except Exception as e:
                        app_state.handle_event(Event.UPDATE_FAILED, error=str(e))
    elif key == ord('a'):
        if app_state.state != State.REGISTER:
            app_state.handle_event(Event.REGISTER)
            # Handle registration synchronously for now
            ui.render(app_state) # Show registration box

            try:
                platform_key = ui.get_input_string("  入力: ", ui.height // 2 - 1, ui.width // 2 - 20)
                platform_name = "youtube" if platform_key == "y" else "niconico"
                channel_name = ui.get_input_string("  入力: ", ui.height // 2 + 2, ui.width // 2 - 20)

                if channel_name:
                    app_state.handle_event(Event.UPDATE_STARTED)
                    ui.render(app_state) # Show loading

                    external_id = channel_resolver.resolve(platform_name, channel_name)
                    channel_id = repository.save_channel(platform_name, channel_name, external_id)

                    # Initial fetch
                    rvs = video_fetcher.fetch_recent(platform_name, external_id, limit=50)
                    repository.save_remote_videos(channel_id, platform_name, channel_name, rvs)

                    app_state.handle_event(Event.REGISTRATION_SUCCEEDED)
                    refresh_app_state(app_state, storage)
                else:
                    app_state.handle_event(Event.BACK_TO_UI)
            except Exception as e:
                app_state.handle_event(Event.REGISTRATION_FAILED, error=str(e))
    elif key == ord('r'):
        app_state.handle_event(Event.RANDOM_REFRESH)
        if app_state.current_tab == "Random":
            ui.selected_idx = 0
            refresh_app_state(app_state, storage)

    return running, show_help, update_finish_time

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

    show_help = False
    running = True
    update_finish_time = None

    while running:
        update_finish_time = update_background_status(app_state, player, storage, update_finish_time, video_fetcher, repository)
        ui.render(app_state, show_help)
        running, show_help, update_finish_time = handle_input(stdscr, app_state, player, storage, ui, show_help, update_finish_time, video_fetcher, repository, channel_resolver)
        handle_state_actions(app_state, player, storage)
        time.sleep(0.05)

def run() -> None:
    curses.wrapper(main)

if __name__ == "__main__":
    run()
