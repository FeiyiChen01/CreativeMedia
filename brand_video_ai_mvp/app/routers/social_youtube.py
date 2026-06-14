"""Social account, YouTube OAuth, and publishing routes."""

import os
import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.core import hash_token, model_to_json, normalize_datetime, utc_now
from app.database import get_db
from app.models import OAuthState, PublishingJob, SocialAccount, User, VideoAsset
from app.schemas import MessageResponse, PublishingJobResponse, SocialAccountRequest, SocialAccountResponse, YouTubeOAuthConnectResponse, YouTubeShortUploadRequest
from app.services import youtube_oauth_service, youtube_upload_service
from app.services.token_crypto_service import TokenCryptoError, encrypt_token
from app.services.youtube_oauth_service import YouTubeOAuthError
from app.services.youtube_upload_service import YouTubeUploadError

router = APIRouter()

@router.get("/api/social-accounts", response_model=list[SocialAccountResponse])
def list_social_accounts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SocialAccountResponse]:
    """List manually linked social accounts for the current user."""

    accounts = db.scalars(
        select(SocialAccount)
        .where(SocialAccount.user_id == current_user.id)
        .order_by(SocialAccount.linked_at.desc(), SocialAccount.id.desc())
    ).all()
    return [SocialAccountResponse.model_validate(account) for account in accounts]


