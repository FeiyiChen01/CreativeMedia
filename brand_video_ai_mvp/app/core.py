"""Shared application configuration and route helpers."""

import hashlib
import json
import os
import secrets
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv
from fastapi import HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AdminActionLog, ApiUsageLog, EmailVerificationToken, PasswordResetToken, Questionnaire, User
from app.schemas import ProfileResponse
from app.services.email_service import EmailService

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
APP_ENV = os.getenv("APP_ENV", "development").lower()
MAX_PROFILE_UPLOAD_BYTES = 5 * 1024 * 1024
ALLOWED_PROFILE_IMAGE_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}

def parse_csv_env(value: str | None) -> list[str]:
    """Parse comma-separated env values into a cleaned list."""

    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def get_cors_allowed_origins() -> list[str]:
    """Return explicit CORS origins from env with safe development defaults."""

    configured_origins = parse_csv_env(os.getenv("CORS_ALLOWED_ORIGINS"))
    if configured_origins:
        return configured_origins

    if APP_ENV == "production":
        raise RuntimeError("CORS_ALLOWED_ORIGINS must be set explicitly in production.")

    return ["http://localhost:8000", "http://127.0.0.1:8000"]


def get_admin_emails() -> set[str]:
    """Return normalized admin bootstrap emails."""

    return {email.lower() for email in parse_csv_env(os.getenv("ADMIN_EMAILS"))}


def get_app_base_url() -> str:
    """Return public app base URL for account links."""

    return os.getenv("APP_BASE_URL", "http://localhost:8000").rstrip("/")


def get_local_video_storage_dir() -> Path:
    """Return the local video storage directory, resolving relative env paths."""

    configured_dir = os.getenv("LOCAL_VIDEO_STORAGE_DIR", "static/generated_videos").strip()
    path = Path(configured_dir)
    return path if path.is_absolute() else BASE_DIR / path


def get_user_upload_dir(user_id: int) -> Path:
    """Return a per-user static upload directory for profile-owned media."""

    return STATIC_DIR / "uploads" / "users" / str(user_id)


def utc_now() -> datetime:
    """Return the current UTC time."""

    return datetime.now(UTC)


def normalize_datetime(value: datetime) -> datetime:
    """Attach UTC timezone to SQLite naive datetimes for safe comparisons."""

    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def hash_token(token: str) -> str:
    """Hash a one-time token before storing or comparing it."""

    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_one_time_token() -> tuple[str, str, datetime]:
    """Create a raw token, its hash, and a 24-hour expiration timestamp."""

    token = secrets.token_urlsafe(32)
    return token, hash_token(token), utc_now() + timedelta(hours=24)


def model_to_json(value: object) -> str:
    """Serialize Pydantic models or simple objects to JSON text."""

    if hasattr(value, "model_dump"):
        value = value.model_dump()
    return json.dumps(value, ensure_ascii=False, default=str)


def build_profile_response(user: User) -> ProfileResponse:
    """Build a profile response with display names and without email."""

    full_name = (user.full_name or "").strip() or None
    company_name = (user.company_name or "").strip() or None
    display_name = full_name or company_name or user.username
    return ProfileResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        full_name=full_name,
        company_name=company_name,
        avatar_url=user.avatar_url,
        phone=user.phone,
        email_verified=user.email_verified,
        email_verified_at=user.email_verified_at,
        role=user.role,
        is_active=user.is_active,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
        updated_at=user.updated_at,
        display_name=display_name,
        display_company_name=company_name if full_name and company_name else None,
    )


