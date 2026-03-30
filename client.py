#
# client.py
# Created: 03/30/2026
# Last Updated: 03/30/2026 by Aidan
#

import socket
import threading 

HOST='127.0.0.1'
PORT=65432

# Listen for incoming messages from the server
def receiveMessages(conn):
    try:
        while True:
            data = conn.recv(4096)
            if not data:
                break
            print(f"\n[RECEIVED] {data.decode()}")
    except ConnectionResetError:
        print("[DISCONNECTED] Lost connection to server")
    finally:
        conn.close()

def main():
    conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    conn.connect((HOST, PORT))
    print(f"[CONNECTED] Connected to {HOST}:{PORT}")

    listener = threading.Thread(target=receiveMessages, args=(conn,))
    listener.daemon = True 
    listener.start()

    try:
        while True:
            msg = input()
            if msg.lower() == '/quit':
                break
            conn.sendall(msg.encode())
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        conn.close()
        print("[DISCONNECTED] Connection closed")

if __name__ == '__main__':
    main()