@router.post("/api/social-accounts", response_model=SocialAccountResponse, status_code=status.HTTP_201_CREATED)
def add_social_account(
    payload: SocialAccountRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SocialAccountResponse:
    """Manually link a social account URL or handle to the current user."""

    account = SocialAccount(
        user_id=current_user.id,
        platform=payload.platform,
        account_url=payload.account_url,
        account_handle=payload.account_handle,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return SocialAccountResponse.model_validate(account)


@router.delete("/api/social-accounts/{account_id}", response_model=MessageResponse)
def delete_social_account(
    account_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Disconnect or remove one social account owned by the current user."""

    account = db.get(SocialAccount, account_id)
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Social account not found.", "error_code": "SOCIAL_ACCOUNT_NOT_FOUND"},
        )
    if account.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"detail": "You cannot disconnect this social account.", "error_code": "SOCIAL_ACCOUNT_FORBIDDEN"},
        )

    db.delete(account)
    db.commit()
    return MessageResponse(message="Social account disconnected.")


@router.get("/api/oauth/youtube/connect", response_model=YouTubeOAuthConnectResponse)
def connect_youtube_oauth(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> YouTubeOAuthConnectResponse:
    """Create a CSRF-protected Google OAuth URL for connecting YouTube."""

    state = secrets.token_urlsafe(32)
    oauth_state = OAuthState(
        user_id=current_user.id,
        provider="youtube",
        state_hash=hash_token(state),
        return_to="/?youtube_connected=success",
        expires_at=utc_now() + timedelta(minutes=10),
    )
    db.add(oauth_state)
    try:
        auth_url = youtube_oauth_service.build_youtube_auth_url(current_user.id, state)
    except YouTubeOAuthError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": str(exc), "error_code": "YOUTUBE_OAUTH_CONFIG_ERROR"},
        ) from exc

    db.commit()
    return YouTubeOAuthConnectResponse(auth_url=auth_url)


def _oauth_failed_redirect() -> RedirectResponse:
    """Redirect the browser back to the frontend with a failed OAuth marker."""

    return RedirectResponse(url="/?youtube_connected=failed", status_code=status.HTTP_302_FOUND)


@router.get("/api/oauth/youtube/callback")
def youtube_oauth_callback(
    code: str | None = None,
    state: str | None = None,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Handle the Google OAuth callback and store encrypted YouTube tokens."""

    if not code or not state:
        return _oauth_failed_redirect()

    oauth_state = db.scalar(
        select(OAuthState).where(
            OAuthState.provider == "youtube",
            OAuthState.state_hash == hash_token(state),
        )
    )
    if (
        oauth_state is None
        or oauth_state.used_at is not None
        or normalize_datetime(oauth_state.expires_at) < utc_now()
    ):
        return _oauth_failed_redirect()

    oauth_state.used_at = utc_now()
    db.commit()

    try:
        token_payload = youtube_oauth_service.exchange_code_for_tokens(code)
        credentials = youtube_oauth_service.credentials_from_token_payload(token_payload)
        try:
            profile = youtube_oauth_service.get_youtube_channel_profile(credentials)
        except YouTubeOAuthError:
            # The upload scope can be enough for publishing even when channel
            # profile reads are denied. Keep the account connected so upload can
            # proceed with the granted refresh token.
            profile = {
                "platform_user_id": None,
                "platform_account_name": "YouTube Channel",
                "account_url": None,
                "metadata": {"profile_sync": "unavailable_with_current_scope"},
            }
        platform_user_id = profile.get("platform_user_id")
        account = None
        if platform_user_id:
            account = db.scalar(
                select(SocialAccount).where(
                    SocialAccount.user_id == oauth_state.user_id,
                    SocialAccount.platform == "youtube",
                    SocialAccount.platform_user_id == platform_user_id,
                )
            )
        if account is None:
            account = db.scalar(
                select(SocialAccount).where(
                    SocialAccount.user_id == oauth_state.user_id,
                    SocialAccount.platform == "youtube",
                    SocialAccount.connection_status == "connected",
                )
            )
        if account is None:
            account = SocialAccount(user_id=oauth_state.user_id, platform="youtube")
            db.add(account)

        account.platform_user_id = profile.get("platform_user_id")
        account.platform_account_name = profile.get("platform_account_name")
        account.account_url = profile.get("account_url")
        account.account_handle = profile.get("platform_account_name")
        account.access_token_encrypted = encrypt_token(token_payload.get("token"))
        refresh_token = token_payload.get("refresh_token")
        if refresh_token:
            account.refresh_token_encrypted = encrypt_token(refresh_token)
        account.token_expires_at = token_payload.get("expiry")
        account.scopes = youtube_oauth_service.serialize_scopes(
            youtube_oauth_service.merge_with_configured_scopes(token_payload.get("scopes"))
        )
        account.connection_status = "connected"
        account.last_synced_at = utc_now()
        account.updated_at = utc_now()
        account.metadata_json = model_to_json(profile.get("metadata") or {})
        db.commit()
    except (YouTubeOAuthError, TokenCryptoError):
        db.rollback()
        return _oauth_failed_redirect()

    return RedirectResponse(url="/?youtube_connected=success", status_code=status.HTTP_302_FOUND)


def _validate_video_asset_owner(db: Session, video_asset_id: int, user_id: int) -> VideoAsset:
    """Return an owned VideoAsset or raise a precise HTTP error."""

    video_asset = db.get(VideoAsset, video_asset_id)
    if video_asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Video asset not found.", "error_code": "VIDEO_ASSET_NOT_FOUND"},
        )
    if video_asset.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"detail": "You cannot publish this video asset.", "error_code": "VIDEO_ASSET_FORBIDDEN"},
        )
    return video_asset


def _validate_social_account_owner(db: Session, social_account_id: int, user_id: int) -> SocialAccount:
    """Return an owned connected YouTube account or raise a precise HTTP error."""

    account = db.get(SocialAccount, social_account_id)
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Social account not found.", "error_code": "SOCIAL_ACCOUNT_NOT_FOUND"},
        )
    if account.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"detail": "You cannot use this social account.", "error_code": "SOCIAL_ACCOUNT_FORBIDDEN"},
        )
    if account.platform != "youtube" or account.connection_status != "connected":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "A connected YouTube account is required.", "error_code": "YOUTUBE_ACCOUNT_NOT_CONNECTED"},
        )
    return account


