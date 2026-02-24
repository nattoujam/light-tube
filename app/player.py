import subprocess
import os
import signal
from typing import Optional
from .models import Video

MPV_EXIT_CODE_NEXT = 5

class MpvPlayer:
    def __init__(self):
        self.process: Optional[subprocess.Popen] = None

    def play(self, video: Video) -> int:
        """
        Launches mpv to play the video.
        If already playing, kills the previous process (Section 6: No multiple mpv).
        Returns the PID of the new process.
        """
        self.stop()

        # In a real environment, we'd use the video URL.
        # For prototype/verification, we use mpv's ability to play dummy or local files.
        # Here we use video.url.
        # Create a temporary input.conf to map 's' to quit, matching our app's 'stop' key.
        # This helps when mpv has focus and the user wants to stop.
        input_conf_path = "/tmp/mpv_input.conf"
        with open(input_conf_path, "w") as f:
            f.write("s quit\n")
            f.write(f"n quit {MPV_EXIT_CODE_NEXT}\n") # Map 'n' to quit with exit code 5 to signal 'next'

        try:
            self.process = subprocess.Popen(
                ['mpv', video.url, '--title=' + video.title, '--input-conf=' + input_conf_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return self.process.pid
        except FileNotFoundError:
            # mpv not found
            raise RuntimeError("mpv command not found")

    def stop(self) -> None:
        """
        Stops the current mpv process if it exists.
        """
        if self.process:
            try:
                # Try graceful termination first
                self.process.terminate()
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                # Force kill if it doesn't stop
                self.process.kill()
            finally:
                self.process = None

    def is_playing(self) -> bool:
        """
        Checks if the mpv process is still running.
        """
        if self.process:
            return self.process.poll() is None
        return False

    def poll_exit_code(self) -> Optional[int]:
        """
        Returns the exit code if the process has exited, otherwise None.
        """
        if self.process:
            return self.process.poll()
        return None
