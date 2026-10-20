"""Registration, login and credential validation tests."""

from fastapi.testclient import TestClient

from tests.conftest import auth_header, register_user, unique_email

PASSWORD = "Str0ngPassw0rd!"


# ── Registration ─────────────────────────────────────────────────────────


def test_register_returns_token_and_user(client: TestClient) -> None:
    email = unique_email("reg")
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": PASSWORD, "full_name": "Ada"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["expires_in"] > 0
    assert body["user"]["email"] == email
    assert body["user"]["role"] == "pet_owner"


def test_registered_token_authenticates_immediately(client: TestClient) -> None:
    body = register_user(client)
    response = client.get("/api/auth/me", headers=auth_header(body["access_token"]))
    assert response.status_code == 200
    assert response.json()["email"] == body["user"]["email"]


def test_duplicate_email_is_rejected(client: TestClient) -> None:
    email = unique_email("dup")
    register_user(client, email=email)
    response = client.post(
        "/api/auth/register", json={"email": email, "password": PASSWORD}
    )
    assert response.status_code == 409


def test_email_is_normalised_to_lowercase(client: TestClient) -> None:
    email = unique_email("Mixed")
    body = register_user(client, email=email.upper())
    assert body["user"]["email"] == email.lower()


def test_invalid_email_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/auth/register", json={"email": "not-an-email", "password": PASSWORD}
    )
    assert response.status_code == 422


def test_short_password_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/auth/register", json={"email": unique_email("short"), "password": "Ab1!"}
    )
    assert response.status_code == 422


def test_password_over_72_bytes_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/auth/register",
        json={"email": unique_email("long"), "password": "a" * 73},
    )
    assert response.status_code == 422


def test_oversized_full_name_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/auth/register",
        json={
            "email": unique_email("longname"),
            "password": PASSWORD,
            "full_name": "x" * 500,
        },
    )
    assert response.status_code == 422


def test_missing_password_is_rejected(client: TestClient) -> None:
    response = client.post("/api/auth/register", json={"email": unique_email("nopw")})
    assert response.status_code == 422


# ── Login ────────────────────────────────────────────────────────────────


def test_login_with_correct_credentials(client: TestClient) -> None:
    email = unique_email("login")
    register_user(client, email=email)
    response = client.post(
        "/api/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert response.status_code == 200
    assert response.json()["access_token"]


def test_login_with_wrong_password_is_401(client: TestClient) -> None:
    email = unique_email("badpw")
    register_user(client, email=email)
    response = client.post(
        "/api/auth/login", json={"email": email, "password": "Wr0ngPassw0rd!"}
    )
    assert response.status_code == 401


def test_login_with_unknown_email_is_401(client: TestClient) -> None:
    """Same status as a wrong password, so registered emails stay undisclosed."""
    response = client.post(
        "/api/auth/login",
        json={"email": "nobody@example.com", "password": PASSWORD},
    )
    assert response.status_code == 401


def test_login_rejects_blank_password(client: TestClient) -> None:
    email = unique_email("blank")
    register_user(client, email=email)
    response = client.post(
        "/api/auth/login", json={"email": email, "password": ""}
    )
    assert response.status_code in (401, 422)


def test_login_with_inactive_account_is_403(client: TestClient, db) -> None:
    from sqlalchemy import select

    from app.models.user import User

    email = unique_email("inactive")
    register_user(client, email=email)

    user = db.execute(select(User).where(User.email == email)).scalar_one()
    user.is_active = False
    db.commit()

    login = client.post(
        "/api/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert login.status_code == 403


def test_inactive_user_token_is_403_on_protected_route(client: TestClient, db) -> None:
    from sqlalchemy import select

    from app.models.user import User

    email = unique_email("deactivated")
    body = register_user(client, email=email)
    token = body["access_token"]

    user = db.execute(select(User).where(User.email == email)).scalar_one()
    user.is_active = False
    db.commit()

    response = client.get("/api/users/me", headers=auth_header(token))
    assert response.status_code == 403
