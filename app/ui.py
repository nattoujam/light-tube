import curses
import time
from typing import List, Optional, Tuple
import random
from .state import AppState, State, FocusArea
from .models import Video, Channel

class Tui:
    # Color Pair IDs
    COLOR_DEFAULT = 0
    COLOR_HIGHLIGHT = 1  # Magenta
    COLOR_BORDER = 2
    COLOR_HEADER = 3

    SIDEBAR_WIDTH = 25

    def __init__(self, stdscr):
        self.stdscr = stdscr
        curses.curs_set(0)
        self._init_colors()
        self.height, self.width = stdscr.getmaxyx()
        self.scroll_offset = 0
        self.sidebar_scroll_offset = 0

        # Initialize windows once to avoid memory leaks
        self.header_win = curses.newwin(2, self.width, 0, 0)
        self.sidebar_win = curses.newwin(self.height - 6, self.SIDEBAR_WIDTH, 2, 0)
        self.main_win = curses.newwin(self.height - 6, self.width - self.SIDEBAR_WIDTH, 2, self.SIDEBAR_WIDTH)
        self.footer_win = curses.newwin(4, self.width, self.height - 4, 0)

        self.register_win = curses.newwin(12, 60, self.height // 2 - 6, self.width // 2 - 30)
        self.confirm_win = curses.newwin(8, 60, self.height // 2 - 4, self.width // 2 - 30)
        self.error_win = curses.newwin(10, 60, self.height // 2 - 5, self.width // 2 - 30)
        self.loading_win = curses.newwin(5, 40, self.height // 2 - 2, self.width // 2 - 20)
        self.help_win = None

    def _init_colors(self):
        if curses.has_colors():
            curses.start_color()
            curses.use_default_colors()
            # Magenta foreground, default background
            curses.init_pair(self.COLOR_HIGHLIGHT, curses.COLOR_MAGENTA, -1)
            # Border/Dim color
            curses.init_pair(self.COLOR_BORDER, curses.COLOR_CYAN, -1)
            # Header color
            curses.init_pair(self.COLOR_HEADER, curses.COLOR_BLACK, curses.COLOR_WHITE)

    def draw_header(self, state: AppState):
        self.header_win.erase()
        self.header_win.attron(curses.A_REVERSE)
        app_name = "Lightweight Video Player"

        channel = state.highlighted_channel
        context_name = channel.name if channel else "All Videos"

        status = state.update_status if state.update_status else ""
        if state.state == State.UPDATING or state.state == State.LOADING:
            status = "処理中..."

        line = f" {app_name} | {context_name} | {status}"
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

    def _calculate_scroll_offset(self, current_idx: int, visible_height: int, current_offset: int) -> int:
        if current_idx < current_offset:
            return current_idx
        elif current_idx >= current_offset + visible_height:
            return current_idx - visible_height + 1
        return current_offset

    def _draw_scrollbar(self, win, offset: int, total_items: int):
        h, w = win.getmaxyx()
        if total_items <= h:
            return

        # Handle (thumb) height based on visible proportion
        bar_height = max(1, int(h * h / total_items))
        # Handle position based on scroll offset
        bar_pos = int(h * offset / total_items)
        # Prevent handle from overflowing
        bar_pos = min(bar_pos, h - bar_height)

        for i in range(h):
            char = "┃" if bar_pos <= i < bar_pos + bar_height else "│"
            try:
                win.attron(curses.color_pair(self.COLOR_BORDER))
                win.addstr(i, w - 1, char)
                win.attroff(curses.color_pair(self.COLOR_BORDER))
            except curses.error:
                pass

    def _draw_sidebar_item(self, y: int, name: str, is_selected: bool, is_focused: bool, width: int):
        display_name = self._truncate_with_width(name, width - 2)
        attr = curses.A_NORMAL
        if is_selected:
            if is_focused:
                attr = curses.color_pair(self.COLOR_HIGHLIGHT) | curses.A_BOLD
            else:
                attr = curses.A_UNDERLINE

        try:
            self.sidebar_win.addstr(y, 1, display_name, attr)
        except curses.error:
            pass

    def draw_sidebar(self, state: AppState):
        self.sidebar_win.erase()
        h, w = self.sidebar_win.getmaxyx()

        items = ["All Videos"] + [c.name for c in state.display_channels]
        total_items = len(items)

        if state.focus_area == FocusArea.SIDEBAR:
            self.sidebar_scroll_offset = self._calculate_scroll_offset(state.sidebar_idx, h, self.sidebar_scroll_offset)

        for i in range(h):
            idx = i + self.sidebar_scroll_offset
            if idx >= total_items:
                break

            self._draw_sidebar_item(
                i, items[idx],
                is_selected=(idx == state.sidebar_idx),
                is_focused=(state.focus_area == FocusArea.SIDEBAR),
                width=w
            )

        self._draw_scrollbar(self.sidebar_win, self.sidebar_scroll_offset, total_items)
        # Vertical divider
        for i in range(h):
            try:
                self.sidebar_win.attron(curses.color_pair(self.COLOR_BORDER))
                self.sidebar_win.addstr(i, w - 2, "│")
                self.sidebar_win.attroff(curses.color_pair(self.COLOR_BORDER))
            except curses.error:
                pass
        self.sidebar_win.noutrefresh()

    def _draw_video_line(self, y: int, video: Video, is_selected: bool, width: int):
        viewed_mark = "●" if not video.viewed else " "
        channel_info = f" {video.channel.name}"

        attr = curses.A_NORMAL
        if is_selected:
            attr = curses.color_pair(self.COLOR_HIGHLIGHT) | curses.A_BOLD

        title_width = width - 15 - self._get_display_width(channel_info)
        title = self._truncate_with_width(video.title, title_width)

        line = f" {viewed_mark} {title}"
        try:
            self.main_win.addstr(y, 0, line, attr)
            # Align channel info to the right
            chan_x = width - self._get_display_width(channel_info) - 2
            self.main_win.addstr(y, chan_x, channel_info, curses.A_DIM)
        except curses.error:
            pass

    def draw_main_area(self, state: AppState):
        self.main_win.erase()
        main_height, main_width = self.main_win.getmaxyx()

        videos = state.display_videos
        if not videos:
            self.main_win.addstr(1, 2, "No videos found.")
        else:
            self.scroll_offset = self._calculate_scroll_offset(state.selected_idx, main_height, self.scroll_offset)
            for i in range(main_height):
                idx = i + self.scroll_offset
                if idx >= len(videos):
                    break

                self._draw_video_line(
                    i, videos[idx],
                    is_selected=(idx == state.selected_idx and state.focus_area == FocusArea.MAIN),
                    width=main_width
                )

        self._draw_scrollbar(self.main_win, self.scroll_offset, len(videos))
        self.main_win.noutrefresh()

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

        # Row 1: Playback status
        status_text = self._get_status_text(state)
        display_line1 = self._truncate_with_width(status_text, self.width - 6)
        self.footer_win.addstr(1, 2, display_line1)

        # Row 2: Guide
        if state.focus_area == FocusArea.SIDEBAR:
            guide_text = "[Enter:Select] [a:Add] [d:Delete] [u:Update] [?:Help]"
        else:
            guide_text = "[Enter:Play] [n:Next] [s:Stop] [u:Update] [i:History] [?:Help]"

        self.footer_win.addstr(2, 2, guide_text)

        next_video = state.next_video
        if next_video:
            max_next_len = self.width - len(guide_text) - 10
            next_text = f"Next: {self._truncate_with_width(next_video.title, max_next_len)}"
            self.footer_win.addstr(2, self.width - self._get_display_width(next_text) - 2, next_text, curses.A_DIM)

        self.footer_win.noutrefresh()

    def draw_help(self, state: AppState):
        items = [
            "↑/↓, j/k: Move",
            "←/→, h/l: Sidebar/Main",
            "b: Back to UI",
            "?: Toggle Help",
            "q: Quit"
        ]

        if state.focus_area == FocusArea.SIDEBAR:
            items.insert(2, "a: Add Channel")
            items.insert(3, "d: Delete Channel")
            items.insert(4, "u: Update Channels")
        else:
            items.insert(2, "Enter: Play")
            items.insert(3, "n: Next")
            items.insert(4, "s: Stop")
            items.insert(5, "u: Update Latest")
            items.insert(6, "i: Update History")

        win_height = len(items) + 4
        if not self.help_win or self.help_win.getmaxyx()[0] != win_height:
            self.help_win = curses.newwin(win_height, 40, self.height // 2 - win_height // 2, self.width // 2 - 20)

        self.help_win.erase()
        self.help_win.box()
        channel = state.highlighted_channel
        context_name = channel.name if channel else "All Videos"
        self.help_win.addstr(1, 2, f"Help: {context_name}", curses.A_BOLD)
        for i, item in enumerate(items):
            self.help_win.addstr(2 + i, 2, item)
        self.help_win.noutrefresh()

    def render(self, state: AppState):
        if state.state != State.REGISTER:
            curses.curs_set(0)
        self.draw_header(state)
        self.draw_sidebar(state)
        self.draw_main_area(state)
        self.draw_footer(state)
        if state.state == State.UPDATING or state.state == State.LOADING:
            self.draw_loading(state)
        if state.state == State.REGISTER:
            self.draw_register(state)
        elif state.state == State.CONFIRM_DELETE:
            self.draw_confirm_delete(state)
        elif state.state == State.ERROR:
            self.draw_error(state)
        if state.show_help:
            self.draw_help(state)
        curses.doupdate()

    def draw_confirm_delete(self, state: AppState):
        self.confirm_win.erase()
        self.confirm_win.box()
        self.confirm_win.addstr(1, 2, "チャンネル削除の確認", curses.A_BOLD)

        channel = state.highlighted_channel
        name = channel.name if channel else "???"
        self.confirm_win.addstr(3, 2, f"チャンネル 「{name}」 を削除しますか？")
        self.confirm_win.addstr(4, 2, "紐付く動画データもすべて削除されます。")
        self.confirm_win.addstr(6, 2, "y: 削除する  /  n: キャンセル", curses.A_REVERSE)
        self.confirm_win.noutrefresh()

    def draw_register(self, state: AppState):
        self.register_win.erase()
        self.register_win.box()
        h, w = self.register_win.getmaxyx()

        # Title with highlight
        self.register_win.addstr(1, w // 2 - 7, " チャンネル登録 ", curses.A_BOLD | curses.color_pair(self.COLOR_HIGHLIGHT))

        # Step 1: Platform
        p_attr = curses.A_BOLD if state.registration_step == 0 else curses.A_DIM
        self.register_win.addstr(3, 4, "1. プラットフォームを選択", p_attr)

        y_attr = curses.color_pair(self.COLOR_HIGHLIGHT) if state.registration_platform == "youtube" else curses.A_DIM
        self.register_win.addstr(4, 7, "[y]: YouTube", y_attr)

        # Step 2: Channel Name
        n_attr = curses.A_BOLD if state.registration_step == 1 else curses.A_DIM
        self.register_win.addstr(6, 4, "2. チャンネル名を入力", n_attr)

        if state.registration_step == 1:
            prompt = "  入力: "
            pw = self._get_display_width(prompt)
            self.register_win.addstr(7, 4, prompt, curses.color_pair(self.COLOR_HIGHLIGHT) | curses.A_BOLD)

            # Draw buffer
            input_area_width = w - 4 - 4 - pw
            self.register_win.addstr(7, 4 + pw, "_" * input_area_width, curses.A_DIM)
            display_input = self._truncate_with_width(state.registration_buffer, input_area_width)
            self.register_win.addstr(7, 4 + pw, display_input)

            # Position cursor for doupdate
            curses.curs_set(1)
            cursor_pos = self._get_display_width(display_input)
            self.register_win.move(7, 4 + pw + cursor_pos)
        else:
            curses.curs_set(0)

        # Footer guidance
        self.register_win.addstr(h - 2, 4, "[Esc: キャンセル]", curses.A_DIM)

        # エラーメッセージがあれば表示
        if state.error_message:
            msg = f" Error: {state.error_message[:45]} "
            self.register_win.addstr(h - 4, w // 2 - len(msg) // 2, msg, curses.color_pair(1) | curses.A_BOLD)

        self.register_win.noutrefresh()

    def draw_loading(self, state: AppState):
        self.loading_win.erase()
        self.loading_win.box()
        msg = "Processing..."
        if state.state == State.UPDATING:
            msg = "Updating Videos..."
        elif state.state == State.LOADING:
            msg = "Registering Channel..."

        self.loading_win.addstr(2, 20 - len(msg) // 2, msg, curses.A_BOLD | curses.color_pair(self.COLOR_HIGHLIGHT))

        # Simple progress animation
        spinner = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        frame = int(time.time() * 10) % len(spinner)
        self.loading_win.addstr(2, 2, spinner[frame])

        self.loading_win.noutrefresh()

    def draw_error(self, state: AppState):
        self.error_win.erase()
        self.error_win.box()
        self.error_win.attron(curses.A_BOLD | curses.color_pair(1)) # Red if possible
        self.error_win.addstr(1, 2, "エラーが発生しました")
        self.error_win.attroff(curses.A_BOLD | curses.color_pair(1))

        msg = state.error_message or "不明なエラー"
        # メッセージを折り返して表示
        for i, line in enumerate([msg[i:i+54] for i in range(0, len(msg), 54)]):
            if i > 5: break
            self.error_win.addstr(3 + i, 2, line)

        self.error_win.addstr(8, 2, "bキーで戻る")
        self.error_win.noutrefresh()

