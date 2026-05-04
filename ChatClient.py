#
# ChatClient.py
# Created: 03/31/2026
# Last Updated: 04/07/2026 by Aidan
#

import curses
import json
import socket
import textwrap
import threading
import time

from ChaCha import ChaChaCipher
from RSA import RSAKeyExchange

HOST = ''
PORT = 65432
DISCOVERY_PORT = 65433
DISCOVERY_MESSAGE = 'DISCOVER_CHAT_SERVER'
DISCOVERY_TIMEOUT = 2.0
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


def discover_servers():
    servers = []
    seen = set()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.bind(('', 0))
        sock.settimeout(0.25)
        sock.sendto(DISCOVERY_MESSAGE.encode('utf-8'), ('255.255.255.255', DISCOVERY_PORT))

        deadline = time.monotonic() + DISCOVERY_TIMEOUT
        while time.monotonic() < deadline:
            try:
                data, addr = sock.recvfrom(4096)
            except socket.timeout:
                continue

            try:
                response = json.loads(data.decode('utf-8', errors='replace'))
            except json.JSONDecodeError:
                continue

            server_ip = str(response.get('ip', addr[0])).strip() or addr[0]
            try:
                server_port = int(response.get('port', PORT))
            except (TypeError, ValueError):
                server_port = PORT

            key = (server_ip, server_port)
            if key in seen:
                continue

            seen.add(key)
            servers.append({
                'name': str(response.get('name', 'Chat Server')),
                'ip': server_ip,
                'port': server_port,
            })
    except OSError:
        pass
    finally:
        sock.close()

    return servers


