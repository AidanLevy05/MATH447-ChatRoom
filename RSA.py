#
# RSA.py
# Created: 04/07/2026
# Last Updated: 04/07/2026 by Codex
#

import base64
import binascii

from Cryptodome.Cipher import PKCS1_OAEP
from Cryptodome.PublicKey import RSA as CryptoRSA


class RSAKeyExchange:
    def __init__(self, key_size=2048):
        self.private_key = CryptoRSA.generate(key_size)
        self.public_key = self.private_key.publickey()

    def export_public_key(self):
        return self.public_key.export_key().decode('utf-8')

    def import_public_key(self, public_key_text):
        return CryptoRSA.import_key(public_key_text.encode('utf-8'))

    def encrypt_for_public_key(self, plaintext, public_key_text):
        if isinstance(plaintext, str):
            plaintext = plaintext.encode('utf-8')

        cipher = PKCS1_OAEP.new(self.import_public_key(public_key_text))
        encrypted = cipher.encrypt(plaintext)
        return base64.b64encode(encrypted).decode('ascii')

    def decrypt_from_base64(self, ciphertext):
        try:
            encrypted = base64.b64decode(ciphertext.encode('ascii'), validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError('Invalid RSA ciphertext.') from exc

        cipher = PKCS1_OAEP.new(self.private_key)
        return cipher.decrypt(encrypted)
