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
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("GOOGLE_OAUTH_REDIRECT_URI", "http://testserver/api/oauth/youtube/callback")
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", "test-token-encryption-key")
    monkeypatch.setenv("YOUTUBE_UPLOAD_ALLOW_PUBLIC", "false")

    from app import database
    from app.database import Base, get_db
    from app.main import app
    from app import models  # noqa: F401

    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=Session)
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(database, "SessionLocal", TestingSessionLocal)

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


def test_admin_user_actions_log_changes(client):
    user = register(client, "managed@example.com", "manageduser")
    admin = register(client, "admin@example.com", "adminuser")
    admin_headers = auth_headers(admin["access_token"])

    updated = client.patch(
        f"/api/admin/users/{user['user']['id']}",
        headers=admin_headers,
        json={"is_active": False, "role": "admin", "email_verified": True},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["is_active"] is False
    assert updated.json()["role"] == "admin"
    assert updated.json()["email_verified"] is True

    logs = client.get("/api/admin/action-logs", headers=admin_headers)
    assert logs.status_code == 200
    assert any(log["action"] == "update_user" and log["target_id"] == str(user["user"]["id"]) for log in logs.json())


def test_generate_outline_and_prompts_persist(client):
    token = register(client, "gen@example.com", "genuser")["access_token"]
    headers = auth_headers(token)

    questionnaire = client.post(
        "/api/questionnaire",
        headers=headers,
        json={
            "brand_name": "Luna Bloom",
            "brand_description": "Modern jewelry",
            "target_audience": "young professionals",
            "video_style": "专业商务风",
            "additional_info": {"campaign": "spring launch"},
        },
    )
    assert questionnaire.status_code == 200
    questionnaire_id = questionnaire.json()["id"]

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
            "generated_outline_id": outline_data["generated_outline_id"],
        },
    )
    assert prompt_response.status_code == 200, prompt_response.text
    prompt_data = prompt_response.json()
    assert prompt_data["generated_prompt_package_id"]

    assert len(client.get("/api/generated/outlines", headers=headers).json()) == 1
    assert len(client.get("/api/generated/prompts", headers=headers).json()) == 1

    from app.models import ApiUsageLog, GeneratedOutline, GeneratedPromptPackage, GenerationJob

    with client.testing_session_local() as db:  # type: ignore[attr-defined]
        outline = db.get(GeneratedOutline, outline_data["generated_outline_id"])
        package = db.get(GeneratedPromptPackage, prompt_data["generated_prompt_package_id"])
        outline_job = db.get(GenerationJob, outline_data["generation_job_id"])
        prompt_job = db.get(GenerationJob, prompt_data["generation_job_id"])
        usage_rows = db.scalars(select(ApiUsageLog)).all()

    assert outline.questionnaire_id == questionnaire_id
    assert package.questionnaire_id == questionnaire_id
    assert package.outline_id == outline.id
    assert outline_job.output_json and "generated_outline_id" in outline_job.output_json
    assert prompt_job.output_json and "generated_prompt_package_id" in prompt_job.output_json
    assert {row.operation for row in usage_rows} >= {"generate_outline", "generate_prompts"}


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

    from app.main import run_video_generation_job

    run_video_generation_job(job_id)

    from app.models import ApiUsageLog, VideoAsset

    with client.testing_session_local() as db:  # type: ignore[attr-defined]
        asset = db.scalar(select(VideoAsset).where(VideoAsset.generation_job_id == job_id))
        usage = db.scalar(select(ApiUsageLog).where(ApiUsageLog.generation_job_id == job_id))

    assert asset is not None
    assert asset.storage_backend == "local"
    assert usage is not None
    assert usage.operation == "generate_video"


def test_register_email_delivery_failure_returns_structured_error(client, monkeypatch):
    from app import main

    def fail_send(_user, _db):
        raise RuntimeError("SMTP failure")

    monkeypatch.setattr(main, "send_verification_for_user", fail_send)
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


def test_youtube_oauth_connect_requires_login(client):
    response = client.get("/api/oauth/youtube/connect")
    assert response.status_code == 401


def test_youtube_oauth_connect_returns_auth_url(client, monkeypatch):
    from app import main

    token = register(client, "ytconnect@example.com", "ytconnect")["access_token"]
    monkeypatch.setattr(
        main.youtube_oauth_service,
        "build_youtube_auth_url",
        lambda user_id, state: f"https://accounts.google.com/o/oauth2/auth?state={state}&user={user_id}",
    )

    response = client.get("/api/oauth/youtube/connect", headers=auth_headers(token))

    assert response.status_code == 200, response.text
    assert response.json()["auth_url"].startswith("https://accounts.google.com/")


