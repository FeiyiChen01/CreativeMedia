"""Phase 4-10 integration tests using an isolated SQLite database."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker


@pytest.fixture()
def client(tmp_path, monkeypatch) -> Generator[TestClient, None, None]:
    """Create a FastAPI client backed by a temporary SQLite database."""

    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("APP_BASE_URL", "http://testserver")
    monkeypatch.setenv("ALLOW_MOCK_AI", "true")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("ADMIN_EMAILS", "admin@example.com")

    from app.database import Base, get_db
    from app.main import app
    from app import models  # noqa: F401

    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=Session)
    Base.metadata.create_all(bind=engine)

    def override_get_db() -> Generator[Session, None, None]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        test_client.testing_session_local = TestingSessionLocal  # type: ignore[attr-defined]
        yield test_client
    app.dependency_overrides.clear()


def register(client: TestClient, email: str, username: str, password: str = "Passw0rd!") -> dict:
    response = client.post(
        "/api/auth/register",
        json={
            "email": email,
            "username": username,
            "password": password,
            "password_confirm": password,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def login(client: TestClient, email: str, password: str = "Passw0rd!") -> dict:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def outline_payload() -> dict:
    return {
        "questionnaire": {
            "brand_name": "Luna Bloom",
            "industry": "Jewelry",
            "target_audience": "young professionals",
            "brand_keywords": ["premium", "warm", "modern"],
            "promotion_theme": "spring launch",
            "video_length": "15-30 seconds",
            "language": "en",
        }
    }


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


def test_email_verification_token_flow(client, monkeypatch):
    from app import main

    monkeypatch.setattr(main.secrets, "token_urlsafe", lambda _size: "verify-token-long-enough")
    register(client, "verify@example.com", "verifyuser")

    response = client.get("/api/auth/verify-email", params={"token": "verify-token-long-enough"})
    assert response.status_code == 200

    logged_in = login(client, "verify@example.com")
    me = client.get("/api/auth/me", headers=auth_headers(logged_in["access_token"]))
    assert me.json()["email_verified"] is True


def test_password_reset_flow(client, monkeypatch):
    from app import main

    register(client, "reset@example.com", "resetuser")
    monkeypatch.setattr(main.secrets, "token_urlsafe", lambda _size: "reset-token-long-enough")
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


def test_profile_get_update_and_change_password(client):
    token = register(client, "profile@example.com", "profileuser")["access_token"]
    headers = auth_headers(token)

    profile = client.get("/api/profile", headers=headers)
    assert profile.status_code == 200

    updated = client.patch(
        "/api/profile",
        headers=headers,
        json={"username": "profileuser2", "full_name": "Profile User", "company_name": "Acme", "avatar_url": ""},
    )
    assert updated.status_code == 200
    assert updated.json()["username"] == "profileuser2"

    changed = client.post(
        "/api/profile/change-password",
        headers=headers,
        json={
            "current_password": "Passw0rd!",
            "new_password": "Changed1!",
            "new_password_confirm": "Changed1!",
        },
    )
    assert changed.status_code == 200
    assert login(client, "profile@example.com", "Changed1!")["access_token"]


def test_admin_protection_metrics_and_system_prompts(client):
    user_token = register(client, "normal@example.com", "normaluser")["access_token"]
    admin_token = register(client, "admin@example.com", "adminuser")["access_token"]

    assert client.get("/api/admin/metrics", headers=auth_headers(user_token)).status_code == 403
    assert client.get("/api/system-prompts", headers=auth_headers(user_token)).status_code == 403

    metrics = client.get("/api/admin/metrics", headers=auth_headers(admin_token))
    assert metrics.status_code == 200
    assert metrics.json()["total_users"] == 2
    assert client.get("/api/system-prompts", headers=auth_headers(admin_token)).status_code == 200


def test_generate_outline_and_prompts_persist(client):
    token = register(client, "gen@example.com", "genuser")["access_token"]
    headers = auth_headers(token)

    outline_response = client.post("/api/generate-outline", headers=headers, json=outline_payload())
    assert outline_response.status_code == 200, outline_response.text
    outline_data = outline_response.json()
    assert outline_data["generated_outline_id"]
    assert outline_data["generation_job_id"]

    prompt_response = client.post(
        "/api/generate-prompts",
        headers=headers,
        json={
            "questionnaire": outline_payload()["questionnaire"],
            "outline": outline_data["outline"],
            "target_tool": "sora-2",
        },
    )
    assert prompt_response.status_code == 200, prompt_response.text
    prompt_data = prompt_response.json()
    assert prompt_data["generated_prompt_package_id"]

    assert len(client.get("/api/generated/outlines", headers=headers).json()) == 1
    assert len(client.get("/api/generated/prompts", headers=headers).json()) == 1


def test_video_job_create_and_access_control(client):
    owner_token = register(client, "owner@example.com", "owneruser")["access_token"]
    other_token = register(client, "other@example.com", "otheruser")["access_token"]
    admin_token = register(client, "admin@example.com", "adminuser")["access_token"]

    created = client.post(
        "/api/video-jobs",
        headers=auth_headers(owner_token),
        json={"prompt_en": "A clean product shot", "duration_seconds": 4, "scene_number": 1},
    )
    assert created.status_code == 201, created.text
    job_id = created.json()["job_id"]

    owner_status = client.get(f"/api/video-jobs/{job_id}", headers=auth_headers(owner_token))
    assert owner_status.status_code == 200
    assert owner_status.json()["user_id"]

    assert client.get(f"/api/video-jobs/{job_id}", headers=auth_headers(other_token)).status_code == 403
    assert client.get(f"/api/video-jobs/{job_id}", headers=auth_headers(admin_token)).status_code == 200
