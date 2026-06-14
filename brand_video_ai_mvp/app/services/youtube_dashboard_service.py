"""YouTube dashboard metric sync and read helpers."""

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import model_to_json, utc_now
from app.models import SocialAccount, YouTubeChannelMetric, YouTubeVideoMetric
from app.schemas import (
    YouTubeChannelMetricResponse,
    YouTubeDashboardResponse,
    YouTubeSocialAccountSummary,
    YouTubeVideoMetricResponse,
)
from app.services import youtube_oauth_service
from app.services.youtube_oauth_service import YouTubeOAuthError

YOUTUBE_READONLY_SCOPE = "https://www.googleapis.com/auth/youtube.readonly"


class YouTubeDashboardError(RuntimeError):
    """Raised when YouTube dashboard data cannot be synced."""


class YouTubeDashboardReconnectRequired(YouTubeDashboardError):
    """Raised when a connected account lacks read permissions."""


class YouTubeDashboardTokenRefreshError(YouTubeDashboardError):
    """Raised when a connected account token cannot be refreshed."""


def _parse_scope_text(scopes: str | None) -> list[str]:
    """Parse JSON, comma-delimited, or whitespace-delimited scope text."""

    if not scopes:
        return []
    cleaned = scopes.strip()
    if not cleaned:
        return []
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, list):
            return [str(scope).strip() for scope in parsed if str(scope).strip()]
        if isinstance(parsed, str):
            cleaned = parsed
    except json.JSONDecodeError:
        pass
    return [scope.strip() for scope in cleaned.replace(",", " ").split() if scope.strip()]


def account_has_readonly_scope(account: SocialAccount) -> bool:
    """Return whether the account has YouTube readonly scope."""

    return YOUTUBE_READONLY_SCOPE in _parse_scope_text(account.scopes)


def get_connected_youtube_account(db: Session, user_id: int) -> SocialAccount | None:
    """Return the current user's connected YouTube account."""

    return db.scalar(
        select(SocialAccount)
        .where(
            SocialAccount.user_id == user_id,
            SocialAccount.platform == "youtube",
            SocialAccount.connection_status == "connected",
        )
        .order_by(SocialAccount.updated_at.desc(), SocialAccount.linked_at.desc(), SocialAccount.id.desc())
    )


def _latest_channel_metric(db: Session, account: SocialAccount) -> YouTubeChannelMetric | None:
    """Return the latest cached channel metric for an account."""

    return db.scalar(
        select(YouTubeChannelMetric)
        .where(
            YouTubeChannelMetric.user_id == account.user_id,
            YouTubeChannelMetric.social_account_id == account.id,
        )
        .order_by(YouTubeChannelMetric.synced_at.desc(), YouTubeChannelMetric.id.desc())
    )


def _recent_video_metrics(db: Session, account: SocialAccount, limit: int = 10) -> list[YouTubeVideoMetric]:
    """Return cached recent video metrics for an account."""

    return list(
        db.scalars(
            select(YouTubeVideoMetric)
            .where(
                YouTubeVideoMetric.user_id == account.user_id,
                YouTubeVideoMetric.social_account_id == account.id,
            )
            .order_by(
                YouTubeVideoMetric.published_at.desc().nullslast(),
                YouTubeVideoMetric.synced_at.desc(),
                YouTubeVideoMetric.id.desc(),
            )
            .limit(limit)
        ).all()
    )


def build_dashboard_response(db: Session, user_id: int) -> YouTubeDashboardResponse:
    """Build dashboard state from cached database rows only."""

    account = get_connected_youtube_account(db, user_id)
    if account is None:
        return YouTubeDashboardResponse(
            connected=False,
            reconnect_required=False,
            social_account=None,
            channel_metrics=None,
            recent_videos=[],
            message="Connect YouTube to monitor your Shorts performance.",
        )

    account_summary = YouTubeSocialAccountSummary.model_validate(account)
    if not account_has_readonly_scope(account):
        return YouTubeDashboardResponse(
            connected=True,
            reconnect_required=True,
            social_account=account_summary,
            channel_metrics=None,
            recent_videos=[],
            message="Please reconnect YouTube to enable analytics access.",
        )

    channel_metric = _latest_channel_metric(db, account)
    recent_videos = _recent_video_metrics(db, account)
    return YouTubeDashboardResponse(
        connected=True,
        reconnect_required=False,
        social_account=account_summary,
        channel_metrics=YouTubeChannelMetricResponse.model_validate(channel_metric) if channel_metric else None,
        recent_videos=[YouTubeVideoMetricResponse.model_validate(video) for video in recent_videos],
        message=None if channel_metric else "Click refresh to sync your latest YouTube channel metrics.",
    )


def _parse_int(value: object) -> int | None:
    """Parse an integer metric value returned by YouTube."""

    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_datetime(value: str | None) -> datetime | None:
    """Parse YouTube RFC3339 datetime strings into timezone-aware datetimes."""

    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _best_thumbnail_url(thumbnails: dict[str, Any] | None) -> str | None:
    """Return the best available thumbnail URL."""

    if not thumbnails:
        return None
    for key in ("maxres", "standard", "high", "medium", "default"):
        thumbnail = thumbnails.get(key) or {}
        url = thumbnail.get("url")
        if url:
            return str(url)
    return None


