#
# ChaCha.py
# Created: 04/07/2026
# Last Updated: 04/07/2026 by Aidan
#

import base64
import binascii

from Cryptodome.Cipher import ChaCha20_Poly1305
from Cryptodome.Random import get_random_bytes


class ChaChaCipher:
    def generate_key(self):
        return base64.b64encode(get_random_bytes(32)).decode('ascii')

    def key_from_text(self, key_text):
        try:
            key = base64.b64decode(key_text.encode('ascii'), validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError('Invalid ChaCha20-Poly1305 key.') from exc

        if len(key) != 32:
            raise ValueError('ChaCha20-Poly1305 key must be 32 bytes.')
        return key

    def encrypt(self, plaintext, key_text):
        if isinstance(plaintext, str):
            plaintext = plaintext.encode('utf-8')

        cipher = ChaCha20_Poly1305.new(key=self.key_from_text(key_text))
        ciphertext, tag = cipher.encrypt_and_digest(plaintext)
        return {
            'nonce': base64.b64encode(cipher.nonce).decode('ascii'),
            'ciphertext': base64.b64encode(ciphertext).decode('ascii'),
            'tag': base64.b64encode(tag).decode('ascii'),
        }

    def decrypt(self, payload, key_text):
        try:
            nonce = base64.b64decode(str(payload.get('nonce', '')).encode('ascii'), validate=True)
            ciphertext = base64.b64decode(str(payload.get('ciphertext', '')).encode('ascii'), validate=True)
            tag = base64.b64decode(str(payload.get('tag', '')).encode('ascii'), validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError('Invalid encrypted ChaCha20-Poly1305 payload.') from exc

        cipher = ChaCha20_Poly1305.new(
            key=self.key_from_text(key_text),
            nonce=nonce,
        )
        return cipher.decrypt_and_verify(ciphertext, tag)