def save_upload_file(file: UploadFile, user_id: int, stem: str) -> tuple[str, str]:
    """Validate and save a small user-owned image under static/uploads."""

    extension = ALLOWED_PROFILE_IMAGE_TYPES.get((file.content_type or "").lower())
    if extension is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Only png, jpg, jpeg, or webp images are allowed.", "error_code": "INVALID_IMAGE_TYPE"},
        )

    contents = file.file.read(MAX_PROFILE_UPLOAD_BYTES + 1)
    if len(contents) > MAX_PROFILE_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Image must be 5MB or smaller.", "error_code": "IMAGE_TOO_LARGE"},
        )

    upload_dir = get_user_upload_dir(user_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{stem}-{secrets.token_hex(8)}{extension}"
    target_path = upload_dir / filename
    target_path.write_bytes(contents)
    url = f"/static/uploads/users/{user_id}/{filename}"
    return str(target_path), url


def parse_json_text(value: str | None) -> object | None:
    """Parse JSON text stored in ORM records for API output."""

    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def json_safe(value: object) -> object:
    """Convert nested validation details into JSON-serializable values."""

    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def source_provider(source: str) -> str:
    """Normalize provider values for constrained job records."""

    return "openai" if source == "openai" else "mock"


def get_latest_questionnaire(db: Session, user_id: int) -> Questionnaire | None:
    """Return the latest questionnaire for relationship tracking."""

    return db.scalar(
        select(Questionnaire)
        .where(Questionnaire.user_id == user_id)
        .order_by(Questionnaire.updated_at.desc(), Questionnaire.id.desc())
    )


def resolve_questionnaire_id(db: Session, user_id: int, questionnaire_id: int | None = None) -> int | None:
    """Use an explicit questionnaire id when owned by the user, otherwise the latest one."""

    if questionnaire_id:
        questionnaire = db.get(Questionnaire, questionnaire_id)
        if questionnaire and questionnaire.user_id == user_id:
            return questionnaire.id
    latest_questionnaire = get_latest_questionnaire(db, user_id)
    return latest_questionnaire.id if latest_questionnaire else None


def create_api_usage_log(
    db: Session,
    operation: str,
    provider: str,
    model: str | None,
    generation_job_id: int | None = None,
    user_id: int | None = None,
    latency_ms: int | None = None,
    estimated_cost: float | Decimal | None = 0,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
) -> None:
    """Persist a provider usage row for admin cost visibility.

    Token and cost calculation is intentionally stubbed at zero until real
    provider usage metadata is wired in.
    """

    db.add(
        ApiUsageLog(
            user_id=user_id,
            generation_job_id=generation_job_id,
            provider=provider,
            model=model or "unknown",
            operation=operation,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost=estimated_cost if estimated_cost is not None else Decimal("0"),
            latency_ms=latency_ms,
        )
    )


def send_verification_for_user(user: User, db: Session) -> str:
    """Create a verification token and deliver/log its link."""

    token, token_hash, expires_at = create_one_time_token()
    record = EmailVerificationToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.add(record)
    db.commit()

    verification_url = f"{get_app_base_url()}/api/auth/verify-email?token={token}"
    EmailService().send_verification_email(user.email, verification_url)
    return verification_url


def send_password_reset_for_user(user: User, db: Session) -> str:
    """Create a password reset token and deliver/log its link."""

    token, token_hash, expires_at = create_one_time_token()
    record = PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.add(record)
    db.commit()

    reset_url = f"{get_app_base_url()}/?reset_token={token}"
    EmailService().send_password_reset_email(user.email, reset_url)
    return reset_url


def row_count(db: Session, model: type, *criteria: object) -> int:
    """Count model rows with optional SQLAlchemy criteria."""

    statement = select(func.count()).select_from(model)
    if criteria:
        statement = statement.where(*criteria)
    return int(db.scalar(statement) or 0)


def log_admin_action(
    db: Session,
    admin_user: User,
    action: str,
    target_type: str | None = None,
    target_id: str | None = None,
    metadata: dict[str, object] | None = None,
) -> None:
    """Persist a simple admin audit event."""

    db.add(
        AdminActionLog(
            admin_user_id=admin_user.id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            metadata_json=model_to_json(metadata or {}),
        )
    )

