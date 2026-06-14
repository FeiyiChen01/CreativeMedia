"""YouTube dashboard API tests."""

from datetime import UTC, datetime, timedelta
import json

from conftest import auth_headers, register


READONLY_SCOPES = json.dumps([
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
])
UPLOAD_ONLY_SCOPES = json.dumps(["https://www.googleapis.com/auth/youtube.upload"])


def create_youtube_account(client, user_id: int, *, scopes: str = READONLY_SCOPES, connected: bool = True):
    """Create a YouTube social account directly in the test DB."""

    from app.models import SocialAccount

    with client.testing_session_local() as db:  # type: ignore[attr-defined]
        account = SocialAccount(
            user_id=user_id,
            platform="youtube",
            account_url=f"https://www.youtube.com/channel/channel-{user_id}",
            account_handle="Test Channel",
            platform_user_id=f"channel-{user_id}",
            platform_account_name=f"Channel {user_id}",
            connection_status="connected" if connected else "manual",
            scopes=scopes,
            token_expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        db.add(account)
        db.commit()
        db.refresh(account)
        return account.id


def test_get_youtube_dashboard_requires_login(client):
    response = client.get("/api/dashboard/youtube")

    assert response.status_code == 401


def test_get_youtube_dashboard_without_connection_returns_empty_state(client):
    user = register(client, "dash-empty@example.com", "dashempty")

    response = client.get("/api/dashboard/youtube", headers=auth_headers(user["access_token"]))

    assert response.status_code == 200
    body = response.json()
    assert body["connected"] is False
    assert body["reconnect_required"] is False
    assert body["channel_metrics"] is None
    assert body["recent_videos"] == []


def test_get_youtube_dashboard_connected_without_metrics(client):
    user = register(client, "dash-connected@example.com", "dashconnected")
    create_youtube_account(client, user["user"]["id"])

    response = client.get("/api/dashboard/youtube", headers=auth_headers(user["access_token"]))

    assert response.status_code == 200
    body = response.json()
    assert body["connected"] is True
    assert body["reconnect_required"] is False
    assert body["channel_metrics"] is None
    assert "Click refresh" in body["message"]


def test_get_youtube_dashboard_scope_missing_returns_reconnect_required(client):
    user = register(client, "dash-scope@example.com", "dashscope")
    create_youtube_account(client, user["user"]["id"], scopes=UPLOAD_ONLY_SCOPES)

    response = client.get("/api/dashboard/youtube", headers=auth_headers(user["access_token"]))

    assert response.status_code == 200
    body = response.json()
    assert body["connected"] is True
    assert body["reconnect_required"] is True
    assert body["channel_metrics"] is None


def test_get_youtube_dashboard_returns_cached_channel_metrics(client):
    from app.models import YouTubeChannelMetric

    user = register(client, "dash-metrics@example.com", "dashmetrics")
    account_id = create_youtube_account(client, user["user"]["id"])
    synced_at = datetime.now(UTC)
    with client.testing_session_local() as db:  # type: ignore[attr-defined]
        db.add(
            YouTubeChannelMetric(
                user_id=user["user"]["id"],
                social_account_id=account_id,
                channel_id="UCcached",
                channel_title="Cached Channel",
                subscriber_count=1200,
                video_count=42,
                view_count=56000,
                synced_at=synced_at,
            )
        )
        db.commit()

    response = client.get("/api/dashboard/youtube", headers=auth_headers(user["access_token"]))

    assert response.status_code == 200
    metrics = response.json()["channel_metrics"]
    assert metrics["subscriber_count"] == 1200
    assert metrics["video_count"] == 42
    assert metrics["view_count"] == 56000


def test_get_youtube_dashboard_only_returns_current_users_metrics(client):
    from app.models import YouTubeChannelMetric

    first = register(client, "dash-owner@example.com", "dashowner")
    second = register(client, "dash-other@example.com", "dashother")
    first_account_id = create_youtube_account(client, first["user"]["id"])
    second_account_id = create_youtube_account(client, second["user"]["id"])
    synced_at = datetime.now(UTC)
    with client.testing_session_local() as db:  # type: ignore[attr-defined]
        db.add_all([
            YouTubeChannelMetric(
                user_id=first["user"]["id"],
                social_account_id=first_account_id,
                channel_id="UCfirst",
                channel_title="First Channel",
                subscriber_count=10,
                synced_at=synced_at,
            ),
            YouTubeChannelMetric(
                user_id=second["user"]["id"],
                social_account_id=second_account_id,
                channel_id="UCsecond",
                channel_title="Second Channel",
                subscriber_count=9999,
                synced_at=synced_at,
            ),
        ])
        db.commit()

    response = client.get("/api/dashboard/youtube", headers=auth_headers(first["access_token"]))

    assert response.status_code == 200
    assert response.json()["channel_metrics"]["channel_id"] == "UCfirst"


def test_refresh_youtube_dashboard_requires_login(client):
    response = client.post("/api/dashboard/youtube/refresh")

    assert response.status_code == 401


def test_refresh_youtube_dashboard_without_connection_returns_400(client):
    user = register(client, "dash-refresh-empty@example.com", "dashrefreshempty")

    response = client.post("/api/dashboard/youtube/refresh", headers=auth_headers(user["access_token"]))

    assert response.status_code == 400
    assert response.json()["error_code"] == "YOUTUBE_ACCOUNT_NOT_CONNECTED"


def test_refresh_youtube_dashboard_scope_missing_returns_reconnect_error(client):
    user = register(client, "dash-refresh-scope@example.com", "dashrefreshscope")
    create_youtube_account(client, user["user"]["id"], scopes=UPLOAD_ONLY_SCOPES)

    response = client.post("/api/dashboard/youtube/refresh", headers=auth_headers(user["access_token"]))

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "YOUTUBE_RECONNECT_REQUIRED"
    assert body["reconnect_required"] is True


def test_refresh_youtube_dashboard_calls_token_refresh_and_saves_metrics(client, monkeypatch):
    from app.models import YouTubeChannelMetric, YouTubeVideoMetric
    from app.services import youtube_dashboard_service

    user = register(client, "dash-refresh@example.com", "dashrefresh")
    account_id = create_youtube_account(client, user["user"]["id"])
    calls = {"refresh": 0}

    def mock_refresh(_account):
        calls["refresh"] += 1
        return object()

    monkeypatch.setattr(youtube_dashboard_service.youtube_oauth_service, "refresh_access_token_if_needed", mock_refresh)
    monkeypatch.setattr(youtube_dashboard_service, "fetch_youtube_channel_and_recent_videos", lambda _credentials: mock_youtube_payload())

    response = client.post("/api/dashboard/youtube/refresh", headers=auth_headers(user["access_token"]))

    assert response.status_code == 200, response.text
    body = response.json()
    assert calls["refresh"] == 1
    assert body["channel_metrics"]["channel_id"] == "UC123"
    assert body["recent_videos"][0]["provider_video_id"] == "video123"
    with client.testing_session_local() as db:  # type: ignore[attr-defined]
        assert db.query(YouTubeChannelMetric).filter_by(social_account_id=account_id).count() == 1
        assert db.query(YouTubeVideoMetric).filter_by(social_account_id=account_id).count() == 1


def test_refresh_youtube_dashboard_replaces_recent_video_cache(client, monkeypatch):
    from app.models import YouTubeVideoMetric
    from app.services import youtube_dashboard_service

    user = register(client, "dash-refresh-replace@example.com", "dashrefreshreplace")
    account_id = create_youtube_account(client, user["user"]["id"])
    monkeypatch.setattr(youtube_dashboard_service.youtube_oauth_service, "refresh_access_token_if_needed", lambda _account: object())
    monkeypatch.setattr(youtube_dashboard_service, "fetch_youtube_channel_and_recent_videos", lambda _credentials: mock_youtube_payload())

    headers = auth_headers(user["access_token"])
    first = client.post("/api/dashboard/youtube/refresh", headers=headers)
    second = client.post("/api/dashboard/youtube/refresh", headers=headers)

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert len(second.json()["recent_videos"]) == 1
    with client.testing_session_local() as db:  # type: ignore[attr-defined]
        assert db.query(YouTubeVideoMetric).filter_by(social_account_id=account_id).count() == 1


def test_refresh_youtube_dashboard_token_refresh_failure_marks_account_expired(client, monkeypatch):
    from app.models import SocialAccount
    from app.services import youtube_dashboard_service
    from app.services.youtube_oauth_service import YouTubeOAuthError

    user = register(client, "dash-token-fail@example.com", "dashtokenfail")
    account_id = create_youtube_account(client, user["user"]["id"])

    def fail_refresh(_account):
        raise YouTubeOAuthError("refresh failed")

    monkeypatch.setattr(youtube_dashboard_service.youtube_oauth_service, "refresh_access_token_if_needed", fail_refresh)

    response = client.post("/api/dashboard/youtube/refresh", headers=auth_headers(user["access_token"]))

    assert response.status_code == 401
    assert response.json()["error_code"] == "YOUTUBE_TOKEN_REFRESH_FAILED"
    with client.testing_session_local() as db:  # type: ignore[attr-defined]
        assert db.get(SocialAccount, account_id).connection_status == "expired"


def test_refresh_youtube_dashboard_missing_like_and_comment_counts(client, monkeypatch):
    from app.services import youtube_dashboard_service

    user = register(client, "dash-missing-counts@example.com", "dashmissingcounts")
    create_youtube_account(client, user["user"]["id"])
    monkeypatch.setattr(youtube_dashboard_service.youtube_oauth_service, "refresh_access_token_if_needed", lambda _account: object())

    payload = mock_youtube_payload()
    payload["videos"][0]["statistics"].pop("likeCount")
    payload["videos"][0]["statistics"].pop("commentCount")
    monkeypatch.setattr(youtube_dashboard_service, "fetch_youtube_channel_and_recent_videos", lambda _credentials: payload)

    response = client.post("/api/dashboard/youtube/refresh", headers=auth_headers(user["access_token"]))

    assert response.status_code == 200, response.text
    video = response.json()["recent_videos"][0]
    assert video["like_count"] is None
    assert video["comment_count"] is None


def test_refresh_youtube_dashboard_no_items_does_not_crash(client, monkeypatch):
    from app.services import youtube_dashboard_service

    user = register(client, "dash-no-items@example.com", "dashnoitems")
    create_youtube_account(client, user["user"]["id"])
    monkeypatch.setattr(youtube_dashboard_service.youtube_oauth_service, "refresh_access_token_if_needed", lambda _account: object())
    monkeypatch.setattr(
        youtube_dashboard_service,
        "fetch_youtube_channel_and_recent_videos",
        lambda _credentials: {"channel": None, "videos": [], "raw": {"channel": {"items": []}}},
    )

    response = client.post("/api/dashboard/youtube/refresh", headers=auth_headers(user["access_token"]))

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["connected"] is True
    assert body["channel_metrics"] is None
    assert body["recent_videos"] == []


def test_refresh_youtube_dashboard_provider_failure_returns_502(client, monkeypatch):
    from app.services import youtube_dashboard_service

    user = register(client, "dash-provider-fail@example.com", "dashproviderfail")
    create_youtube_account(client, user["user"]["id"])
    monkeypatch.setattr(youtube_dashboard_service.youtube_oauth_service, "refresh_access_token_if_needed", lambda _account: object())

    def fail_fetch(_credentials):
        raise youtube_dashboard_service.YouTubeDashboardError("provider unavailable")

    monkeypatch.setattr(youtube_dashboard_service, "fetch_youtube_channel_and_recent_videos", fail_fetch)

    response = client.post("/api/dashboard/youtube/refresh", headers=auth_headers(user["access_token"]))

    assert response.status_code == 502
    assert response.json()["error_code"] == "YOUTUBE_DASHBOARD_PROVIDER_ERROR"


def test_user_cannot_read_other_users_youtube_metrics(client):
    from app.models import YouTubeChannelMetric

    first = register(client, "dash-isolate-one@example.com", "dashisolateone")
    second = register(client, "dash-isolate-two@example.com", "dashisolatetwo")
    create_youtube_account(client, first["user"]["id"])
    second_account_id = create_youtube_account(client, second["user"]["id"])
    with client.testing_session_local() as db:  # type: ignore[attr-defined]
        db.add(
            YouTubeChannelMetric(
                user_id=second["user"]["id"],
                social_account_id=second_account_id,
                channel_id="UCprivate",
                channel_title="Private Channel",
                subscriber_count=12345,
                synced_at=datetime.now(UTC),
            )
        )
        db.commit()

    response = client.get("/api/dashboard/youtube", headers=auth_headers(first["access_token"]))

    assert response.status_code == 200
    assert response.json()["channel_metrics"] is None


def mock_youtube_payload():
    """Return a representative YouTube Data API payload."""

    return {
        "channel": {
            "id": "UC123",
            "snippet": {"title": "Demo Channel"},
            "statistics": {
                "subscriberCount": "1200",
                "videoCount": "42",
                "viewCount": "56000",
            },
            "contentDetails": {"relatedPlaylists": {"uploads": "UU123"}},
        },
        "videos": [
            {
                "id": "video123",
                "snippet": {
                    "title": "My Short",
                    "publishedAt": "2026-06-14T12:00:00Z",
                    "thumbnails": {"high": {"url": "https://img.youtube.com/video123.jpg"}},
                },
                "statistics": {
                    "viewCount": "1000",
                    "likeCount": "50",
                    "commentCount": "8",
                },
            }
        ],
        "raw": {"channel": {"items": []}, "playlist_items": {"items": []}, "videos": {"items": []}},
    }
