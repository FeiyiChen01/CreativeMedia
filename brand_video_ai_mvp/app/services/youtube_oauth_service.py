"""Google OAuth helpers for connecting a user's YouTube channel."""

import json
import os
from datetime import UTC, datetime, timedelta
from typing import Any

from app.models import SocialAccount
from app.services.token_crypto_service import decrypt_token, encrypt_token

TOKEN_URI = "https://oauth2.googleapis.com/token"
AUTH_URI = "https://accounts.google.com/o/oauth2/auth"
DEFAULT_SCOPE = "https://www.googleapis.com/auth/youtube.upload"


class YouTubeOAuthError(RuntimeError):
    """Raised when the YouTube OAuth flow cannot complete."""


def _scopes() -> list[str]:
    """Return configured OAuth scopes."""

    configured = os.getenv("GOOGLE_OAUTH_SCOPES", DEFAULT_SCOPE)
    return [scope.strip() for scope in configured.replace(",", " ").split() if scope.strip()]


def _client_config() -> dict[str, Any]:
    """Build a Google OAuth client config from environment variables."""

    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
    redirect_uri = os.getenv("GOOGLE_OAUTH_REDIRECT_URI", "http://localhost:8000/api/oauth/youtube/callback").strip()
    if not client_id or not client_secret:
        raise YouTubeOAuthError("GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are required for YouTube OAuth.")
    return {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": AUTH_URI,
            "token_uri": TOKEN_URI,
            "redirect_uris": [redirect_uri],
        }
    }


def _credentials_to_dict(credentials: object) -> dict[str, Any]:
    """Extract non-sensitive credential metadata and tokens."""

    return {
        "token": getattr(credentials, "token", None),
        "refresh_token": getattr(credentials, "refresh_token", None),
        "expiry": getattr(credentials, "expiry", None),
        "scopes": list(getattr(credentials, "scopes", None) or _scopes()),
    }


def build_youtube_auth_url(user_id: int, state: str) -> str:
    """Create the Google authorization URL for the server-side web flow."""

    from google_auth_oauthlib.flow import Flow

    flow = Flow.from_client_config(
        _client_config(),
        scopes=_scopes(),
        redirect_uri=os.getenv("GOOGLE_OAUTH_REDIRECT_URI", "http://localhost:8000/api/oauth/youtube/callback"),
    )
    auth_url, _state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=state,
    )
    return auth_url


def exchange_code_for_tokens(code: str) -> dict[str, Any]:
    """Exchange an OAuth authorization code for Google credentials."""

    from google_auth_oauthlib.flow import Flow

    flow = Flow.from_client_config(
        _client_config(),
        scopes=_scopes(),
        redirect_uri=os.getenv("GOOGLE_OAUTH_REDIRECT_URI", "http://localhost:8000/api/oauth/youtube/callback"),
    )
    try:
        flow.fetch_token(code=code)
    except Exception as exc:  # noqa: BLE001 - surface a safe OAuth error to the API layer.
        raise YouTubeOAuthError("Google OAuth code exchange failed.") from exc
    return _credentials_to_dict(flow.credentials)


def credentials_from_account(account: SocialAccount) -> object:
    """Create Google Credentials from an encrypted SocialAccount."""

    from google.oauth2.credentials import Credentials

    access_token = decrypt_token(account.access_token_encrypted)
    refresh_token = decrypt_token(account.refresh_token_encrypted)
    return Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri=TOKEN_URI,
        client_id=os.getenv("GOOGLE_CLIENT_ID", "").strip(),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET", "").strip(),
        scopes=_scopes(),
    )


def credentials_from_token_payload(token_payload: dict[str, Any]) -> object:
    """Create Google Credentials from freshly exchanged token data."""

    from google.oauth2.credentials import Credentials

    return Credentials(
        token=token_payload.get("token"),
        refresh_token=token_payload.get("refresh_token"),
        token_uri=TOKEN_URI,
        client_id=os.getenv("GOOGLE_CLIENT_ID", "").strip(),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET", "").strip(),
        scopes=token_payload.get("scopes") or _scopes(),
    )


def refresh_access_token_if_needed(account: SocialAccount) -> object:
    """Refresh the encrypted access token when it is missing or near expiry."""

    from google.auth.transport.requests import Request

    credentials = credentials_from_account(account)
    expires_at = account.token_expires_at
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)

    should_refresh = not getattr(credentials, "token", None)
    if expires_at:
        should_refresh = should_refresh or expires_at <= datetime.now(UTC) + timedelta(minutes=5)
    if not should_refresh:
        return credentials

    try:
        credentials.refresh(Request())
    except Exception as exc:  # noqa: BLE001 - callers update account status.
        raise YouTubeOAuthError("YouTube access token refresh failed.") from exc

    account.access_token_encrypted = encrypt_token(getattr(credentials, "token", None))
    if getattr(credentials, "refresh_token", None):
        account.refresh_token_encrypted = encrypt_token(getattr(credentials, "refresh_token", None))
    account.token_expires_at = getattr(credentials, "expiry", None)
    account.connection_status = "connected"
    account.updated_at = datetime.now(UTC)
    return credentials


def get_youtube_channel_profile(credentials: object) -> dict[str, Any]:
    """Fetch the connected user's primary YouTube channel profile."""

    from googleapiclient.discovery import build

    youtube = build("youtube", "v3", credentials=credentials)
    try:
        response = youtube.channels().list(part="snippet", mine=True).execute()
    except Exception as exc:  # noqa: BLE001 - keep provider details out of logs/errors.
        raise YouTubeOAuthError("Could not fetch YouTube channel profile.") from exc

    items = response.get("items") or []
    if not items:
        raise YouTubeOAuthError("No YouTube channel was found for this Google account.")

    channel = items[0]
    snippet = channel.get("snippet") or {}
    return {
        "platform_user_id": channel.get("id"),
        "platform_account_name": snippet.get("title"),
        "account_url": f"https://www.youtube.com/channel/{channel.get('id')}" if channel.get("id") else None,
        "metadata": {
            "description": snippet.get("description"),
            "published_at": snippet.get("publishedAt"),
            "thumbnails": snippet.get("thumbnails"),
        },
        "raw": response,
    }


def serialize_scopes(scopes: list[str] | tuple[str, ...] | None = None) -> str:
    """Serialize scopes as JSON text for the SocialAccount row."""

    return json.dumps(list(scopes or _scopes()), ensure_ascii=False)
