from pathlib import Path

from cryptography.fernet import Fernet


def load_or_create_secret(path: Path) -> bytes:
    """Return the instance secret, generating it on first start.

    The key sits next to the data it protects, which guards against leaking
    provider API keys through a database backup -- not against an attacker who
    already has the filesystem. That trade-off is deliberate: for self-hosting,
    a zero-step install beats cryptographic purity. See README.
    """
    if path.exists():
        return path.read_bytes()

    key = Fernet.generate_key()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(key)
    path.chmod(0o600)
    return key
