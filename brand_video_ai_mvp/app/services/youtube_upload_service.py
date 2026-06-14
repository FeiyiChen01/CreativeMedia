"""YouTube upload service built on YouTube Data API v3 videos.insert."""

import mimetypes
from pathlib import Path
from typing import Any

from app.models import SocialAccount, VideoAsset
from app.services.youtube_oauth_service import refresh_access_token_if_needed


class YouTubeUploadError(RuntimeError):
    """Raised when a video cannot be uploaded to YouTube."""


def _resolve_video_path(video_asset: VideoAsset) -> Path:
    """Return the local file path for a VideoAsset and verify it exists."""

    if not video_asset.file_path:
        raise YouTubeUploadError("Video asset does not have a local file path.")

    path = Path(video_asset.file_path)
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[2] / path
    if not path.exists() or not path.is_file():
        raise YouTubeUploadError("Video file does not exist.")

    mime_type, _encoding = mimetypes.guess_type(path.name)
    if mime_type and not mime_type.startswith("video/"):
        raise YouTubeUploadError("Selected asset is not a video file.")
    if not mime_type and path.suffix.lower() not in {".mp4", ".mov", ".m4v", ".webm"}:
        raise YouTubeUploadError("Selected asset must be a video file.")
    return path


def upload_video_to_youtube(
    account: SocialAccount,
    video_asset: VideoAsset,
    title: str,
    description: str | None,
    tags: list[str],
    privacy_status: str,
    contains_synthetic_media: bool = False,
) -> dict[str, Any]:
    """Upload a VideoAsset to YouTube with Shorts-compatible metadata."""

    path = _resolve_video_path(video_asset)

    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    credentials = refresh_access_token_if_needed(account)
    youtube = build("youtube", "v3", credentials=credentials)

    metadata = {
        "snippet": {
            "title": title,
            "description": description or "",
            "tags": tags or [],
            "categoryId": "22",
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False,
            # YouTube supports this status flag for synthetic media disclosures.
            "containsSyntheticMedia": bool(contains_synthetic_media),
        },
    }
    media = MediaFileUpload(str(path), chunksize=-1, resumable=True)

    try:
        request = youtube.videos().insert(part="snippet,status", body=metadata, media_body=media)
        response = request.execute()
    except Exception as exc:  # noqa: BLE001 - callers persist the failure on PublishingJob.
        raise YouTubeUploadError("YouTube video upload failed.") from exc

    video_id = response.get("id")
    if not video_id:
        raise YouTubeUploadError("YouTube upload response did not include a video id.")

    return {
        "video_id": video_id,
        "watch_url": f"https://www.youtube.com/watch?v={video_id}",
        "response": response,
    }