def test_youtube_oauth_callback_invalid_state_redirects_failed(client):
    response = client.get(
        "/api/oauth/youtube/callback",
        params={"code": "code", "state": "invalid"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"] == "/?youtube_connected=failed"


def test_youtube_upload_rejects_other_users_video_asset(client, tmp_path):
    owner = register(client, "asset-owner@example.com", "assetowner")
    other = register(client, "asset-other@example.com", "assetother")
    other_asset_id, _other_account_id = create_video_asset_and_account(client, other["user"]["id"], tmp_path)
    _owner_asset_id, owner_account_id = create_video_asset_and_account(client, owner["user"]["id"], tmp_path)

    response = client.post(
        "/api/youtube/shorts/upload",
        headers=auth_headers(owner["access_token"]),
        json={
            "video_asset_id": other_asset_id,
            "social_account_id": owner_account_id,
            "title": "Forbidden asset",
            "privacy_status": "private",
        },
    )

    assert response.status_code == 403


def test_youtube_upload_rejects_other_users_social_account(client, tmp_path):
    owner = register(client, "acct-owner@example.com", "acctowner")
    other = register(client, "acct-other@example.com", "acctother")
    owner_asset_id, _owner_account_id = create_video_asset_and_account(client, owner["user"]["id"], tmp_path)
    _other_asset_id, other_account_id = create_video_asset_and_account(client, other["user"]["id"], tmp_path)

    response = client.post(
        "/api/youtube/shorts/upload",
        headers=auth_headers(owner["access_token"]),
        json={
            "video_asset_id": owner_asset_id,
            "social_account_id": other_account_id,
            "title": "Forbidden account",
            "privacy_status": "private",
        },
    )

    assert response.status_code == 403


def test_youtube_upload_requires_connected_youtube_account(client, tmp_path):
    user = register(client, "manual-youtube@example.com", "manualyt")
    asset_id, account_id = create_video_asset_and_account(client, user["user"]["id"], tmp_path, connected=False)

    response = client.post(
        "/api/youtube/shorts/upload",
        headers=auth_headers(user["access_token"]),
        json={
            "video_asset_id": asset_id,
            "social_account_id": account_id,
            "title": "Needs OAuth",
            "privacy_status": "private",
        },
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "YOUTUBE_ACCOUNT_NOT_CONNECTED"


def test_youtube_upload_missing_video_file_fails(client, tmp_path):
    from app.models import VideoAsset

    user = register(client, "missing-video@example.com", "missingvideo")
    asset_id, account_id = create_video_asset_and_account(client, user["user"]["id"], tmp_path)
    with client.testing_session_local() as db:  # type: ignore[attr-defined]
        asset = db.get(VideoAsset, asset_id)
        asset.file_path = str(tmp_path / "missing.mp4")
        db.commit()

    response = client.post(
        "/api/youtube/shorts/upload",
        headers=auth_headers(user["access_token"]),
        json={
            "video_asset_id": asset_id,
            "social_account_id": account_id,
            "title": "Missing file",
            "privacy_status": "private",
        },
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "VIDEO_FILE_INVALID"


def test_youtube_upload_success_creates_success_publishing_job(client, tmp_path, monkeypatch):
    from app import main

    user = register(client, "upload-success@example.com", "uploadsuccess")
    asset_id, account_id = create_video_asset_and_account(client, user["user"]["id"], tmp_path)

    monkeypatch.setattr(
        main.youtube_upload_service,
        "upload_video_to_youtube",
        lambda **_kwargs: {"video_id": "abc123", "watch_url": "https://www.youtube.com/watch?v=abc123", "response": {"id": "abc123"}},
    )

    response = client.post(
        "/api/youtube/shorts/upload",
        headers=auth_headers(user["access_token"]),
        json={
            "video_asset_id": asset_id,
            "social_account_id": account_id,
            "title": "Success Short",
            "description": "Generated by OmniSocial AI",
            "tags": ["shorts", "ai"],
            "privacy_status": "private",
            "contains_synthetic_media": True,
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "success"
    assert body["provider_post_id"] == "abc123"
    assert body["provider_post_url"] == "https://www.youtube.com/watch?v=abc123"


def test_youtube_upload_failure_creates_failed_publishing_job(client, tmp_path, monkeypatch):
    from app import main

    user = register(client, "upload-fail@example.com", "uploadfail")
    asset_id, account_id = create_video_asset_and_account(client, user["user"]["id"], tmp_path)

    def fail_upload(**_kwargs):
        raise RuntimeError("provider rejected upload")

    monkeypatch.setattr(main.youtube_upload_service, "upload_video_to_youtube", fail_upload)

    response = client.post(
        "/api/youtube/shorts/upload",
        headers=auth_headers(user["access_token"]),
        json={
            "video_asset_id": asset_id,
            "social_account_id": account_id,
            "title": "Failed Short",
            "privacy_status": "private",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "failed"
    assert body["error_message"] == "provider rejected upload"


def test_publishing_jobs_are_scoped_to_current_user(client, tmp_path, monkeypatch):
    from app import main

    first = register(client, "jobs-one@example.com", "jobsone")
    second = register(client, "jobs-two@example.com", "jobstwo")
    first_asset_id, first_account_id = create_video_asset_and_account(client, first["user"]["id"], tmp_path)
    second_asset_id, second_account_id = create_video_asset_and_account(client, second["user"]["id"], tmp_path)

    monkeypatch.setattr(
        main.youtube_upload_service,
        "upload_video_to_youtube",
        lambda **kwargs: {
            "video_id": f"video-{kwargs['video_asset'].id}",
            "watch_url": f"https://www.youtube.com/watch?v=video-{kwargs['video_asset'].id}",
            "response": {"id": f"video-{kwargs['video_asset'].id}"},
        },
    )

    client.post(
        "/api/youtube/shorts/upload",
        headers=auth_headers(first["access_token"]),
        json={"video_asset_id": first_asset_id, "social_account_id": first_account_id, "title": "First", "privacy_status": "private"},
    )
    client.post(
        "/api/youtube/shorts/upload",
        headers=auth_headers(second["access_token"]),
        json={"video_asset_id": second_asset_id, "social_account_id": second_account_id, "title": "Second", "privacy_status": "private"},
    )

    response = client.get("/api/publishing-jobs", headers=auth_headers(first["access_token"]))

    assert response.status_code == 200
    jobs = response.json()
    assert len(jobs) == 1
    assert jobs[0]["title"] == "First"
