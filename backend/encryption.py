"""Simple API key encryption at rest using HMAC-based obfuscation.

Keys are obfuscated before storing in the database and de-obfuscated when read.
Uses XOR with a PBKDF2-derived keystream from SECRET_KEY.
No external dependencies required.
"""

import base64
import hashlib
import logging

logger = logging.getLogger(__name__)

_keystream_cache = None


def _get_keystream(length=256):
    """Derive a repeatable keystream from SECRET_KEY via PBKDF2."""
    global _keystream_cache
    if _keystream_cache is not None and len(_keystream_cache) >= length:
        return _keystream_cache

    from config import SECRET_KEY
    salt = b'fitcoach-api-key-encryption-v1'
    # Generate enough keystream bytes
    blocks = []
    for i in range((length // 32) + 1):
        dk = hashlib.pbkdf2_hmac('sha256', SECRET_KEY.encode(), salt + i.to_bytes(4, 'big'), 100_000)
        blocks.append(dk)
    _keystream_cache = b''.join(blocks)
    return _keystream_cache


def encrypt_api_key(plaintext: str) -> str:
    """Encrypt an API key for storage using XOR obfuscation."""
    try:
        data = plaintext.encode()
        ks = _get_keystream(len(data))
        xored = bytes(a ^ b for a, b in zip(data, ks))
        return 'enc:' + base64.urlsafe_b64encode(xored).decode()
    except Exception:
        logger.warning('Failed to encrypt API key, storing plaintext')
        return plaintext


def decrypt_api_key(stored: str) -> str:
    """Decrypt an API key from storage. Returns as-is if not encrypted."""
    if not stored.startswith('enc:'):
        return stored
    try:
        xored = base64.urlsafe_b64decode(stored[4:])
        ks = _get_keystream(len(xored))
        data = bytes(a ^ b for a, b in zip(xored, ks))
        return data.decode()
    except Exception:
        logger.warning('Failed to decrypt API key, returning raw value')
        return stored[4:]
