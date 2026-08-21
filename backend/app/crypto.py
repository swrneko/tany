from cryptography.fernet import Fernet

VISIBLE_HEAD = 3
VISIBLE_TAIL = 4


def encrypt_secret(value: str, key: bytes) -> bytes:
    return Fernet(key).encrypt(value.encode())


def decrypt_secret(token: bytes, key: bytes) -> str:
    return Fernet(key).decrypt(token).decode()


def mask_secret(value: str) -> str:
    """What the API returns in place of a key. It never returns the key itself,
    not even to the admin who typed it in -- a masked value is enough to tell
    two providers apart, which is the only reason to show it at all."""
    if len(value) <= VISIBLE_HEAD + VISIBLE_TAIL:
        return "…"
    return f"{value[:VISIBLE_HEAD]}…{value[-VISIBLE_TAIL:]}"
