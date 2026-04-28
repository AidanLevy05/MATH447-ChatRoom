# MATH447 Final Project

Aidan, Maddie, Lei

## Project

This project is an end-to-end encrypted chat room written in Python. It includes two runnable versions:

- Encrypted chat: messages are protected with RSA-2048 key exchange and ChaCha20-Poly1305 message encryption.
- Un-encrypted chat: messages are sent as plaintext so the server can display readable chat messages.

The encrypted version is useful for showing that the server can relay messages without being able to read the plaintext. The un-encrypted version is useful as a comparison because the server log displays the actual messages.

## Files

- `server.py`: starts the encrypted chat server.
- `client.py`: starts an encrypted chat client.
- `plain_server.py`: starts the un-encrypted plaintext chat server.
- `plain_client.py`: starts an un-encrypted plaintext chat client.
- `ChatServer.py` and `ChatClient.py`: encrypted chat implementation.
- `PlainChatServer.py` and `PlainChatClient.py`: plaintext chat implementation.
- `RSA.py`: RSA-2048 key exchange helper.
- `ChaCha.py`: ChaCha20-Poly1305 encryption helper.

## Requirements

- Python 3
- `pycryptodomex`
- A terminal that supports `curses`

Install the crypto dependency with:

```bash
python3 -m pip install pycryptodomex
```

## Notes

- Run each server and each client in a separate terminal window.
- Start the server before starting clients.
- To stop a server, press `q` in the server terminal.
- To leave a client, type `/quit` and press Enter.
- For a demo, open at least three terminals: one server and two clients.

## Run The Encrypted Chat

Use three separate terminals.

Terminal 1, encrypted server:

```bash
python3 server.py
```

Terminal 2, first encrypted client:

```bash
python3 client.py
```

Terminal 3, second encrypted client:

```bash
python3 client.py
```

When each encrypted client starts, enter your name. The client will search for servers on the local network. Select a discovered server by number, or press `M` to manually enter the server IP address.

## Run The Un-Encrypted Chat

Use three separate terminals.

Terminal 1, un-encrypted server:

```bash
python3 plain_server.py
```

Terminal 2, first un-encrypted client:

```bash
python3 plain_client.py
```

Terminal 3, second un-encrypted client:

```bash
python3 plain_client.py
```

When each un-encrypted client starts, enter your name. The plaintext version connects to `127.0.0.1:65433`, so run the plaintext server and clients on the same computer.
