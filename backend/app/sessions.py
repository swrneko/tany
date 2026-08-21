import uuid

from itsdangerous import BadSignature, URLSafeTimedSerializer

SESSION_SALT = "transcribe-anything.session"


class SessionSigner:
    """Stateless signed session cookies.

    No JWT in localStorage: there is nothing distributed here to justify it, and
    localStorage is an XSS hole by default. A signed httpOnly cookie is enough.
    """

    def __init__(self, secret: bytes, max_age_days: int) -> None:
        self._serializer = URLSafeTimedSerializer(secret, salt=SESSION_SALT)
        self.max_age_seconds = max_age_days * 24 * 60 * 60

    def issue(self, user_id: uuid.UUID) -> str:
        return self._serializer.dumps(str(user_id))

    def read(self, token: str) -> uuid.UUID | None:
        try:
            return uuid.UUID(self._serializer.loads(token, max_age=self.max_age_seconds))
        except (BadSignature, ValueError):
            return None
