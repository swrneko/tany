from cryptography.fernet import Fernet

from app.crypto import decrypt_secret, encrypt_secret, mask_secret


def test_an_api_key_survives_a_round_trip_and_is_not_stored_in_the_clear() -> None:
    secret = Fernet.generate_key()

    stored = encrypt_secret("sk-proj-abcdefgh1234", secret)

    assert b"sk-proj" not in stored
    assert decrypt_secret(stored, secret) == "sk-proj-abcdefgh1234"


def test_masking_reveals_only_the_tail() -> None:
    assert mask_secret("sk-proj-abcdefgh1234") == "sk-…1234"


def test_masking_a_short_key_reveals_nothing() -> None:
    assert mask_secret("abcd") == "…"