class ChatClient:
    def __init__(self):
        self.conn = None
        self.listener = None
        self.chacha = ChaChaCipher()
        self.rsa = RSAKeyExchange()
        self.name = ''
        self.messages = []
        self.messages_lock = threading.Lock()
        self.peer_keys = {}
        self.peer_keys_lock = threading.Lock()
        self.running = True
        self.status = 'Not connected'
        self.client_id = None
        self.server_public_key = ''

    def add_message(self, message):
        with self.messages_lock:
            self.messages.append(message)

    def get_messages(self):
        with self.messages_lock:
            return list(self.messages)

    def peer_count(self):
        with self.peer_keys_lock:
            return len(self.peer_keys)

    def secure_peer_count(self):
        with self.peer_keys_lock:
            return sum(1 for peer in self.peer_keys.values() if peer.get('session_key'))

    def update_status(self):
        if self.conn is None:
            self.status = 'Disconnected'
            return

        if self.client_id is None:
            self.status = f'Connected to {HOST}:{PORT} | RSA pending'
            return

        self.status = (
            f'Connected to {HOST}:{PORT} | ID {self.client_id} | '
            f'Peers {self.peer_count()} | Secure {self.secure_peer_count()}'
        )

    def replace_peers(self, peers):
        with self.peer_keys_lock:
            existing_peers = self.peer_keys
            self.peer_keys = {}
            for peer in peers:
                public_key = peer.get('public_key', '')
                client_id = peer.get('client_id')
                if not public_key or client_id is None:
                    continue

                existing = existing_peers.get(client_id, {})
                self.peer_keys[client_id] = {
                    'name': peer.get('name', f'Client {client_id}'),
                    'public_key': public_key,
                    'session_key': existing.get('session_key', ''),
                }

    def upsert_peer(self, client_id, name, public_key):
        with self.peer_keys_lock:
            existing = self.peer_keys.get(client_id, {})
            self.peer_keys[client_id] = {
                'name': name,
                'public_key': public_key,
                'session_key': existing.get('session_key', ''),
            }

    def remove_peer(self, client_id):
        with self.peer_keys_lock:
            peer = self.peer_keys.pop(client_id, None)

        if peer is None:
            return None
        return peer['name']

    def get_peer_info(self, client_id):
        with self.peer_keys_lock:
            peer = self.peer_keys.get(client_id)
            if peer is None:
                return None
            return dict(peer)

    def get_peer_snapshot(self):
        with self.peer_keys_lock:
            return {
                client_id: dict(peer_info)
                for client_id, peer_info in self.peer_keys.items()
            }

    def set_session_key(self, client_id, session_key, name=None):
        with self.peer_keys_lock:
            existing = self.peer_keys.get(client_id, {})
            self.peer_keys[client_id] = {
                'name': name or existing.get('name', f'Client {client_id}'),
                'public_key': existing.get('public_key', ''),
                'session_key': session_key,
            }

    def clear_session_key(self, client_id, expected_key=None):
        with self.peer_keys_lock:
            peer = self.peer_keys.get(client_id)
            if peer is None:
                return
            if expected_key is not None and peer.get('session_key') != expected_key:
                return
            peer['session_key'] = ''

    def maybe_share_key_with_peer(self, client_id):
        if self.client_id is None or client_id is None or self.client_id >= client_id:
            return

        peer = self.get_peer_info(client_id)
        if peer is None or not peer.get('public_key') or peer.get('session_key'):
            return

        session_key = self.chacha.generate_key()
        self.set_session_key(client_id, session_key, peer['name'])

        try:
            encrypted_key = self.rsa.encrypt_for_public_key(session_key, peer['public_key'])
            self.send_packet({
                'type': 'key_exchange',
                'target_client_id': client_id,
                'encrypted_key': encrypted_key,
            })
            self.add_message(f'[SYSTEM] Secure session key shared with {peer["name"]}.')
            self.update_status()
        except (OSError, TypeError, ValueError) as exc:
            self.clear_session_key(client_id, expected_key=session_key)
            self.add_message(f'[SYSTEM] Could not share secure key with {peer["name"]}: {exc}')
            self.update_status()

    def ensure_session_keys(self):
        for client_id in self.get_peer_snapshot():
            self.maybe_share_key_with_peer(client_id)

    def send_packet(self, packet):
        payload = json.dumps(packet, separators=(',', ':')).encode('utf-8') + b'\n'
        self.conn.sendall(payload)

    def send_chat_message(self, message):
        peers = self.get_peer_snapshot()
        if not peers:
            self.add_message('[SYSTEM] No connected peers.')
            return False

        pending = [peer['name'] for peer in peers.values() if not peer.get('session_key')]
        if pending:
            self.add_message('[SYSTEM] Secure key exchange is still in progress.')
            return False

        for client_id, peer in peers.items():
            encrypted = self.chacha.encrypt(message, peer['session_key'])
            self.send_packet({
                'type': 'encrypted_chat',
                'target_client_id': client_id,
                'nonce': encrypted['nonce'],
                'ciphertext': encrypted['ciphertext'],
                'tag': encrypted['tag'],
            })

        self.add_message(f'{self.name}: {message}')
        return True

    def handle_packet(self, packet):
        packet_type = packet.get('type', '')

        if packet_type == 'welcome':
            self.client_id = packet.get('client_id')
            self.server_public_key = str(packet.get('server_public_key', ''))
            proof = str(packet.get('proof', ''))

            try:
                decrypted = self.rsa.decrypt_from_base64(proof).decode('utf-8', errors='replace')
            except (TypeError, ValueError) as exc:
                self.add_message(f'[SYSTEM] RSA key exchange failed: {exc}')
                return

            if decrypted != f'client-{self.client_id}-ready':
                self.add_message('[SYSTEM] RSA proof from server did not match.')
                return

            if self.server_public_key:
                try:
                    confirm = self.rsa.encrypt_for_public_key(
                        f'server-ready:{self.client_id}',
                        self.server_public_key,
                    )
                    self.send_packet({'type': 'hello_confirm', 'proof': confirm})
                except (OSError, TypeError, ValueError) as exc:
                    self.add_message(f'[SYSTEM] RSA confirmation failed: {exc}')
                    return

            self.add_message('[SYSTEM] RSA-2048 key exchange complete.')
            self.update_status()
            return

        if packet_type == 'peer_list':
            peers = packet.get('peers', [])
            self.replace_peers(peers)
            if peers:
                self.add_message(f'[SYSTEM] Loaded {len(peers)} peer public key(s).')
            self.ensure_session_keys()
            self.update_status()
            return

        if packet_type == 'peer_joined':
            client_id = packet.get('client_id')
            name = str(packet.get('name', f'Client {client_id}'))
            public_key = str(packet.get('public_key', ''))
            if client_id is None or not public_key:
                return

            self.upsert_peer(client_id, name, public_key)
            self.add_message(f'[SYSTEM] {name} joined. RSA public key received.')
            self.maybe_share_key_with_peer(client_id)
            self.update_status()
            return

        if packet_type == 'peer_left':
            client_id = packet.get('client_id')
            name = self.remove_peer(client_id)
            if name is None:
                self.add_message(f'[SYSTEM] Client {client_id} disconnected.')
            else:
                self.add_message(f'[SYSTEM] {name} disconnected.')
            self.update_status()
            return

        if packet_type == 'key_exchange':
            sender_client_id = packet.get('client_id')
            sender_name = str(packet.get('from', f'Client {sender_client_id}'))
            encrypted_key = str(packet.get('encrypted_key', ''))
            if sender_client_id is None or not encrypted_key:
                return

            try:
                session_key = self.rsa.decrypt_from_base64(encrypted_key).decode('ascii')
                self.chacha.key_from_text(session_key)
            except (TypeError, ValueError) as exc:
                self.add_message(f'[SYSTEM] Could not load secure key from {sender_name}: {exc}')
                return

            self.set_session_key(sender_client_id, session_key, sender_name)
            self.add_message(f'[SYSTEM] Secure session key received from {sender_name}.')
            self.update_status()
            return

        if packet_type == 'encrypted_chat':
            sender_client_id = packet.get('client_id')
            sender = str(packet.get('from', 'Unknown'))
            peer = self.get_peer_info(sender_client_id)
            if peer is None or not peer.get('session_key'):
                self.add_message(f'[SYSTEM] Missing secure key for {sender}.')
                return

            try:
                message = self.chacha.decrypt(packet, peer['session_key']).decode('utf-8', errors='replace')
            except (TypeError, ValueError) as exc:
                self.add_message(f'[SYSTEM] Could not decrypt message from {sender}: {exc}')
                return

            self.add_message(f'{sender}: {message}')
            return

        if packet_type == 'system':
            self.add_message(f'[SYSTEM] {packet.get("message", "")}')
            return

    def connect(self):
        self.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.conn.connect((HOST, PORT))
        self.update_status()
        self.listener = threading.Thread(target=self.receive_messages, daemon=True)
        self.listener.start()
        try:
            self.send_packet({
                'type': 'hello',
                'name': self.name,
                'public_key': self.rsa.export_public_key(),
            })
        except OSError:
            self.close_connection()
            raise

    def receive_messages(self):
        buffer = ''

        try:
            while self.running:
                data = self.conn.recv(4096)
                if not data:
                    self.add_message('[SYSTEM] Server closed the connection.')
                    break

                buffer += data.decode('utf-8', errors='replace')
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if not line.strip():
                        continue

                    try:
                        packet = json.loads(line)
                    except json.JSONDecodeError:
                        self.add_message('[SYSTEM] Received malformed data from server.')
                        continue

                    try:
                        self.handle_packet(packet)
                    except (OSError, TypeError, ValueError) as exc:
                        self.add_message(f'[SYSTEM] Protocol error: {exc}')
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

    def prompt_for_ip(self, stdscr):
        buffer = ''

        while True:
            stdscr.erase()
            height, width = stdscr.getmaxyx()
            center_x = max(2, (width // 2) - 10)
            center_y = max(2, height // 2 - 2)

            safe_addstr(stdscr, center_y - 2, center_x, 'MATH 447 CHAT ROOM', curses.A_BOLD)
            safe_addstr(stdscr, center_y, 2, f'Enter IP (port {PORT}) and press ENTER:')
            draw_hline(stdscr, center_y + 1)
            visible = buffer[-max(1, width - 6):]
            safe_addstr(stdscr, center_y + 2, 2, f'> {visible}')
            safe_addstr(stdscr, height - 2, 2, 'Digits and dots only. Press Ctrl+C to exit.')

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
            elif key in (-1, curses.KEY_RESIZE):
                continue
            elif ord('0') <= key <= ord('9') or key == ord('.'):
                buffer += chr(key)

    def prompt_for_server(self, stdscr):
        stdscr.erase()
        height, width = stdscr.getmaxyx()
        center_x = max(2, (width // 2) - 14)
        center_y = max(2, height // 2 - 1)
        safe_addstr(stdscr, center_y - 2, center_x, 'MATH 447 CHAT ROOM', curses.A_BOLD)
        safe_addstr(stdscr, center_y, 2, 'Searching for chat servers on your LAN...')
        safe_addstr(stdscr, height - 2, 2, 'Please wait.')
        stdscr.refresh()

        servers = discover_servers()

        while True:
            stdscr.erase()
            height, width = stdscr.getmaxyx()
            center_x = max(2, (width // 2) - 10)
            top_y = max(2, height // 2 - 5)

            safe_addstr(stdscr, top_y - 2, center_x, 'MATH 447 CHAT ROOM', curses.A_BOLD)
            safe_addstr(stdscr, top_y, 2, 'Discovered Servers:')

            row = top_y + 2
            if servers:
                for index, server in enumerate(servers[:9], start=1):
                    safe_addstr(stdscr, row, 4, f'{index}. {server["ip"]}:{server["port"]}')
                    row += 1
            else:
                safe_addstr(stdscr, row, 4, 'No servers found.')
                row += 1

            draw_hline(stdscr, row + 1)
            safe_addstr(stdscr, row + 2, 2, 'Press 1-9 to select a server or M to enter an IP.')
            safe_addstr(stdscr, height - 2, 2, 'Press Ctrl+C to exit.')
            stdscr.refresh()

            key = stdscr.getch()
            if key in (-1, curses.KEY_RESIZE):
                continue
            if key in (ord('m'), ord('M')):
                return self.prompt_for_ip(stdscr)
            if ord('1') <= key <= ord('9'):
                index = key - ord('1')
                if index < len(servers):
                    return servers[index]['ip']

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
        global HOST

        try:
            curses.curs_set(1)
        except curses.error:
            pass
        stdscr.keypad(True)
        stdscr.timeout(POLL_MS)

        self.name = self.prompt_for_name(stdscr)
        HOST = self.prompt_for_server(stdscr)

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

                    try:
                        self.send_chat_message(message)
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
