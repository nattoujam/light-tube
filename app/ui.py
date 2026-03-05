import curses
from typing import List, Optional, Tuple
import random
from .state import AppState, State
from .models import Video, Channel

class Tui:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        curses.curs_set(0)
        self.height, self.width = stdscr.getmaxyx()
        self.scroll_offset = 0

        # Initialize windows once to avoid memory leaks
        self.header_win = curses.newwin(2, self.width, 0, 0)
        self.main_win = curses.newwin(self.height - 6, self.width, 2, 0)
        self.footer_win = curses.newwin(4, self.width, self.height - 4, 0)
        self.register_win = curses.newwin(12, 60, self.height // 2 - 6, self.width // 2 - 30)
        self.confirm_win = curses.newwin(8, 60, self.height // 2 - 4, self.width // 2 - 30)
        self.error_win = curses.newwin(10, 60, self.height // 2 - 5, self.width // 2 - 30)
        self.help_win = None

    def draw_header(self, state: AppState):
        self.header_win.erase()
        self.header_win.attron(curses.A_REVERSE)
        app_name = "Lightweight Video Player"
        tab_info = f"Tab: [{state.current_tab}]"
        status = state.update_status if state.update_status else ""
        if state.state == State.UPDATING or state.state == State.LOADING:
            status = "処理中..."

        line = f" {app_name} | {tab_info} | {status}"
        self.header_win.addstr(0, 0, line.ljust(self.width))
        self.header_win.attroff(curses.A_REVERSE)
        self.header_win.noutrefresh()

    def _get_display_width(self, text: str) -> int:
        width = 0
        for char in text:
            width += 2 if ord(char) > 0x7F else 1
        return width

    def _truncate_with_width(self, text: str, max_width: int) -> str:
        current_width = 0
        result = ""
        for char in text:
            char_width = 2 if ord(char) > 0x7F else 1
            if current_width + char_width > max_width:
                break
            result += char
            current_width += char_width
        return result

    def _pad_with_width(self, text: str, target_width: int) -> str:
        current_width = self._get_display_width(text)
        if current_width >= target_width:
            return text
        return text + (" " * (target_width - current_width))

    def _adjust_scroll(self, selected_idx: int, main_height: int) -> None:
        if selected_idx < self.scroll_offset:
            self.scroll_offset = selected_idx
        elif selected_idx >= self.scroll_offset + main_height:
            self.scroll_offset = selected_idx - main_height + 1

    def draw_main_area(self, state: AppState):
        self.main_win.erase()
        main_height, _ = self.main_win.getmaxyx()

        if state.current_tab == "Channels":
            channels = state.display_channels
            if not channels:
                self.main_win.addstr(1, 2, "No channels registered.")
            else:
                self._adjust_scroll(state.selected_idx, main_height)
                for i in range(main_height):
                    channel_idx = i + self.scroll_offset
                    if channel_idx >= len(channels):
                        break
                    self._draw_channel_line(i, channel_idx, channels[channel_idx], state.selected_idx)
        else:
            videos = state.get_filtered_videos()
            if not videos:
                self.main_win.addstr(1, 2, "No videos found.")
            else:
                self._adjust_scroll(state.selected_idx, main_height)

                for i in range(main_height):
                    video_idx = i + self.scroll_offset
                    if video_idx >= len(videos):
                        break
                    self._draw_video_line(i, video_idx, videos[video_idx], state.selected_idx)

        self.main_win.noutrefresh()

    def _draw_channel_line(self, y: int, idx: int, channel: Channel, selected_idx: int) -> None:
        prefix = ">" if idx == selected_idx else " "
        line = f"{prefix} {channel.name} ({channel.platform})"
        display_line = self._truncate_with_width(line, self.width - 2)

        try:
            if idx == selected_idx:
                self.main_win.attron(curses.A_REVERSE)
                padded_line = self._pad_with_width(display_line, self.width - 2)
                self.main_win.addstr(y, 0, padded_line)
                self.main_win.attroff(curses.A_REVERSE)
            else:
                self.main_win.addstr(y, 0, display_line)
        except curses.error:
            pass

    def _draw_video_line(self, y: int, video_idx: int, video: Video, selected_idx: int) -> None:
        prefix = ">" if video_idx == selected_idx else " "
        viewed_mark = "[v]" if video.viewed else "[ ]"

        # Calculate max title length to avoid overflow
        # Space for prefix(2), viewed_mark(4), space(1), channel(varies), parens(2)
        channel_info = f"({video.channel})"
        available_width = self.width - 10 - len(channel_info)
        title = self._truncate_with_width(video.title, available_width)
        line = f"{prefix} {viewed_mark} {title} {channel_info}"

        # Avoid writing to the last column of the last line to prevent ERR
        # Using self.width - 2 for extra safety
        display_line = self._truncate_with_width(line, self.width - 2)

        try:
            if video_idx == selected_idx:
                self.main_win.attron(curses.A_REVERSE)
                # Use custom pad instead of ljust (which is char-count based)
                padded_line = self._pad_with_width(display_line, self.width - 2)
                self.main_win.addstr(y, 0, padded_line)
                self.main_win.attroff(curses.A_REVERSE)
            else:
                self.main_win.addstr(y, 0, display_line)
        except curses.error:
            pass # Ignore write errors to the very edge

    def _get_status_text(self, state: AppState) -> str:
        status_text = "▶ Ready"
        if state.state == State.LAUNCHING:
            video = state.selected_video
            title = video.title if video else "???"
            status_text = f"▶ 起動中… {title}"
        elif state.state == State.PLAYING:
            title = state.now_playing.title if state.now_playing else "???"
            status_text = f"▶ 再生中: {title}"
        elif state.state == State.AFTER_PLAY:
            last_video = state.last_played_video
            title = last_video.title if last_video else "???"
            status_text = f"⏹ 再生終了: {title}"
        elif state.state == State.ERROR:
            status_text = "⚠ エラーが発生しました"
        return status_text

    def draw_footer(self, state: AppState):
        self.footer_win.erase()
        self.footer_win.box()

        # 1行目: 再生ステータスとタイトル
        status_text = self._get_status_text(state)

        # ウィンドウ幅（全角考慮）に合わせて切り捨て
        display_line1 = self._truncate_with_width(status_text, self.width - 6)
        self.footer_win.addstr(1, 2, display_line1)

        # 2行目: 次の動画と操作ガイド
        if state.current_tab == "Channels":
            guide_text = "[d:Delete] [a:Add] [b:Back] [u:Update] [h:Help]"
        else:
            guide_text = "[n:Next] [s:Stop] [b:Back] [u:Update] [i:History] [h:Help]"

        next_video = state.next_video
        if next_video:
            # Reserve space for guide_text at the right
            max_next_len = self.width - len(guide_text) - 10
            next_text = f"Next: {self._truncate_with_width(next_video.title, max_next_len)}"
            self.footer_win.addstr(2, 2, next_text)
            self.footer_win.addstr(2, self.width - len(guide_text) - 2, guide_text)
        else:
            self.footer_win.addstr(2, 2, guide_text)

        self.footer_win.noutrefresh()

    def draw_help(self):
        if not self.help_win:
            # Increased height to 16 to accommodate all items including border
            self.help_win = curses.newwin(16, 40, self.height // 2 - 8, self.width // 2 - 20)
        self.help_win.erase()
        self.help_win.box()
        self.help_win.addstr(1, 2, "Keys:")
        self.help_win.addstr(2, 2, "↑/↓, j/k: Move")
        self.help_win.addstr(3, 2, "Enter: Play")
        self.help_win.addstr(4, 2, "Tab: Switch Tab")
        self.help_win.addstr(5, 2, "n: Next")
        self.help_win.addstr(6, 2, "s: Stop")
        self.help_win.addstr(7, 2, "u: Update Latest")
        self.help_win.addstr(8, 2, "i: Update History")
        self.help_win.addstr(9, 2, "a: Add Channel (Channel Tab only)")
        self.help_win.addstr(10, 2, "d: Delete Channel (Channel Tab only)")
        self.help_win.addstr(11, 2, "r: Random Refresh")
        self.help_win.addstr(12, 2, "b: Back to UI")
        self.help_win.addstr(13, 2, "h: Toggle Help")
        self.help_win.addstr(14, 2, "q: Quit")
        self.help_win.noutrefresh()

    def render(self, state: AppState):
        self.draw_header(state)
        self.draw_main_area(state)
        self.draw_footer(state)
        if state.state == State.REGISTER:
            self.draw_register(state)
        elif state.state == State.CONFIRM_DELETE:
            self.draw_confirm_delete(state)
        elif state.state == State.ERROR:
            self.draw_error(state)
        if state.show_help:
            self.draw_help()
        curses.doupdate()

    def draw_confirm_delete(self, state: AppState):
        self.confirm_win.erase()
        self.confirm_win.box()
        self.confirm_win.addstr(1, 2, "チャンネル削除の確認", curses.A_BOLD)

        channel = None
        if 0 <= state.selected_idx < len(state.display_channels):
            channel = state.display_channels[state.selected_idx]

        name = channel.name if channel else "???"
        self.confirm_win.addstr(3, 2, f"チャンネル 「{name}」 を削除しますか？")
        self.confirm_win.addstr(4, 2, "紐付く動画データもすべて削除されます。")
        self.confirm_win.addstr(6, 2, "y: 削除する  /  n: キャンセル", curses.A_REVERSE)
        self.confirm_win.noutrefresh()

    def draw_register(self, state: AppState):
        self.register_win.erase()
        self.register_win.box()
        self.register_win.addstr(1, 2, "チャンネル登録", curses.A_BOLD)
        self.register_win.addstr(3, 2, "1. プラットフォームを選択 (y: YouTube)")
        # Input for platform will be on line 4
        self.register_win.addstr(6, 2, "2. チャンネル名(YT) を入力")
        # Input for name will be on line 7
        self.register_win.addstr(9, 2, "bキーでキャンセル")

        # エラーメッセージがあれば表示
        if state.error_message:
            self.register_win.attron(curses.color_pair(1) if curses.has_colors() else curses.A_BOLD)
            self.register_win.addstr(10, 2, f"エラー: {state.error_message[:54]}")
            if curses.has_colors():
                self.register_win.attroff(curses.color_pair(1))

        self.register_win.noutrefresh()

    def draw_error(self, state: AppState):
        self.error_win.erase()
        self.error_win.box()
        self.error_win.attron(curses.A_BOLD)
        self.error_win.addstr(1, 2, "エラーが発生しました")
        self.error_win.attroff(curses.A_BOLD)

        msg = state.error_message or "不明なエラー"
        # メッセージを折り返して表示
        for i, line in enumerate([msg[i:i+54] for i in range(0, len(msg), 54)]):
            if i > 5: break
            self.error_win.addstr(3 + i, 2, line)

        self.error_win.addstr(8, 2, "bキーで戻る")
        self.error_win.noutrefresh()

    def get_input_string(self, prompt: str, y: int, x: int) -> str:
        curses.echo()
        curses.curs_set(1)
        self.stdscr.nodelay(False)
        self.stdscr.addstr(y, x, prompt)
        self.stdscr.refresh()
        try:
            input_bytes = self.stdscr.getstr(y, x + len(prompt), 50)
            input_str = input_bytes.decode('utf-8')
        except:
            input_str = ""
        self.stdscr.nodelay(True)
        curses.curs_set(0)
        curses.noecho()
        return input_str
