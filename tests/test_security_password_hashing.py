"""Password hashing and JWT integrity tests."""

from datetime import timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.core.jwt import create_access_token, decode_access_token
from app.core.security import (
    MAX_PASSWORD_BYTES,
    PasswordTooLongError,
    hash_password,
    validate_password,
    verify_password,
)
from app.models.user import User

from tests.conftest import register_user, unique_email

PLAIN = "Str0ngPassw0rd!"


# ── Password hashing ─────────────────────────────────────────────────────


def test_hash_is_not_the_plaintext() -> None:
    hashed = hash_password(PLAIN)
    assert hashed != PLAIN
    assert PLAIN not in hashed


def test_hash_is_bcrypt_format() -> None:
    hashed = hash_password(PLAIN)
    assert hashed.startswith(("$2a$", "$2b$", "$2y$"))


def test_same_password_hashes_differently_each_time() -> None:
    assert hash_password(PLAIN) != hash_password(PLAIN)


def test_correct_password_verifies() -> None:
    assert verify_password(PLAIN, hash_password(PLAIN)) is True


def test_wrong_password_does_not_verify() -> None:
    assert verify_password("Wr0ngPassw0rd!", hash_password(PLAIN)) is False


def test_empty_values_do_not_verify() -> None:
    assert verify_password("", hash_password(PLAIN)) is False
    assert verify_password(PLAIN, "") is False


def test_malformed_hash_does_not_verify() -> None:
    assert verify_password(PLAIN, "not-a-bcrypt-hash") is False


def test_short_password_is_rejected() -> None:
    with pytest.raises(ValueError):
        validate_password("Ab1!")


def test_password_over_72_bytes_is_rejected_explicitly() -> None:
    """bcrypt truncates past 72 bytes, so the limit is enforced up front."""
    too_long = "a" * (MAX_PASSWORD_BYTES + 1)
    with pytest.raises(PasswordTooLongError):
        hash_password(too_long)


def test_password_at_exactly_72_bytes_is_accepted() -> None:
    assert len("a" * MAX_PASSWORD_BYTES) == MAX_PASSWORD_BYTES
    hashed = hash_password("a" * MAX_PASSWORD_BYTES)
    assert verify_password("a" * MAX_PASSWORD_BYTES, hashed) is True


def test_plaintext_password_is_never_persisted(client: TestClient, db) -> None:
    email = unique_email("noplain")
    register_user(client, email=email, password=PLAIN)

    user = db.execute(select(User).where(User.email == email)).scalar_one()
    assert user.hashed_password != PLAIN
    assert PLAIN not in user.hashed_password
    assert user.hashed_password.startswith("$2")


def test_api_never_returns_the_password_hash(client: TestClient) -> None:
    body = register_user(client)
    assert "hashed_password" not in body["user"]
    assert "password" not in body["user"]


# ── JWT integrity ────────────────────────────────────────────────────────


def test_access_token_decodes_to_its_subject() -> None:
    token = create_access_token(subject="11111111-1111-1111-1111-111111111111")
    payload = decode_access_token(token)
    assert payload["sub"] == "11111111-1111-1111-1111-111111111111"
    assert payload["type"] == "access"
    assert payload["iss"] == settings.jwt_issuer
    assert payload["aud"] == settings.jwt_audience


def test_token_carries_exp_and_jti() -> None:
    payload = decode_access_token(create_access_token(subject="abc"))
    assert "exp" in payload and "iat" in payload and "jti" in payload


def test_tampered_signature_is_rejected() -> None:
    token = create_access_token(subject="abc")
    header, payload, signature = token.split(".")
    forged = f"{header}.{payload}.{signature[:-4]}AAAA"
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(forged)


def test_tampered_payload_is_rejected() -> None:
    token = create_access_token(subject="abc")
    header, payload, signature = token.split(".")
    forged = f"{header}.{payload}x.{signature}"
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(forged)


def test_unsigned_alg_none_token_is_rejected() -> None:
    forged = jwt.encode(
        {"sub": "abc", "type": "access", "iss": settings.jwt_issuer,
         "aud": settings.jwt_audience},
        key="",
        algorithm="none",
    )
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(forged)


def test_token_signed_with_wrong_key_is_rejected() -> None:
    forged = jwt.encode(
        {
            "sub": "abc",
            "type": "access",
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "exp": 9999999999,
        },
        key="a-completely-different-signing-key-value-x",
        algorithm="HS256",
    )
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(forged)


def test_expired_token_is_rejected() -> None:
    expired = create_access_token(
        subject="abc", expires_delta=timedelta(minutes=-5)
    )
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(expired)
