import curses
from typing import List, Optional, Tuple
import random
from .state import AppState, State
from .models import Video

class Tui:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        curses.curs_set(0)
        self.height, self.width = stdscr.getmaxyx()
        self.scroll_offset = 0

        # Initialize windows once to avoid memory leaks
        self.header_win = curses.newwin(2, self.width, 0, 0)
        self.main_win = curses.newwin(self.height - 5, self.width, 2, 0)
        self.footer_win = curses.newwin(3, self.width, self.height - 3, 0)
        self.help_win = None

    def draw_header(self, state: AppState):
        self.header_win.erase()
        self.header_win.attron(curses.A_REVERSE)
        app_name = "Lightweight Video Player"
        tab_info = f"Tab: [{state.current_tab}]"
        status = state.update_status if state.update_status else ""
        if state.state == State.UPDATING:
            status = "更新中..."

        line = f" {app_name} | {tab_info} | {status}"
        self.header_win.addstr(0, 0, line.ljust(self.width))
        self.header_win.attroff(curses.A_REVERSE)
        self.header_win.noutrefresh()

    def draw_main_area(self, state: AppState):
        self.main_win.erase()
        main_height, _ = self.main_win.getmaxyx()

        videos = state.get_filtered_videos()
        if not videos:
            self.main_win.addstr(1, 2, "No videos found.")
        else:
            # Adjust scroll offset if necessary
            if state.selected_idx < self.scroll_offset:
                self.scroll_offset = state.selected_idx
            elif state.selected_idx >= self.scroll_offset + main_height:
                self.scroll_offset = state.selected_idx - main_height + 1

            for i in range(main_height):
                video_idx = i + self.scroll_offset
                if video_idx >= len(videos):
                    break

                video = videos[video_idx]
                prefix = ">" if video_idx == state.selected_idx else " "
                viewed_mark = "[v]" if video.viewed else "[ ]"
                title = video.title[:self.width - 25]
                line = f"{prefix} {viewed_mark} {title} ({video.channel})"

                if video_idx == state.selected_idx:
                    self.main_win.attron(curses.A_REVERSE)
                    self.main_win.addstr(i, 0, line.ljust(self.width))
                    self.main_win.attroff(curses.A_REVERSE)
                else:
                    self.main_win.addstr(i, 0, line)

        self.main_win.noutrefresh()

    def draw_footer(self, state: AppState):
        self.footer_win.erase()
        self.footer_win.box()

        status_text = "▶ Ready"
        if state.state == State.LAUNCHING:
            video = state.selected_video
            title = video.title if video else "???"
            status_text = f"▶ 起動中… {title}"
        elif state.state == State.PLAYING:
            title = state.now_playing.title if state.now_playing else "???"
            status_text = f"▶ 再生中: {title} [n:Next] [s:Stop] [b:UI]"
        elif state.state == State.AFTER_PLAY:
            last_video = state.last_played_video
            title = last_video.title if last_video else "???"
            status_text = f"⏹ 再生終了: {title} [n:Next]"
        elif state.state == State.ERROR:
            status_text = f"⚠ Error: {state.error_message}"

        self.footer_win.addstr(1, 2, status_text[:self.width - 4])

        # Next info
        next_video = state.next_video
        if next_video:
            next_text = f"Next: {next_video.title} (n)"
            self.footer_win.addstr(1, max(2, self.width // 2), next_text[:self.width // 2 - 2])

        self.footer_win.noutrefresh()

    def draw_help(self):
        if not self.help_win:
            self.help_win = curses.newwin(13, 40, self.height // 2 - 6, self.width // 2 - 20)
        self.help_win.erase()
        self.help_win.box()
        self.help_win.addstr(1, 2, "Keys:")
        self.help_win.addstr(2, 2, "↑/↓, j/k: Move")
        self.help_win.addstr(3, 2, "Enter: Play")
        self.help_win.addstr(4, 2, "Tab: Switch Tab")
        self.help_win.addstr(5, 2, "n: Next")
        self.help_win.addstr(6, 2, "s: Stop")
        self.help_win.addstr(7, 2, "u: Update")
        self.help_win.addstr(8, 2, "r: Random Refresh")
        self.help_win.addstr(9, 2, "b: Back to UI")
        self.help_win.addstr(10, 2, "h: Toggle Help")
        self.help_win.addstr(11, 2, "q: Quit")
        self.help_win.noutrefresh()

    def render(self, state: AppState):
        self.draw_header(state)
        self.draw_main_area(state)
        self.draw_footer(state)
        if state.show_help:
            self.draw_help()
        curses.doupdate()
