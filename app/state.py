from enum import Enum, auto
from dataclasses import dataclass
from typing import Optional
from .models import Video

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
    selected_video_id: Optional[str] = None
    now_playing: Optional[Video] = None
    mpv_pid: Optional[int] = None
    last_played_video_id: Optional[str] = None
    update_status: Optional[str] = None
    error_message: Optional[str] = None
