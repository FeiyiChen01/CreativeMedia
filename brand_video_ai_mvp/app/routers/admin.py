"""Admin routes."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import get_current_admin_user
from app.core import log_admin_action, row_count, utc_now
from app.database import get_db
from app.models import AdminActionLog, ApiUsageLog, GeneratedOutline, GeneratedPromptPackage, GenerationJob, Questionnaire, SocialAccount, User, VideoAsset
from app.schemas import AdminActionLogResponse, AdminUserUpdateRequest, ApiUsageLogResponse, GenerationJobResponse, QuestionnaireResponse, SocialAccountResponse, UserResponse, VideoAssetResponse

router = APIRouter()

@router.get("/api/admin/metrics")
def get_admin_metrics(
    _admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """Return overview metrics for the admin dashboard."""

    recent_errors = db.scalars(
        select(GenerationJob)
        .where(GenerationJob.status == "failed")
        .order_by(GenerationJob.completed_at.desc(), GenerationJob.id.desc())
        .limit(10)
    ).all()
    estimated_total_cost = db.scalar(select(func.coalesce(func.sum(ApiUsageLog.estimated_cost), 0))) or 0

    return {
        "total_users": row_count(db, User),
        "active_users": row_count(db, User, User.is_active.is_(True)),
        "verified_users": row_count(db, User, User.email_verified.is_(True)),
        "total_questionnaires": row_count(db, Questionnaire),
        "total_social_accounts": row_count(db, SocialAccount),
        "total_generated_outlines": row_count(db, GeneratedOutline),
        "total_prompt_packages": row_count(db, GeneratedPromptPackage),
        "total_generation_jobs": row_count(db, GenerationJob),
        "total_video_jobs": row_count(db, GenerationJob, GenerationJob.job_type == "video"),
        "successful_jobs": row_count(db, GenerationJob, GenerationJob.status == "success"),
        "failed_jobs": row_count(db, GenerationJob, GenerationJob.status == "failed"),
        "total_api_usage_rows": row_count(db, ApiUsageLog),
        "estimated_total_cost": float(estimated_total_cost or 0),
        "recent_errors": [
            {
                "id": job.id,
                "job_type": job.job_type,
                "error_message": job.error_message,
                "completed_at": job.completed_at,
            }
            for job in recent_errors
        ],
    }


@router.get("/api/admin/users", response_model=list[UserResponse])
def list_admin_users(
    _admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[UserResponse]:
    """List users for admin management."""

    users = db.scalars(select(User).order_by(User.created_at.desc(), User.id.desc()).limit(limit).offset(offset)).all()
    return [UserResponse.model_validate(user) for user in users]


@router.get("/api/admin/users/{user_id}")
def get_admin_user_detail(
    user_id: int,
    _admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """Return one user's details and related account records."""

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "User not found.", "error_code": "USER_NOT_FOUND"},
        )

    questionnaires = db.scalars(select(Questionnaire).where(Questionnaire.user_id == user_id)).all()
    social_accounts = db.scalars(select(SocialAccount).where(SocialAccount.user_id == user_id)).all()
    return {
        "user": UserResponse.model_validate(user),
        "questionnaires": [QuestionnaireResponse.model_validate(item) for item in questionnaires],
        "social_accounts": [SocialAccountResponse.model_validate(item) for item in social_accounts],
        "generation_job_count": row_count(db, GenerationJob, GenerationJob.user_id == user_id),
        "video_asset_count": row_count(db, VideoAsset, VideoAsset.user_id == user_id),
    }


@router.patch("/api/admin/users/{user_id}", response_model=UserResponse)
def update_admin_user(
    user_id: int,
    payload: AdminUserUpdateRequest,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> UserResponse:
    """Update admin-managed user fields and log the action."""

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "User not found.", "error_code": "USER_NOT_FOUND"},
        )

    changes: dict[str, object] = {}
    if payload.is_active is not None and payload.is_active != user.is_active:
        changes["is_active"] = payload.is_active
        user.is_active = payload.is_active
    if payload.role is not None and payload.role != user.role:
        changes["role"] = payload.role
        user.role = payload.role
    if payload.email_verified is not None and payload.email_verified != user.email_verified:
        changes["email_verified"] = payload.email_verified
        user.email_verified = payload.email_verified
        user.email_verified_at = utc_now() if payload.email_verified else None

    log_admin_action(db, admin_user, "update_user", "user", str(user.id), changes)
    db.commit()
    db.refresh(user)
    return UserResponse.model_validate(user)


@router.get("/api/admin/questionnaires", response_model=list[QuestionnaireResponse])
def list_admin_questionnaires(
    _admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[QuestionnaireResponse]:
    """List saved questionnaires for admins."""

    rows = db.scalars(select(Questionnaire).order_by(Questionnaire.updated_at.desc()).limit(limit).offset(offset)).all()
    return [QuestionnaireResponse.model_validate(row) for row in rows]


@router.get("/api/admin/generation-jobs", response_model=list[GenerationJobResponse])
def list_admin_generation_jobs(
    _admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
    status_filter: str | None = Query(default=None, alias="status"),
    job_type: str | None = None,
    user_id: int | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[GenerationJobResponse]:
    """List generation jobs with simple filters."""

    statement = select(GenerationJob)
    if status_filter:
        statement = statement.where(GenerationJob.status == status_filter)
    if job_type:
        statement = statement.where(GenerationJob.job_type == job_type)
    if user_id:
        statement = statement.where(GenerationJob.user_id == user_id)
    rows = db.scalars(statement.order_by(GenerationJob.created_at.desc(), GenerationJob.id.desc()).limit(limit).offset(offset)).all()
    return [GenerationJobResponse.model_validate(row) for row in rows]


@router.get("/api/admin/video-assets", response_model=list[VideoAssetResponse])
def list_admin_video_assets(
    _admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[VideoAssetResponse]:
    """List video assets for admins."""

    rows = db.scalars(select(VideoAsset).order_by(VideoAsset.created_at.desc(), VideoAsset.id.desc()).limit(limit).offset(offset)).all()
    return [VideoAssetResponse.model_validate(row) for row in rows]


@router.get("/api/admin/api-usage", response_model=list[ApiUsageLogResponse])
def list_admin_api_usage(
    _admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[ApiUsageLogResponse]:
    """List API usage and cost rows for admins."""

    rows = db.scalars(select(ApiUsageLog).order_by(ApiUsageLog.created_at.desc(), ApiUsageLog.id.desc()).limit(limit).offset(offset)).all()
    return [ApiUsageLogResponse.model_validate(row) for row in rows]


@router.get("/api/admin/action-logs", response_model=list[AdminActionLogResponse])
def list_admin_action_logs(
    _admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[AdminActionLogResponse]:
    """List admin audit events."""

    rows = db.scalars(select(AdminActionLog).order_by(AdminActionLog.created_at.desc(), AdminActionLog.id.desc()).limit(limit).offset(offset)).all()
    return [AdminActionLogResponse.model_validate(row) for row in rows]