@router.post("/api/youtube/shorts/upload", response_model=PublishingJobResponse)
def upload_youtube_short(
    payload: YouTubeShortUploadRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PublishingJobResponse:
    """Upload an owned VideoAsset to YouTube using the connected account."""

    if payload.privacy_status == "public" and os.getenv("YOUTUBE_UPLOAD_ALLOW_PUBLIC", "false").lower() != "true":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Public YouTube uploads are disabled in this environment.", "error_code": "PUBLIC_UPLOAD_DISABLED"},
        )

    video_asset = _validate_video_asset_owner(db, payload.video_asset_id, current_user.id)
    account = _validate_social_account_owner(db, payload.social_account_id, current_user.id)
    request_payload = payload.model_dump()

    job = PublishingJob(
        user_id=current_user.id,
        video_asset_id=video_asset.id,
        social_account_id=account.id,
        platform="youtube",
        status="running",
        title=payload.title.strip(),
        description=payload.description or "",
        tags_json=model_to_json(payload.tags),
        privacy_status=payload.privacy_status or os.getenv("YOUTUBE_UPLOAD_DEFAULT_PRIVACY_STATUS", "private"),
        request_json=model_to_json(request_payload),
        started_at=utc_now(),
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        result = youtube_upload_service.upload_video_to_youtube(
            account=account,
            video_asset=video_asset,
            title=job.title,
            description=job.description,
            tags=payload.tags,
            privacy_status=job.privacy_status,
            contains_synthetic_media=payload.contains_synthetic_media,
        )
        job.status = "success"
        job.provider_post_id = result.get("video_id")
        job.provider_post_url = result.get("watch_url")
        job.response_json = model_to_json(result.get("response") or result)
        job.completed_at = utc_now()
        db.commit()
        db.refresh(job)
        return PublishingJobResponse.model_validate(job)
    except YouTubeOAuthError as exc:
        account.connection_status = "expired"
        account.updated_at = utc_now()
        job.status = "failed"
        job.error_message = str(exc)
        job.completed_at = utc_now()
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"detail": str(exc), "error_code": "YOUTUBE_TOKEN_REFRESH_FAILED"},
        ) from exc
    except YouTubeUploadError as exc:
        job.status = "failed"
        job.error_message = str(exc)
        job.completed_at = utc_now()
        db.commit()
        if "does not exist" in str(exc) or "file path" in str(exc) or "video file" in str(exc):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"detail": str(exc), "error_code": "VIDEO_FILE_INVALID"},
            ) from exc
        db.refresh(job)
        return PublishingJobResponse.model_validate(job)
    except Exception as exc:  # noqa: BLE001 - persist provider failures even when tests monkeypatch the service.
        job.status = "failed"
        job.error_message = str(exc)
        job.completed_at = utc_now()
        db.commit()
        db.refresh(job)
        return PublishingJobResponse.model_validate(job)


@router.get("/api/publishing-jobs", response_model=list[PublishingJobResponse])
def list_publishing_jobs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PublishingJobResponse]:
    """List publishing history for the current user."""

    rows = db.scalars(
        select(PublishingJob)
        .where(PublishingJob.user_id == current_user.id)
        .order_by(PublishingJob.created_at.desc(), PublishingJob.id.desc())
    ).all()
    return [PublishingJobResponse.model_validate(row) for row in rows]


@router.get("/api/publishing-jobs/{job_id}", response_model=PublishingJobResponse)
def get_publishing_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PublishingJobResponse:
    """Return one publishing job owned by the current user."""

    job = db.get(PublishingJob, job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Publishing job not found.", "error_code": "PUBLISHING_JOB_NOT_FOUND"},
        )
    if job.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"detail": "You cannot access this publishing job.", "error_code": "PUBLISHING_JOB_FORBIDDEN"},
        )
    return PublishingJobResponse.model_validate(job)
# ==================== END AUTH ADDITION ====================

