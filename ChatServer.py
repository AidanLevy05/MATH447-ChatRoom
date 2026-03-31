#
# ChatServer.py
# Created: 03/31/2026
# Last Updated: 03/31/2026 by Codex
#

import curses
import socket
import textwrap
import threading
import time

HOST = '127.0.0.1'
PORT = 65432
MAX_CLIENTS = 2
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


class ChatServer:
    def __init__(self):
        self.server = None
        self.clients = []
        self.client_threads = []
        self.clients_lock = threading.Lock()
        self.logs = []
        self.logs_lock = threading.Lock()
        self.running = threading.Event()
        self.running.set()
        self.client_id = 0
        self.accept_thread = None

    def log(self, message):
        with self.logs_lock:
            self.logs.append(message)

    def get_logs(self):
        with self.logs_lock:
            return list(self.logs)

    def active_clients(self):
        with self.clients_lock:
            return len(self.clients)

    def start(self):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind((HOST, PORT))
        self.server.listen(MAX_CLIENTS)
        self.server.settimeout(0.5)
        self.log(f'[SERVER] Listening on: {HOST}:{PORT}')
        self.accept_thread = threading.Thread(target=self.accept_loop, daemon=True)
        self.accept_thread.start()

    def accept_loop(self):
        announced_ready = False

        while self.running.is_set():
            if self.active_clients() >= MAX_CLIENTS:
                if not announced_ready:
                    self.log('[SERVER] Both clients connected. Relaying messages.')
                    announced_ready = True
                time.sleep(0.1)
                continue

            try:
                conn, addr = self.server.accept()
            except socket.timeout:
                continue
            except OSError:
                break

            with self.clients_lock:
                if len(self.clients) >= MAX_CLIENTS:
                    conn.close()
                    continue

                self.client_id += 1
                client_id = self.client_id
                self.clients.append(conn)

            self.log(f'[CLIENT {client_id}] Connected from {addr}')

            thread = threading.Thread(
                target=self.handle_client,
                args=(conn, client_id),
                daemon=True,
            )
            self.client_threads.append(thread)
            thread.start()

            if self.active_clients() < MAX_CLIENTS:
                announced_ready = False

    def handle_client(self, conn, client_id):
        try:
            while self.running.is_set():
                data = conn.recv(4096)
                if not data:
                    break

                message = data.decode(errors='replace')
                self.log(f'[CLIENT {client_id}] {len(data)} bytes | {message}')

                with self.clients_lock:
                    recipients = [client for client in self.clients if client is not conn]

                for recipient in recipients:
                    try:
                        recipient.sendall(data)
                    except OSError:
                        pass
        except (ConnectionResetError, OSError) as exc:
            if self.running.is_set():
                self.log(f'[CLIENT {client_id}] Connection error: {exc}')
        finally:
            with self.clients_lock:
                if conn in self.clients:
                    self.clients.remove(conn)

            try:
                conn.close()
            except OSError:
                pass

            self.log(f'[CLIENT {client_id}] Disconnected')

    def draw(self, stdscr):
        stdscr.erase()
        height, width = stdscr.getmaxyx()
        log_top = 3
        log_bottom = max(log_top, height - 3)
        log_height = max(1, log_bottom - log_top + 1)
        log_width = max(8, width - 4)

        safe_addstr(stdscr, 0, 2, 'MATH 447 CHAT ROOM SERVER', curses.A_BOLD)
        safe_addstr(stdscr, 1, 2, f'Listening on {HOST}:{PORT} | Active clients: {self.active_clients()}/{MAX_CLIENTS}')
        draw_hline(stdscr, 2)
        draw_hline(stdscr, height - 2)

        visible_logs = wrap_lines(self.get_logs(), log_width)[-log_height:]
        for row, line in enumerate(visible_logs, start=log_top):
            safe_addstr(stdscr, row, 2, line)

        safe_addstr(stdscr, height - 1, 2, 'Press q to stop the server.')
        stdscr.refresh()

    def show_error(self, stdscr, message):
        stdscr.erase()
        safe_addstr(stdscr, 1, 2, 'MATH 447 CHAT ROOM SERVER', curses.A_BOLD)
        draw_hline(stdscr, 2)
        wrapped = wrap_lines([message], max(8, stdscr.getmaxyx()[1] - 4))
        for row, line in enumerate(wrapped, start=4):
            safe_addstr(stdscr, row, 2, line)
        safe_addstr(stdscr, stdscr.getmaxyx()[0] - 2, 2, 'Press any key to exit.')
        stdscr.refresh()
        stdscr.timeout(-1)
        stdscr.getch()

    def shutdown(self):
        self.running.clear()

        if self.server is not None:
            try:
                self.server.close()
            except OSError:
                pass

        with self.clients_lock:
            clients = list(self.clients)
            self.clients.clear()

        for conn in clients:
            try:
                conn.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                conn.close()
            except OSError:
                pass

        if self.accept_thread is not None:
            self.accept_thread.join(timeout=1)

        for thread in self.client_threads:
            thread.join(timeout=1)

    def run(self, stdscr):
        try:
            curses.curs_set(0)
        except curses.error:
            pass
        stdscr.keypad(True)
        stdscr.timeout(POLL_MS)

        try:
            self.start()
        except OSError as exc:
            self.show_error(stdscr, f'Could not start server on {HOST}:{PORT}: {exc}')
            return

        try:
            while self.running.is_set():
                self.draw(stdscr)
                key = stdscr.getch()
                if key in (ord('q'), ord('Q')):
                    break
        finally:
            self.shutdown()


def main():
    server = ChatServer()
    curses.wrapper(server.run)


if __name__ == '__main__':
    main()
