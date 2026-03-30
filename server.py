#
# server.py
# Created: 03/30/2026
# Last Updated: 03/30/2026 by Aidan
#

import socket
import threading 

HOST='127.0.0.1'
PORT=65432

clients=[]


# Receive messages from one client and forward to another
def handleClient(conn, addr, clientID):
    print(f"[CLIENT {clientID}] Connected from {addr}")
    try:
        while True:
            data = conn.recv(4096)  
            if not data:
                break
            print(f"[CLIENT {clientID}] {len(data)} bytes | {data}")
            for c in clients:
                if c is not conn:
                    c.sendall(data)
    except ConnectionResetError:
        print(f"[CLIENT {clientID}] Disconnected")
    finally:
        conn.close()

def welcome():
    print("=========================================")
    print()
    print("            MATH 447 CHAT ROOM           ")
    print("                 server.py               ")
    print()
    print("=========================================\n")

def main():

    welcome()

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(2)
    print(f"[SERVER] Listening on: {HOST}:{PORT}")

    clientID = 0
    while len(clients) < 2:
        conn, addr = server.accept()
        clients.append(conn)
        clientID += 1
        thread = threading.Thread(target=handleClient, args=(conn, addr, clientID))
        thread.daemon = True
        thread.start()

    print("[SERVER] Both clients connected. Relaying messages.")

    for thread in threading.enumerate():
        if thread is not threading.main_thread():
            thread.join()

    server.close()

if __name__ == '__main__':
    main()