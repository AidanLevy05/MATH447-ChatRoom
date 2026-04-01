#
# ChatClient.py
# Created: 03/31/2026
# Last Updated: 03/31/2026 by Aidan
#

import curses
import socket
import textwrap
import threading

HOST = '127.0.0.1'
PORT = 65432
POLL_MS = 100


def safe_addstr(win, y, x, text, attr=0):
    height, width = win.getmaxyx()
    if y < 0 or y >= height or x < 0 or x >= width:
        return

    max_len = max(0, width - x - 1)
    if max_len <= 0:
        return

    try:
        win.addnstr(y, x, text, max_len, attr)
    except curses.error:
        pass


def draw_hline(win, y, char='-'):
    _, width = win.getmaxyx()
    if y < 0:
        return
    try:
        win.hline(y, 0, ord(char), max(0, width - 1))
    except curses.error:
        pass


def wrap_lines(messages, width):
    if width <= 1:
        return []

    lines = []
    for message in messages:
        parts = message.splitlines() or ['']
        for part in parts:
            wrapped = textwrap.wrap(part, width=width) or ['']
            lines.extend(wrapped)
    return lines


class ChatClient:
    def __init__(self):
        self.conn = None
        self.listener = None
        self.name = ''
        self.messages = []
        self.messages_lock = threading.Lock()
        self.running = True
        self.status = 'Not connected'

    def add_message(self, message):
        with self.messages_lock:
            self.messages.append(message)

    def get_messages(self):
        with self.messages_lock:
            return list(self.messages)

    def connect(self):
        self.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.conn.connect((HOST, PORT))
        self.status = f'Connected to {HOST}:{PORT}'
        self.listener = threading.Thread(target=self.receive_messages, daemon=True)
        self.listener.start()

    def receive_messages(self):
        try:
            while self.running:
                data = self.conn.recv(4096)
                if not data:
                    self.add_message('[SYSTEM] Server closed the connection.')
                    break
                self.add_message(data.decode(errors='replace'))
        except (ConnectionResetError, OSError) as exc:
            if self.running:
                self.add_message(f'[SYSTEM] Connection lost: {exc}')
        finally:
            self.running = False
            self.status = 'Disconnected'
            self.close_connection()

    def close_connection(self):
        if self.conn is None:
            return
        try:
            self.conn.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self.conn.close()
        except OSError:
            pass
        self.conn = None

    def prompt_for_name(self, stdscr):
        buffer = ''

        while True:
            stdscr.erase()
            height, width = stdscr.getmaxyx()
            center_x = max(2, (width // 2) - 10)
            center_y = max(2, height // 2 - 2)

            safe_addstr(stdscr, center_y - 2, center_x, 'MATH 447 CHAT ROOM', curses.A_BOLD)
            safe_addstr(stdscr, center_y, 2, 'Enter your name and press ENTER:')
            draw_hline(stdscr, center_y + 1)
            visible = buffer[-max(1, width - 6):]
            safe_addstr(stdscr, center_y + 2, 2, f'> {visible}')
            safe_addstr(stdscr, height - 2, 2, 'Press Ctrl+C to exit.')

            cursor_x = min(width - 2, 4 + len(visible))
            try:
                stdscr.move(center_y + 2, cursor_x)
            except curses.error:
                pass

            stdscr.refresh()
            key = stdscr.getch()

            if key in (curses.KEY_ENTER, 10, 13):
                if buffer.strip():
                    return buffer.strip()
            elif key in (curses.KEY_BACKSPACE, 127, 8):
                buffer = buffer[:-1]
            elif key == curses.KEY_RESIZE:
                continue
            elif 32 <= key <= 126:
                buffer += chr(key)

    def draw(self, stdscr, input_buffer):
        stdscr.erase()
        height, width = stdscr.getmaxyx()
        chat_top = 3
        chat_bottom = max(chat_top, height - 4)
        chat_height = max(1, chat_bottom - chat_top + 1)
        chat_width = max(8, width - 4)

        safe_addstr(stdscr, 0, 2, 'MATH 447 CHAT ROOM', curses.A_BOLD)
        safe_addstr(stdscr, 1, 2, f'Name: {self.name} | {self.status}')
        draw_hline(stdscr, 2)
        draw_hline(stdscr, height - 3)

        visible_messages = wrap_lines(self.get_messages(), chat_width)[-chat_height:]
        for row, line in enumerate(visible_messages, start=chat_top):
            safe_addstr(stdscr, row, 2, line)

        visible_input = input_buffer[-max(1, width - 6):]
        safe_addstr(stdscr, height - 2, 2, f'> {visible_input}')
        safe_addstr(stdscr, height - 1, 2, 'ENTER=send  /quit=exit')

        cursor_x = min(width - 2, 4 + len(visible_input))
        try:
            stdscr.move(height - 2, cursor_x)
        except curses.error:
            pass

        stdscr.refresh()

    def show_error(self, stdscr, message):
        stdscr.erase()
        safe_addstr(stdscr, 1, 2, 'MATH 447 CHAT ROOM', curses.A_BOLD)
        draw_hline(stdscr, 2)
        wrapped = wrap_lines([message], max(8, stdscr.getmaxyx()[1] - 4))
        for row, line in enumerate(wrapped, start=4):
            safe_addstr(stdscr, row, 2, line)
        safe_addstr(stdscr, stdscr.getmaxyx()[0] - 2, 2, 'Press any key to exit.')
        stdscr.refresh()
        stdscr.timeout(-1)
        stdscr.getch()

    def run(self, stdscr):
        try:
            curses.curs_set(1)
        except curses.error:
            pass
        stdscr.keypad(True)
        stdscr.timeout(POLL_MS)

        self.name = self.prompt_for_name(stdscr)

        try:
            self.connect()
        except OSError as exc:
            self.show_error(stdscr, f'Could not connect to {HOST}:{PORT}: {exc}')
            return

        input_buffer = ''
        self.add_message(f'[SYSTEM] Connected to {HOST}:{PORT}')

        try:
            while self.running:
                self.draw(stdscr, input_buffer)
                key = stdscr.getch()

                if key == -1 or key == curses.KEY_RESIZE:
                    continue
                if key in (curses.KEY_ENTER, 10, 13):
                    message = input_buffer.strip()
                    input_buffer = ''

                    if not message:
                        continue
                    if message.lower() == '/quit':
                        break

                    payload = f'{self.name}: {message}'
                    try:
                        self.conn.sendall(payload.encode())
                        self.add_message(payload)
                    except OSError as exc:
                        self.add_message(f'[SYSTEM] Send failed: {exc}')
                        break
                elif key in (curses.KEY_BACKSPACE, 127, 8):
                    input_buffer = input_buffer[:-1]
                elif 32 <= key <= 126:
                    input_buffer += chr(key)
        finally:
            self.running = False
            self.status = 'Disconnected'
            self.close_connection()


def main():
    client = ChatClient()
    curses.wrapper(client.run)


if __name__ == '__main__':
    main()
