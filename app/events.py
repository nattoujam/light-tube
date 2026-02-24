from enum import Enum, auto

class Event(Enum):
    # UI Input Events
    PLAY_SELECTED = auto()
    NEXT = auto()
    STOP = auto()
    BACK_TO_UI = auto()
    UPDATE = auto()
    RANDOM_REFRESH = auto()
    TAB_NEXT = auto()
    TAB_PREV = auto()
    HELP_TOGGLE = auto()
    QUIT = auto()

    # Internal Events
    CACHE_LOADED = auto()
    UPDATE_STARTED = auto()
    UPDATE_SUCCEEDED = auto()
    UPDATE_FAILED = auto()

    # mpv Events
    MPV_SPAWNED = auto()
    MPV_SPAWN_FAILED = auto()
    MPV_EXITED = auto()
