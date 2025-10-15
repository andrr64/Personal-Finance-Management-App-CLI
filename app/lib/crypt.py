# app/lib/crypt.py

import os
import base64
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

# ==============================
# Helper Enkripsi & Hashing
# ==============================


def derive_key(password: str, salt: bytes) -> bytes:
    """Derives a 32-byte encryption key from a password and salt using PBKDF2."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100_000,
        backend=default_backend()
    )
    return kdf.derive(password.encode())


def encrypt(data: str, password: str) -> str:
    """Encrypts data using AES-CFB mode with a derived key."""
    if not data:
        return ""
    salt = os.urandom(16)
    key = derive_key(password, salt)
    iv = os.urandom(16)
    cipher = Cipher(algorithms.AES(key), modes.CFB(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    ct = encryptor.update(data.encode()) + encryptor.finalize()
    # Prepend salt and IV to the ciphertext for later decryption
    return base64.b64encode(salt + iv + ct).decode()


def decrypt(enc_data: str, password: str) -> str:
    """Decrypts data that was encrypted with the corresponding master password."""
    if not enc_data:
        return ""
    try:
        raw = base64.b64decode(enc_data)
        salt, iv, ct = raw[:16], raw[16:32], raw[32:]
        key = derive_key(password, salt)
        cipher = Cipher(algorithms.AES(key), modes.CFB(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        return (decryptor.update(ct) + decryptor.finalize()).decode()
    except Exception:
        # Return a specific error string if decryption fails (e.g., wrong password)
        return "DECRYPTION_ERROR"
