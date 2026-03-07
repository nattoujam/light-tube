from enum import Enum, auto

class Event(Enum):
    # UI Input Events
    PLAY_SELECTED = auto()
    NEXT = auto()
    STOP = auto()
    BACK_TO_UI = auto()
    UPDATE = auto()
    CURSOR_UP = auto()
    CURSOR_DOWN = auto()
    CURSOR_LEFT = auto()
    CURSOR_RIGHT = auto()
    HELP_TOGGLE = auto()
    REGISTER_CHANNEL = auto()
    DELETE_CHANNEL = auto()
    HISTORY_UPDATE = auto()
    QUIT = auto()

    # Internal Events
    CACHE_LOADED = auto()
    REGISTRATION_SUCCEEDED = auto()
    REGISTRATION_FAILED = auto()
    UPDATE_STARTED = auto()
    UPDATE_SUCCEEDED = auto()
    UPDATE_FAILED = auto()

    # mpv Events
    MPV_SPAWNED = auto()
    MPV_SPAWN_FAILED = auto()
    MPV_EXITED = auto()
