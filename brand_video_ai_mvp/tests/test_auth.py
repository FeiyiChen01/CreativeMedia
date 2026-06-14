"""Authentication and account security tests."""

import pytest

from conftest import auth_headers, login, register

def test_register_login_duplicate_and_me(client):
    registered = register(client, "user@example.com", "userone")
    assert registered["user"]["email"] == "user@example.com"
    assert registered["user"]["email_verified"] is False

    duplicate = client.post(
        "/api/auth/register",
        json={
            "email": "user@example.com",
            "username": "userone2",
            "password": "Passw0rd!",
            "password_confirm": "Passw0rd!",
        },
    )
    assert duplicate.status_code == 400

    logged_in = login(client, "user@example.com")
    me = client.get("/api/auth/me", headers=auth_headers(logged_in["access_token"]))
    assert me.status_code == 200
    assert me.json()["username"] == "userone"


def test_register_accepts_email_style_username(client):
    response = client.post(
        "/api/auth/register",
        json={
            "email": "normal@test.com",
            "username": "normal@test.com",
            "password": "Passw0rd!",
            "password_confirm": "Passw0rd!",
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["user"]["username"] == "normal@test.com"


def test_register_validation_error_is_json_serializable(client):
    response = client.post(
        "/api/auth/register",
        json={
            "email": "invalid-user@test.com",
            "username": "bad username!",
            "password": "Passw0rd!",
            "password_confirm": "Passw0rd!",
        },
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error_code"] == "VALIDATION_ERROR"
    assert body["errors"][0]["ctx"]["error"] == "Username can only contain letters, numbers, underscores, hyphens, @, and periods."


def test_email_verification_token_flow(client, monkeypatch):
    from app import core

    monkeypatch.setattr(core.secrets, "token_urlsafe", lambda _size: "verify-token-long-enough")
    register(client, "verify@example.com", "verifyuser")

    response = client.get("/api/auth/verify-email", params={"token": "verify-token-long-enough"})
    assert response.status_code == 200

    logged_in = login(client, "verify@example.com")
    me = client.get("/api/auth/me", headers=auth_headers(logged_in["access_token"]))
    assert me.json()["email_verified"] is True


def test_password_reset_flow(client, monkeypatch):
    from app import core

    register(client, "reset@example.com", "resetuser")
    monkeypatch.setattr(core.secrets, "token_urlsafe", lambda _size: "reset-token-long-enough")
    forgot = client.post("/api/auth/forgot-password", json={"email": "reset@example.com"})
    assert forgot.status_code == 200

    reset = client.post(
        "/api/auth/reset-password",
        json={
            "token": "reset-token-long-enough",
            "new_password": "Newpass1!",
            "new_password_confirm": "Newpass1!",
        },
    )
    assert reset.status_code == 200
    assert client.post("/api/auth/login", json={"email": "reset@example.com", "password": "Passw0rd!"}).status_code == 401
    assert login(client, "reset@example.com", "Newpass1!")["access_token"]


def test_register_email_delivery_failure_returns_structured_error(client, monkeypatch):
    from app.routers import auth

    def fail_send(_user, _db):
        raise RuntimeError("SMTP failure")

    monkeypatch.setattr(auth, "send_verification_for_user", fail_send)
    response = client.post(
        "/api/auth/register",
        json={
            "email": "mailfail@example.com",
            "username": "mailfail",
            "password": "Passw0rd!",
            "password_confirm": "Passw0rd!",
        },
    )
    assert response.status_code == 503
    assert response.json()["error_code"] == "EMAIL_DELIVERY_FAILED"


def test_production_requires_smtp(monkeypatch):
    from app.services.email_service import EmailService

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SMTP_FROM_EMAIL", raising=False)

    with pytest.raises(RuntimeError, match="SMTP is required in production for email verification."):
        EmailService().require_production_config()

