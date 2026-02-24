import curses
import time
from datetime import datetime, timedelta
from .state import AppState, State
from .events import Event
from .models import Video
from .storage import VideoStorage
from .player import MpvPlayer
from .ui import Tui
from .next_logic import select_next_video

def main(stdscr):
    # Setup
    storage = VideoStorage('videos.json')
    if not storage.videos:
        storage.add_video(Video("1", "Big Buck Bunny", "Blender", datetime(2023, 1, 1), "http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"))
        storage.add_video(Video("2", "Elephants Dream", "Blender", datetime(2023, 1, 2), "http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ElephantsDream.mp4"))
        storage.add_video(Video("3", "Tears of Steel", "Blender", datetime(2023, 1, 3), "http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/TearsOfSteel.mp4"))
        storage.save()

    app_state = AppState()
    app_state.handle_event(Event.CACHE_LOADED, videos=storage.videos)

    player = MpvPlayer()
    ui = Tui(stdscr)
    stdscr.nodelay(True)

    show_help = False
    running = True
    update_finish_time = None

    while running:
        # 1. Update background status
        if app_state.state == State.PLAYING:
            exit_code = player.poll_exit_code()
            if exit_code is not None:
                if app_state.now_playing:
                    app_state.now_playing.viewed = True
                    storage.update_video(app_state.now_playing)
                    storage.save()
                app_state.handle_event(Event.MPV_EXITED)

        if app_state.state == State.UPDATING:
            if update_finish_time and datetime.now() >= update_finish_time:
                app_state.handle_event(Event.UPDATE_SUCCEEDED, added_count=0)
                update_finish_time = None

        # 2. Render UI
        ui.render(app_state, show_help)

        # 3. Handle Input
        try:
            key = stdscr.getch()
        except:
            key = -1

        if key != -1:
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
            elif key == ord('\n') or key == curses.KEY_ENTER:
                videos = app_state.get_filtered_videos()
                if 0 <= ui.selected_idx < len(videos):
                    video = videos[ui.selected_idx]
                    app_state.handle_event(Event.PLAY_SELECTED, video_id=video.id)
            elif key == ord('n'):
                next_video = select_next_video(app_state.videos,
                                               current_video_id=app_state.now_playing.id if app_state.now_playing else None,
                                               last_video_id=app_state.last_played_video_id)
                if next_video:
                    app_state.handle_event(Event.NEXT, video_id=next_video.id)
            elif key == ord('s'):
                player.stop()
                app_state.handle_event(Event.STOP)
            elif key == ord('b'):
                app_state.handle_event(Event.BACK_TO_UI)
            elif key == ord('u'):
                if app_state.state != State.UPDATING:
                    app_state.handle_event(Event.UPDATE)
                    update_finish_time = datetime.now() + timedelta(seconds=1)
            elif key == ord('r'):
                app_state.handle_event(Event.RANDOM_REFRESH)
                if app_state.current_tab == "Random":
                    ui.selected_idx = 0

        # 4. Handle State-driven Actions
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

        time.sleep(0.05)

def run():
    curses.wrapper(main)

if __name__ == "__main__":
    run()
