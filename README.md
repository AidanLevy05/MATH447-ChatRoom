# MATH447 Final Project

Aidan, Maddie, Lei

# Idea

- Project: End to end encrypted chatroom
- Idea: 2 clients and 1 server.
- Language: Python
- Libraries: socket, Cryptodome
- Messages use RSA-2048 for key exchange
- Message encryption is ChaCha20-Poly1305

# Goals

1. ~~Implement server.py~~
2. ~~Implement client.py~~
3. ~~Ensure connection works with multiple clients~~
4. ~~Create chat server~~
5. ~~Implement RSA-2048 key exchange~~
6. ~~Step 3~~
7. ~~Implement ChaCha20-Poly1305 for message encryption~~
8. ~~Step 3~~
9. ~~Run program, ensure that server cannot read the encrypted messages~~
10. ~~Have an encrypted verion and un-encrypted version to show the server reading or not reading the messages~~

# Run Modes

- Encrypted version: `python3 server.py` and `python3 client.py`
- Plaintext version: `python3 plain_server.py` and `python3 plain_client.py`
