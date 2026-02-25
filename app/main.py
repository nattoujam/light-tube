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

def initialize_data(storage: VideoStorage) -> None:
    # Use compat property 'videos' or just check if any record exists
    if not storage.get_new_videos(1):
        storage.add_video(Video("1", "Big Buck Bunny", "Blender", datetime(2023, 1, 1), "http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"))
        storage.add_video(Video("2", "Elephants Dream", "Blender", datetime(2023, 1, 2), "http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ElephantsDream.mp4"))
        storage.add_video(Video("3", "Tears of Steel", "Blender", datetime(2023, 1, 3), "http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/TearsOfSteel.mp4"))
        # storage.save() is no-op now

def get_display_videos(storage: VideoStorage, app_state: AppState) -> List[Video]:
    if app_state.current_tab == "New":
        return storage.get_new_videos(100)
    elif app_state.current_tab == "Random":
        return storage.get_random_videos(100)
    elif app_state.current_tab == "Related":
        if app_state.last_played_video_id:
            return storage.get_related_videos(app_state.last_played_video_id, 100)
        return []
    return []

def update_background_status(app_state: AppState, player: MpvPlayer, storage: VideoStorage, update_finish_time: Optional[datetime]) -> Optional[datetime]:
    if app_state.state == State.PLAYING:
        exit_code = player.poll_exit_code()
        if exit_code is not None:
            if app_state.now_playing:
                app_state.now_playing.viewed = True
                storage.update_video(app_state.now_playing)

            if exit_code == MPV_EXIT_CODE_NEXT:
                next_video = select_next_video(storage,
                                               current_video_id=app_state.now_playing.id if app_state.now_playing else None,
                                               last_video_id=app_state.last_played_video_id)
                app_state.handle_event(Event.MPV_EXITED)
                if next_video:
                    app_state.handle_event(Event.NEXT, video_id=next_video.id)
            else:
                app_state.handle_event(Event.MPV_EXITED)

            # Refresh display videos to show viewed status
            app_state.handle_event(Event.CACHE_LOADED, videos=get_display_videos(storage, app_state))

    if app_state.state == State.UPDATING:
        if update_finish_time and datetime.now() >= update_finish_time:
            app_state.handle_event(Event.UPDATE_SUCCEEDED, added_count=0)
            # Refresh current display after update
            app_state.handle_event(Event.CACHE_LOADED, videos=get_display_videos(storage, app_state))
            return None
    return update_finish_time

def handle_input(stdscr: Any, app_state: AppState, player: MpvPlayer, storage: VideoStorage, ui: Tui, show_help: bool, update_finish_time: Optional[datetime]) -> tuple[bool, bool, Optional[datetime]]:
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
        app_state.handle_event(Event.CACHE_LOADED, videos=get_display_videos(storage, app_state))
    elif key == ord('\n') or key == curses.KEY_ENTER:
        videos = app_state.get_filtered_videos()
        if 0 <= ui.selected_idx < len(videos):
            if app_state.state == State.PLAYING and app_state.now_playing:
                app_state.now_playing.viewed = True
                storage.update_video(app_state.now_playing)

            video = videos[ui.selected_idx]
            app_state.handle_event(Event.PLAY_SELECTED, video_id=video.id)
            app_state.handle_event(Event.CACHE_LOADED, videos=get_display_videos(storage, app_state))
    elif key == ord('n'):
        if app_state.state == State.PLAYING and app_state.now_playing:
            app_state.now_playing.viewed = True
            storage.update_video(app_state.now_playing)

        next_video = select_next_video(storage,
                                       current_video_id=app_state.now_playing.id if app_state.now_playing else None,
                                       last_video_id=app_state.last_played_video_id)
        if next_video:
            app_state.handle_event(Event.NEXT, video_id=next_video.id)
            app_state.handle_event(Event.CACHE_LOADED, videos=get_display_videos(storage, app_state))
    elif key == ord('s'):
        if app_state.state == State.PLAYING and app_state.now_playing:
            app_state.now_playing.viewed = True
            storage.update_video(app_state.now_playing)

        player.stop()
        app_state.handle_event(Event.STOP)
        # Refresh display in case "Related" tab needs update after play
        app_state.handle_event(Event.CACHE_LOADED, videos=get_display_videos(storage, app_state))
    elif key == ord('b'):
        app_state.handle_event(Event.BACK_TO_UI)
        app_state.handle_event(Event.CACHE_LOADED, videos=get_display_videos(storage, app_state))
    elif key == ord('u'):
        if app_state.state != State.UPDATING:
            app_state.handle_event(Event.UPDATE)
            update_finish_time = datetime.now() + timedelta(seconds=1)
    elif key == ord('r'):
        app_state.handle_event(Event.RANDOM_REFRESH)
        if app_state.current_tab == "Random":
            ui.selected_idx = 0
            app_state.handle_event(Event.CACHE_LOADED, videos=get_display_videos(storage, app_state))

    return running, show_help, update_finish_time

def handle_state_actions(app_state: AppState, player: MpvPlayer, storage: VideoStorage) -> None:
    if app_state.state == State.LAUNCHING:
        video = storage.get_video_by_id(app_state.selected_video_id)
        if video:
            try:
                pid = player.play(video)
                app_state.handle_event(Event.MPV_SPAWNED, pid=pid, video=video)
            except Exception as e:
                app_state.handle_event(Event.MPV_SPAWN_FAILED, error=str(e))
        else:
            app_state.handle_event(Event.MPV_SPAWN_FAILED, error="Video not found")

def main(stdscr: Any) -> None:
    # Setup
    storage = VideoStorage('videos.db')
    initialize_data(storage)

    app_state = AppState()
    # Initial load
    app_state.handle_event(Event.CACHE_LOADED, videos=get_display_videos(storage, app_state))

    player = MpvPlayer()
    ui = Tui(stdscr)
    stdscr.nodelay(True)

    show_help = False
    running = True
    update_finish_time = None

    while running:
        update_finish_time = update_background_status(app_state, player, storage, update_finish_time)
        ui.render(app_state, storage, show_help)
        running, show_help, update_finish_time = handle_input(stdscr, app_state, player, storage, ui, show_help, update_finish_time)
        handle_state_actions(app_state, player, storage)
        time.sleep(0.05)

def run() -> None:
    curses.wrapper(main)

if __name__ == "__main__":
    run()
