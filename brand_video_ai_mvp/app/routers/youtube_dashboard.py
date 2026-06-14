"""YouTube dashboard routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import User
from app.schemas import YouTubeDashboardResponse
from app.services.youtube_dashboard_service import (
    YouTubeDashboardError,
    YouTubeDashboardReconnectRequired,
    YouTubeDashboardTokenRefreshError,
    build_dashboard_response,
    get_connected_youtube_account,
    refresh_youtube_dashboard,
)

router = APIRouter()


@router.get("/api/dashboard/youtube", response_model=YouTubeDashboardResponse)
def get_youtube_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> YouTubeDashboardResponse:
    """Return cached YouTube dashboard data for the current user."""

    return build_dashboard_response(db, current_user.id)


@router.post("/api/dashboard/youtube/refresh", response_model=YouTubeDashboardResponse)
def refresh_youtube_dashboard_route(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> YouTubeDashboardResponse:
    """Sync YouTube dashboard data from the provider and return cached state."""

    account = get_connected_youtube_account(db, current_user.id)
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "detail": "A connected YouTube account is required.",
                "error_code": "YOUTUBE_ACCOUNT_NOT_CONNECTED",
            },
        )

    try:
        return refresh_youtube_dashboard(db, account)
    except YouTubeDashboardReconnectRequired as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "detail": str(exc),
                "error_code": "YOUTUBE_RECONNECT_REQUIRED",
                "reconnect_required": True,
            },
        ) from exc
    except YouTubeDashboardTokenRefreshError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "detail": str(exc),
                "error_code": "YOUTUBE_TOKEN_REFRESH_FAILED",
            },
        ) from exc
    except YouTubeDashboardError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "detail": str(exc),
                "error_code": "YOUTUBE_DASHBOARD_PROVIDER_ERROR",
            },
        ) from exc
