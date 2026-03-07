from enum import Enum, auto
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Any
import random
from .models import Video, Channel
from .events import Event

class State(Enum):
    BOOT = auto()
    BROWSE = auto()
    LAUNCHING = auto()
    PLAYING = auto()
    AFTER_PLAY = auto()
    UPDATING = auto()
    REGISTER = auto()
    LOADING = auto()
    CONFIRM_DELETE = auto()
    ERROR = auto()

class FocusArea(Enum):
    SIDEBAR = auto()
    MAIN = auto()

@dataclass
class AppState:
    state: State = State.BOOT
    display_videos: List[Video] = field(default_factory=list)
    display_channels: List[Channel] = field(default_factory=list)
    selected_idx: int = 0
    sidebar_idx: int = 0
    focus_area: FocusArea = FocusArea.SIDEBAR
    selected_channel_id: Optional[int] = None # None means "All Videos"
    show_help: bool = False
    busy_until: Optional[datetime] = None
    selected_video: Optional[Video] = None
    next_video: Optional[Video] = None
    now_playing: Optional[Video] = None
    mpv_pid: Optional[int] = None
    last_played_video: Optional[Video] = None
    update_status: Optional[str] = None
    error_message: Optional[str] = None
    previous_state: Optional[State] = None
    registration_step: int = 0  # 0: platform, 1: channel name
    registration_buffer: str = ""
    registration_platform: str = ""

    @property
    def current_limit(self) -> int:
        if self.focus_area == FocusArea.SIDEBAR:
            return 1 + len(self.display_channels) # "All Videos" + Channels
        return len(self.display_videos)

    @property
    def highlighted_video(self) -> Optional[Video]:
        if self.focus_area == FocusArea.MAIN:
            if 0 <= self.selected_idx < len(self.display_videos):
                return self.display_videos[self.selected_idx]
        return None

    @property
    def highlighted_channel(self) -> Optional[Channel]:
        # idx 0 in sidebar is "All Videos"
        if self.sidebar_idx > 0:
            channel_idx = self.sidebar_idx - 1
            if 0 <= channel_idx < len(self.display_channels):
                return self.display_channels[channel_idx]
        return None

    def handle_event(self, event: Event, **kwargs: Any) -> None:
        if event == Event.QUIT:
            return

        if event == Event.HELP_TOGGLE:
            self.show_help = not self.show_help
            return

        if event == Event.CURSOR_UP:
            if self.focus_area == FocusArea.SIDEBAR:
                if self.sidebar_idx > 0:
                    self.sidebar_idx -= 1
            else:
                if self.selected_idx > 0:
                    self.selected_idx -= 1
            return

        if event == Event.CURSOR_DOWN:
            if self.focus_area == FocusArea.SIDEBAR:
                if self.sidebar_idx < self.current_limit - 1:
                    self.sidebar_idx += 1
            else:
                if self.selected_idx < self.current_limit - 1:
                    self.selected_idx += 1
            return

        if event == Event.CURSOR_RIGHT:
            if self.focus_area == FocusArea.SIDEBAR:
                self.focus_area = FocusArea.MAIN
                # Selection logic for which channel's videos to show will be in main.py
            return

        if event == Event.CURSOR_LEFT:
            if self.focus_area == FocusArea.MAIN:
                self.focus_area = FocusArea.SIDEBAR
            return

        if event == Event.CACHE_LOADED:
            self.display_videos = kwargs.get('videos', [])
            self.display_channels = kwargs.get('channels', [])
            # Adjust selected_idx if it's out of bounds
            self.selected_idx = max(0, min(self.selected_idx, self.current_limit - 1))

            if self.state == State.BOOT:
                self.state = State.BROWSE
            return

        if self.state == State.BOOT:
            pass # CACHE_LOADED handled above
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
        elif self.state == State.REGISTER:
            self._handle_register(event, **kwargs)
        elif self.state == State.LOADING:
            self._handle_loading(event, **kwargs)
        elif self.state == State.CONFIRM_DELETE:
            self._handle_confirm_delete(event, **kwargs)
        elif self.state == State.ERROR:
            self._handle_error(event, **kwargs)

    def _handle_browse(self, event: Event, **kwargs: Any) -> None:
        if event == Event.PLAY_SELECTED or event == Event.NEXT:
            video = kwargs.get('video')
            if video:
                self.selected_video = video
                self.state = State.LAUNCHING
        elif event == Event.UPDATE or event == Event.HISTORY_UPDATE:
            self.previous_state = self.state
            self.state = State.UPDATING
        elif event == Event.REGISTER_CHANNEL:
            self.previous_state = self.state
            self.state = State.REGISTER
        elif event == Event.DELETE_CHANNEL:
            if self.focus_area == FocusArea.SIDEBAR and self.sidebar_idx > 0:
                self.state = State.CONFIRM_DELETE

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
            self.last_played_video = self.now_playing
            self.now_playing = None
            self.mpv_pid = None
            self.state = State.AFTER_PLAY
        elif event == Event.STOP:
            self.state = State.AFTER_PLAY
        elif event == Event.PLAY_SELECTED or event == Event.NEXT:
            video = kwargs.get('video')
            if video:
                self.selected_video = video
                self.state = State.LAUNCHING
        elif event == Event.BACK_TO_UI:
            pass

    def _handle_after_play(self, event: Event, **kwargs: Any) -> None:
        if event == Event.PLAY_SELECTED or event == Event.NEXT:
            video = kwargs.get('video')
            if video:
                self.selected_video = video
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

    def _handle_register(self, event: Event, **kwargs: Any) -> None:
        if event == Event.UPDATE_STARTED:
            self.state = State.LOADING
        elif event == Event.BACK_TO_UI:
            self.state = State.BROWSE
            self.registration_step = 0
            self.registration_buffer = ""

    def _handle_loading(self, event: Event, **kwargs: Any) -> None:
        if event == Event.REGISTRATION_SUCCEEDED:
            self.update_status = "登録完了"
            self.state = State.BROWSE
            self.registration_step = 0
            self.registration_buffer = ""
        elif event == Event.REGISTRATION_FAILED:
            self.error_message = str(kwargs.get('error'))
            self.state = State.ERROR

    def _handle_confirm_delete(self, event: Event, **kwargs: Any) -> None:
        if event == Event.BACK_TO_UI:
            self.state = State.BROWSE

    def _handle_error(self, event: Event, **kwargs: Any) -> None:
        if event == Event.BACK_TO_UI:
            self.state = State.BROWSE

    def get_filtered_videos(self) -> List[Video]:
        # Now display_videos already contains the filtered list from DB
        return self.display_videos
