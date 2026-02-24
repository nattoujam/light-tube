from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional, List, Any
import random
from .models import Video
from .events import Event

class State(Enum):
    BOOT = auto()
    BROWSE = auto()
    LAUNCHING = auto()
    PLAYING = auto()
    AFTER_PLAY = auto()
    UPDATING = auto()
    ERROR = auto()

@dataclass
class AppState:
    state: State = State.BOOT
    current_tab: str = "New"
    videos: List[Video] = field(default_factory=list)
    selected_video_id: Optional[str] = None
    now_playing: Optional[Video] = None
    mpv_pid: Optional[int] = None
    last_played_video_id: Optional[str] = None
    update_status: Optional[str] = None
    error_message: Optional[str] = None
    previous_state: Optional[State] = None
    random_videos: List[Video] = field(default_factory=list)

    def handle_event(self, event: Event, **kwargs: Any) -> None:
        if event == Event.QUIT:
            return

        if self.state == State.BOOT:
            self._handle_boot(event, **kwargs)
        elif self.state == State.BROWSE:
            self._handle_browse(event, **kwargs)
        elif self.state == State.LAUNCHING:
            self._handle_launching(event, **kwargs)
        elif self.state == State.PLAYING:
            self._handle_playing(event, **kwargs)
        elif self.state == State.AFTER_PLAY:
            self._handle_after_play(event, **kwargs)
        elif self.state == State.UPDATING:
            self._handle_updating(event, **kwargs)
        elif self.state == State.ERROR:
            self._handle_error(event, **kwargs)

    def _handle_boot(self, event: Event, **kwargs: Any) -> None:
        if event == Event.CACHE_LOADED:
            self.videos = kwargs.get('videos', [])
            self.random_videos = list(self.videos)
            random.shuffle(self.random_videos)
            self.state = State.BROWSE

    def _handle_browse(self, event: Event, **kwargs: Any) -> None:
        if event == Event.PLAY_SELECTED or event == Event.NEXT:
            video_id = kwargs.get('video_id')
            if video_id:
                self.selected_video_id = video_id
                self.state = State.LAUNCHING
        elif event == Event.UPDATE:
            self.previous_state = self.state
            self.state = State.UPDATING
        elif event == Event.TAB_NEXT or event == Event.TAB_PREV:
            tabs = ["New", "Random", "Related"]
            idx = tabs.index(self.current_tab)
            if event == Event.TAB_NEXT:
                self.current_tab = tabs[(idx + 1) % len(tabs)]
            else:
                self.current_tab = tabs[(idx - 1) % len(tabs)]
        elif event == Event.RANDOM_REFRESH:
            self.random_videos = list(self.videos)
            random.shuffle(self.random_videos)

    def _handle_launching(self, event: Event, **kwargs: Any) -> None:
        if event == Event.MPV_SPAWNED:
            self.mpv_pid = kwargs.get('pid')
            self.now_playing = kwargs.get('video')
            self.state = State.PLAYING
        elif event == Event.MPV_SPAWN_FAILED:
            self.error_message = kwargs.get('error')
            self.state = State.ERROR

    def _handle_playing(self, event: Event, **kwargs: Any) -> None:
        if event == Event.MPV_EXITED:
            self.last_played_video_id = self.now_playing.id if self.now_playing else None
            self.now_playing = None
            self.mpv_pid = None
            self.state = State.AFTER_PLAY
        elif event == Event.STOP:
            self.state = State.AFTER_PLAY
        elif event == Event.PLAY_SELECTED or event == Event.NEXT:
            video_id = kwargs.get('video_id')
            if video_id:
                self.selected_video_id = video_id
                self.state = State.LAUNCHING
        elif event == Event.BACK_TO_UI:
            pass

    def _handle_after_play(self, event: Event, **kwargs: Any) -> None:
        if event == Event.PLAY_SELECTED or event == Event.NEXT:
            video_id = kwargs.get('video_id')
            if video_id:
                self.selected_video_id = video_id
                self.state = State.LAUNCHING
        elif event == Event.BACK_TO_UI:
            self.state = State.BROWSE

    def _handle_updating(self, event: Event, **kwargs: Any) -> None:
        if event == Event.UPDATE_SUCCEEDED:
            self.update_status = f"更新完了 +{kwargs.get('added_count', 0)}件"
            self.state = self.previous_state or State.BROWSE
        elif event == Event.UPDATE_FAILED:
            self.error_message = str(kwargs.get('error'))
            self.state = State.ERROR

    def _handle_error(self, event: Event, **kwargs: Any) -> None:
        if event == Event.BACK_TO_UI:
            self.state = State.BROWSE

    def get_filtered_videos(self) -> List[Video]:
        if self.current_tab == "New":
            return sorted(self.videos, key=lambda x: x.upload_date, reverse=True)
        elif self.current_tab == "Random":
            return self.random_videos
        elif self.current_tab == "Related":
            if not self.last_played_video_id:
                return []
            last_video = next((v for v in self.videos if v.id == self.last_played_video_id), None)
            if not last_video:
                return []
            from .next_logic import get_related_videos
            return get_related_videos(self.videos, last_video)
        return self.videos
