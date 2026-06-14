"""Shared pytest fixtures and helpers for API integration tests."""

from collections.abc import Generator
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture()
def client(tmp_path, monkeypatch) -> Generator[TestClient, None, None]:
    """Create a FastAPI client backed by a temporary SQLite database."""

    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("APP_BASE_URL", "http://testserver")
    monkeypatch.setenv("ALLOW_MOCK_AI", "true")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("ADMIN_EMAILS", "admin@example.com")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("GOOGLE_OAUTH_REDIRECT_URI", "http://testserver/api/oauth/youtube/callback")
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", "test-token-encryption-key")
    monkeypatch.setenv("YOUTUBE_UPLOAD_ALLOW_PUBLIC", "false")

    from app import core, database, main
    from app import models  # noqa: F401
    from app.database import Base, get_db
    from app.main import app

    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=Session)
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(database, "SessionLocal", TestingSessionLocal)
    upload_static_dir = tmp_path / "static"
    upload_static_dir.mkdir()
    monkeypatch.setattr(main, "STATIC_DIR", upload_static_dir)
    monkeypatch.setattr(core, "STATIC_DIR", upload_static_dir)

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


def create_video_asset_and_account(client, user_id: int, tmp_path, *, connected: bool = True):
    """Create an owned video asset and YouTube account directly in the test DB."""

    from app.models import GenerationJob, SocialAccount, VideoAsset

    video_file = tmp_path / f"video-{user_id}.mp4"
    video_file.write_bytes(b"fake mp4 bytes")

    with client.testing_session_local() as db:  # type: ignore[attr-defined]
        job = GenerationJob(user_id=user_id, job_type="video", status="success", provider="mock")
        db.add(job)
        db.flush()
        asset = VideoAsset(
            user_id=user_id,
            generation_job_id=job.id,
            file_path=str(video_file),
            status="completed",
            storage_backend="local",
        )
        account = SocialAccount(
            user_id=user_id,
            platform="youtube",
            account_url="https://www.youtube.com/channel/test",
            account_handle="Test Channel",
            platform_user_id=f"channel-{user_id}",
            platform_account_name="Test Channel",
            connection_status="connected" if connected else "manual",
        )
        db.add_all([asset, account])
        db.commit()
        db.refresh(asset)
        db.refresh(account)
        return asset.id, account.id
