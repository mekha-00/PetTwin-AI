"""Authentication endpoints: registration and login."""

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.user import TokenWithUser, UserCreate, UserLogin, UserRead
from app.services.auth_service import (
    EmailAlreadyRegisteredError,
    InactiveUserError,
    InvalidCredentialsError,
    authenticate_user,
    create_user,
    issue_access_token,
    record_login,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=TokenWithUser,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new account",
)
def register(payload: UserCreate, db: DbSession) -> TokenWithUser:
    """Create an account and return a token, so the client can start a session."""
    try:
        user = create_user(db, payload)
    except EmailAlreadyRegisteredError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with that email already exists",
        ) from exc

    token, expires_in = issue_access_token(user)
    return TokenWithUser(
        access_token=token,
        expires_in=expires_in,
        user=UserRead.model_validate(user),
    )


@router.post(
    "/login",
    response_model=TokenWithUser,
    summary="Exchange credentials for an access token",
)
def login(payload: UserLogin, db: DbSession) -> TokenWithUser:
    try:
        user = authenticate_user(db, payload.email, payload.password)
    except InactiveUserError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        ) from exc
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    record_login(db, user)
    token, expires_in = issue_access_token(user)
    return TokenWithUser(
        access_token=token,
        expires_in=expires_in,
        user=UserRead.model_validate(user),
    )


@router.get(
    "/me",
    response_model=UserRead,
    summary="Current authenticated user",
)
def read_current_user(current_user: CurrentUser) -> UserRead:
    return UserRead.model_validate(current_user)
