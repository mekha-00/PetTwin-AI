"""Authentication and account services.

Keeps hashing, credential verification and user persistence out of the routers.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.jwt import create_access_token
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.user import UserCreate


class EmailAlreadyRegisteredError(Exception):
    """Raised when a registration collides with an existing email."""


class InvalidCredentialsError(Exception):
    """Raised when an email/password pair does not match."""


class InactiveUserError(Exception):
    """Raised when a valid credential belongs to a deactivated account."""


def get_user_by_email(db: Session, email: str) -> User | None:
    stmt = select(User).where(User.email == email.strip().lower())
    return db.execute(stmt).scalar_one_or_none()


def get_user_by_id(db: Session, user_id) -> User | None:
    return db.get(User, user_id)


def create_user(db: Session, payload: UserCreate) -> User:
    """Register a new user, storing only the bcrypt hash of the password."""
    existing = get_user_by_email(db, payload.email)
    if existing is not None:
        raise EmailAlreadyRegisteredError(payload.email)

    user = User(
        email=payload.email.strip().lower(),
        full_name=payload.full_name,
        phone=payload.phone,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        clinic_name=payload.clinic_name,
        is_active=True,
        is_verified=False,
        password_changed_at=datetime.now(timezone.utc),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise EmailAlreadyRegisteredError(payload.email) from exc
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User:
    """Verify credentials and return the user.

    Raises the same error for an unknown email and a wrong password, so the
    endpoint cannot be used to discover which emails are registered.
    """
    user = get_user_by_email(db, email)
    if user is None or not verify_password(password, user.hashed_password):
        raise InvalidCredentialsError
    if not user.is_active:
        raise InactiveUserError
    return user


def record_login(db: Session, user: User) -> None:
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()


def issue_access_token(user: User) -> tuple[str, int]:
    """Return a fresh access token and its lifetime in seconds."""
    expires_in = settings.access_token_expire_minutes * 60
    token = create_access_token(subject=str(user.id))
    return token, expires_in