def fetch_youtube_channel_and_recent_videos(credentials: object) -> dict[str, Any]:
    """Fetch the connected channel and recent video metrics from YouTube Data API."""

    from googleapiclient.discovery import build

    youtube = build("youtube", "v3", credentials=credentials)
    try:
        channel_response = youtube.channels().list(
            part="snippet,statistics,contentDetails",
            mine=True,
        ).execute()
        channel_items = channel_response.get("items") or []
        if not channel_items:
            return {"channel": None, "videos": [], "raw": {"channel": channel_response, "playlist_items": None, "videos": None}}

        channel = channel_items[0]
        content_details = channel.get("contentDetails") or {}
        related_playlists = content_details.get("relatedPlaylists") or {}
        uploads_playlist_id = related_playlists.get("uploads")

        playlist_response = None
        videos_response = None
        video_ids: list[str] = []
        if uploads_playlist_id:
            playlist_response = youtube.playlistItems().list(
                playlistId=uploads_playlist_id,
                part="snippet,contentDetails",
                maxResults=10,
            ).execute()
            for item in playlist_response.get("items") or []:
                video_id = ((item.get("contentDetails") or {}).get("videoId") or "").strip()
                if video_id:
                    video_ids.append(video_id)

        video_items = []
        if video_ids:
            videos_response = youtube.videos().list(
                part="snippet,statistics",
                id=",".join(video_ids),
            ).execute()
            video_items = videos_response.get("items") or []

        return {
            "channel": channel,
            "videos": video_items,
            "raw": {
                "channel": channel_response,
                "playlist_items": playlist_response,
                "videos": videos_response,
            },
        }
    except Exception as exc:  # noqa: BLE001 - provider details are intentionally hidden from API callers.
        raise YouTubeDashboardError("Could not fetch YouTube dashboard data.") from exc


def refresh_youtube_dashboard(db: Session, account: SocialAccount) -> YouTubeDashboardResponse:
    """Refresh YouTube dashboard data for a connected account and return cached state."""

    if not account_has_readonly_scope(account):
        raise YouTubeDashboardReconnectRequired("Please reconnect YouTube to enable analytics access.")

    try:
        credentials = youtube_oauth_service.refresh_access_token_if_needed(account)
    except YouTubeOAuthError as exc:
        account.connection_status = "expired"
        account.updated_at = utc_now()
        db.commit()
        raise YouTubeDashboardTokenRefreshError("YouTube access token refresh failed.") from exc

    data = fetch_youtube_channel_and_recent_videos(credentials)
    synced_at = utc_now()
    channel = data.get("channel")
    videos = data.get("videos") or []
    raw = data.get("raw") or {}

    if channel:
        snippet = channel.get("snippet") or {}
        statistics = channel.get("statistics") or {}
        channel_id = channel.get("id") or account.platform_user_id or "unknown"
        channel_title = snippet.get("title") or account.platform_account_name or "YouTube Channel"
        metric = YouTubeChannelMetric(
            user_id=account.user_id,
            social_account_id=account.id,
            platform="youtube",
            channel_id=channel_id,
            channel_title=channel_title,
            subscriber_count=_parse_int(statistics.get("subscriberCount")),
            video_count=_parse_int(statistics.get("videoCount")),
            view_count=_parse_int(statistics.get("viewCount")),
            raw_response_json=model_to_json({"channel": raw.get("channel")}),
            synced_at=synced_at,
        )
        db.add(metric)
        account.platform_user_id = channel_id
        account.platform_account_name = channel_title
        account.account_url = f"https://www.youtube.com/channel/{channel_id}" if channel_id != "unknown" else account.account_url
        account.account_handle = channel_title

    db.query(YouTubeVideoMetric).filter(
        YouTubeVideoMetric.user_id == account.user_id,
        YouTubeVideoMetric.social_account_id == account.id,
    ).delete(synchronize_session=False)

    for video in videos:
        video_id = video.get("id")
        if not video_id:
            continue
        snippet = video.get("snippet") or {}
        statistics = video.get("statistics") or {}
        db.add(
            YouTubeVideoMetric(
                user_id=account.user_id,
                social_account_id=account.id,
                platform="youtube",
                provider_video_id=video_id,
                title=snippet.get("title") or "Untitled YouTube video",
                thumbnail_url=_best_thumbnail_url(snippet.get("thumbnails")),
                published_at=_parse_datetime(snippet.get("publishedAt")),
                view_count=_parse_int(statistics.get("viewCount")),
                like_count=_parse_int(statistics.get("likeCount")),
                comment_count=_parse_int(statistics.get("commentCount")),
                provider_url=f"https://www.youtube.com/watch?v={video_id}",
                raw_response_json=model_to_json({"video": video}),
                synced_at=synced_at,
            )
        )

    account.last_synced_at = synced_at
    account.updated_at = synced_at
    db.commit()
    db.refresh(account)
    return build_dashboard_response(db, account.user_id)
