"""Password hashing and credential validation.

Passwords are hashed with bcrypt and only the hash is ever stored. bcrypt
silently truncates anything past 72 bytes, so the byte length is validated
explicitly here instead of letting a long password be quietly cut down or raise
a library error.
"""

import bcrypt

from app.core.config import settings

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_BYTES = 72


class PasswordTooLongError(ValueError):
    """Raised when a password exceeds bcrypt's hard 72-byte input limit."""


def validate_password(password: str) -> None:
    """Reject passwords that cannot be safely hashed."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters long."
        )
    encoded = password.encode("utf-8")
    if len(encoded) > MAX_PASSWORD_BYTES:
        raise PasswordTooLongError(
            f"Password must be at most {MAX_PASSWORD_BYTES} bytes when UTF-8 "
            f"encoded, got {len(encoded)} bytes."
        )


def hash_password(password: str) -> str:
    """Return a bcrypt hash of the given plaintext password."""
    validate_password(password)
    hashed = bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt(rounds=settings.bcrypt_rounds),
    )
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check a plaintext password against a stored bcrypt hash."""
    if not plain_password or not hashed_password:
        return False
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False
