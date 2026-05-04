#
# PlainChatServer.py
# Created: 04/07/2026
# Last Updated: 04/07/2026 by Aidan
#

import curses
import json
import socket
import textwrap
import threading

HOST = '127.0.0.1'
PORT = 65433
MAX_CLIENTS = 10
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


class PlainChatServer:
    def __init__(self):
        self.server = None
        self.clients = {}
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

    def send_packet(self, conn, packet):
        payload = json.dumps(packet, separators=(',', ':')).encode('utf-8') + b'\n'
        conn.sendall(payload)

    def broadcast_packet(self, packet, exclude=None):
        with self.clients_lock:
            recipients = [client for client in self.clients if client is not exclude]

        for recipient in recipients:
            try:
                self.send_packet(recipient, packet)
            except OSError:
                pass

    def get_client_info(self, conn):
        with self.clients_lock:
            info = self.clients.get(conn)
            if info is None:
                return None
            return dict(info)

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
        while self.running.is_set():
            try:
                conn, addr = self.server.accept()
            except socket.timeout:
                continue
            except OSError:
                break

            with self.clients_lock:
                if len(self.clients) >= MAX_CLIENTS:
                    client_id = None
                else:
                    self.client_id += 1
                    client_id = self.client_id
                    self.clients[conn] = {
                        'id': client_id,
                        'addr': addr,
                        'name': f'Client {client_id}',
                    }

            if client_id is None:
                self.log(f'[SERVER] Rejected connection from {addr}: server full.')
                try:
                    conn.close()
                except OSError:
                    pass
                continue

            self.log(f'[CLIENT {client_id}] Connected from {addr}')

            thread = threading.Thread(
                target=self.handle_client,
                args=(conn, client_id),
                daemon=True,
            )
            self.client_threads.append(thread)
            thread.start()

    def handle_packet(self, conn, client_id, packet):
        packet_type = packet.get('type', '')

        if packet_type == 'hello':
            name = str(packet.get('name', '')).strip() or f'Client {client_id}'

            with self.clients_lock:
                info = self.clients.get(conn)
                if info is None:
                    return
                info['name'] = name

            self.send_packet(conn, {
                'type': 'welcome',
                'client_id': client_id,
            })
            self.broadcast_packet({
                'type': 'peer_joined',
                'client_id': client_id,
                'name': name,
            }, exclude=conn)
            self.log(f'[CLIENT {client_id}] Plaintext connection ready for {name}')
            return

        if packet_type == 'chat':
            message = str(packet.get('message', '')).strip()
            if not message:
                return

            info = self.get_client_info(conn)
            if info is None:
                return

            sender_name = info['name']
            self.log(f'[CLIENT {client_id}] {sender_name}: {message}')
            self.broadcast_packet({
                'type': 'chat',
                'client_id': client_id,
                'from': sender_name,
                'message': message,
            }, exclude=conn)
            return

        self.log(f'[CLIENT {client_id}] Unknown packet type: {packet_type}')

    def handle_client(self, conn, client_id):
        buffer = ''

        try:
            while self.running.is_set():
                data = conn.recv(4096)
                if not data:
                    break

                buffer += data.decode('utf-8', errors='replace')
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if not line.strip():
                        continue

                    try:
                        packet = json.loads(line)
                    except json.JSONDecodeError:
                        self.log(f'[CLIENT {client_id}] Malformed packet received')
                        continue

                    self.handle_packet(conn, client_id, packet)
        except (ConnectionResetError, OSError) as exc:
            if self.running.is_set():
                self.log(f'[CLIENT {client_id}] Connection error: {exc}')
        finally:
            with self.clients_lock:
                info = self.clients.pop(conn, None)

            try:
                conn.close()
            except OSError:
                pass

            name = info['name'] if info is not None else f'Client {client_id}'
            self.broadcast_packet({
                'type': 'peer_left',
                'client_id': client_id,
                'name': name,
            }, exclude=conn)
            self.log(f'[CLIENT {client_id}] Disconnected ({name})')

    def draw(self, stdscr):
        stdscr.erase()
        height, width = stdscr.getmaxyx()
        log_top = 3
        log_bottom = max(log_top, height - 3)
        log_height = max(1, log_bottom - log_top + 1)
        log_width = max(8, width - 4)

        safe_addstr(stdscr, 0, 2, 'MATH 447 CHAT ROOM SERVER (PLAINTEXT)', curses.A_BOLD)
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
        safe_addstr(stdscr, 1, 2, 'MATH 447 CHAT ROOM SERVER (PLAINTEXT)', curses.A_BOLD)
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
            clients = list(self.clients.keys())
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
    server = PlainChatServer()
    curses.wrapper(server.run)


if __name__ == '__main__':
    main()
