"""YouTube OAuth and publishing tests."""

from conftest import auth_headers, create_video_asset_and_account, register

def test_youtube_oauth_connect_requires_login(client):
    response = client.get("/api/oauth/youtube/connect")
    assert response.status_code == 401


def test_youtube_oauth_connect_returns_auth_url(client, monkeypatch):
    from app.routers import social_youtube

    token = register(client, "ytconnect@example.com", "ytconnect")["access_token"]
    monkeypatch.setattr(
        social_youtube.youtube_oauth_service,
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
    from app.routers import social_youtube

    user = register(client, "upload-success@example.com", "uploadsuccess")
    asset_id, account_id = create_video_asset_and_account(client, user["user"]["id"], tmp_path)

    monkeypatch.setattr(
        social_youtube.youtube_upload_service,
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
    from app.routers import social_youtube

    user = register(client, "upload-fail@example.com", "uploadfail")
    asset_id, account_id = create_video_asset_and_account(client, user["user"]["id"], tmp_path)

    def fail_upload(**_kwargs):
        raise RuntimeError("provider rejected upload")

    monkeypatch.setattr(social_youtube.youtube_upload_service, "upload_video_to_youtube", fail_upload)

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
    from app.routers import social_youtube

    first = register(client, "jobs-one@example.com", "jobsone")
    second = register(client, "jobs-two@example.com", "jobstwo")
    first_asset_id, first_account_id = create_video_asset_and_account(client, first["user"]["id"], tmp_path)
    second_asset_id, second_account_id = create_video_asset_and_account(client, second["user"]["id"], tmp_path)

    monkeypatch.setattr(
        social_youtube.youtube_upload_service,
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
