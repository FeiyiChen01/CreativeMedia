"""FastAPI entry point for the Brand Video AI MVP.

Run locally with:
    uvicorn app.main:app --reload --port 8000
"""

import hashlib
import json
import os
import secrets
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv
from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, Query, Request, UploadFile, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

# ==================== AUTH ADDITION: database/auth/schema imports ====================
from app.auth import (
    ACCESS_TOKEN_EXPIRE_DAYS,
    create_access_token,
    get_current_admin_user,
    get_current_user,
    hash_password,
    verify_password,
)
from app.database import get_db, init_db
# ==================== END AUTH ADDITION ====================
from app.models import (
    AdminActionLog,
    ApiUsageLog,
    EmailVerificationToken,
    GenerateOutlineRequest,
    GenerateOutlineResponse,
    GeneratePromptsResponse,
    GenerateSceneVideoRequest,
    GenerateSceneVideoResponse,
    GeneratedOutline,
    GeneratedPromptPackage,
    GenerationJob,
    OAuthState,
    PasswordResetToken,
    PublishingJob,
    Questionnaire,
    ReviewOutlineRequest,
    SocialAccount,
    User,
    VideoAsset,
)
from app.prompts import OUTLINE_SYSTEM_PROMPT, VIDEO_PROMPT_SYSTEM_PROMPT
from app.schemas import (
    QuestionnaireRequest,
    QuestionnaireResponse,
    AdminActionLogResponse,
    AdminUserUpdateRequest,
    ApiUsageLogResponse,
    BrandProfileRequest,
    BrandProfileResponse,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    GeneratedOutlineResponse,
    GeneratedPromptPackageResponse,
    GenerationJobResponse,
    MessageResponse,
    ProfileResponse,
    ProfileUpdateRequest,
    PublishingJobResponse,
    ResetPasswordRequest,
    SocialAccountRequest,
    SocialAccountResponse,
    TokenResponse,
    UploadResponse,
    UserLogin,
    UserRegister,
    UserResponse,
    VideoAssetResponse,
    VideoJobCreateRequest,
    VideoJobCreateResponse,
    VideoJobStatusResponse,
    YouTubeOAuthConnectResponse,
    YouTubeShortUploadRequest,
)
from app.services.email_service import EmailService
from app.services.openai_service import AIServiceError, BrandVideoAIService
from app.services.openai_video_service import OpenAIVideoService, VideoGenerationError
from app.services.storage_service import VideoStorageService
from app.services import youtube_oauth_service, youtube_upload_service
from app.services.token_crypto_service import TokenCryptoError, encrypt_token
from app.services.youtube_oauth_service import YouTubeOAuthError
from app.services.youtube_upload_service import YouTubeUploadError

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

app = FastAPI(
    title="Brand Video AI MVP",
    description="AI-powered TikTok outline and video prompt generator for brands.",
    version="0.2.0",
)

# CORS is useful if you later replace static HTML with a React/Vite frontend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ==================== AUTH ADDITION: normalized error handlers ====================
@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    """Return API errors in a consistent top-level JSON format."""

    if isinstance(exc.detail, dict) and "detail" in exc.detail:
        content = exc.detail
    elif exc.status_code == status.HTTP_401_UNAUTHORIZED:
        content = {
            "detail": str(exc.detail),
            "error_code": "INVALID_TOKEN",
        }
    else:
        content = {
            "detail": str(exc.detail),
            "error_code": "HTTP_ERROR",
        }
    return JSONResponse(status_code=exc.status_code, content=content, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    """Return request validation errors with a stable error_code."""

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Invalid request body.",
            "error_code": "VALIDATION_ERROR",
            "errors": json_safe(exc.errors()),
        },
    )


@app.on_event("startup")
def on_startup() -> None:
    """Initialize SQLite tables when the app starts."""

    EmailService().require_production_config()
    init_db()
# ==================== END AUTH ADDITION ====================


@app.get("/")
def serve_index() -> FileResponse:
    """Serve the MVP web UI."""
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health_check() -> dict[str, str]:
    """Simple health check endpoint for local testing."""
    return {"status": "ok"}


# ==================== AUTH ADDITION: auth route helpers ====================
def build_token_response(user: User, message: str | None = None) -> TokenResponse:
    """Build a JWT response for a successfully authenticated user."""

    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email, "username": user.username},
        expires_delta=timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS),
    )
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
        message=message,
    )


@app.post("/api/auth/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register_user(payload: UserRegister, db: Session = Depends(get_db)) -> TokenResponse:
    """Register a new user and return a JWT token for automatic login."""

    email = payload.email.lower().strip()
    username = payload.username.strip()

    existing_user = db.scalar(
        select(User).where(or_(User.email == email, User.username == username))
    )
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "detail": "Email or username already exists.",
                "error_code": "USER_ALREADY_EXISTS",
            },
        )

    user = User(
        email=email,
        username=username,
        password_hash=hash_password(payload.password),
        email_verified=False,
        role="admin" if email in get_admin_emails() else "user",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    try:
        send_verification_for_user(user, db)
    except Exception as exc:  # noqa: BLE001 - return a structured account-delivery error.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "detail": "Account was created, but the verification email could not be sent. Please contact support or try resending verification later.",
                "error_code": "EMAIL_DELIVERY_FAILED",
            },
        ) from exc
    user.last_login_at = datetime.now(UTC)
    db.commit()
    db.refresh(user)
    return build_token_response(
        user,
        message="Account created. Please verify your email using the link sent to you.",
    )


@app.post("/api/auth/login", response_model=TokenResponse)
def login_user(payload: UserLogin, db: Session = Depends(get_db)) -> TokenResponse:
    """Login with email and password and return a JWT token."""

    email = payload.email.lower().strip()
    user = db.scalar(select(User).where(User.email == email, User.is_active.is_(True)))

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "detail": "Email or password is incorrect.",
                "error_code": "INVALID_CREDENTIALS",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    user.last_login_at = datetime.now(UTC)
    db.commit()
    db.refresh(user)
    return build_token_response(user)


@app.post("/api/auth/logout")
def logout_user(_current_user: User = Depends(get_current_user)) -> dict[str, str]:
    """JWT logout is handled by the frontend deleting its stored token."""

    return {"message": "logout success"}


@app.get("/api/auth/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """Return the currently authenticated user."""

    return UserResponse.model_validate(current_user)


@app.post("/api/auth/resend-verification", response_model=MessageResponse)
def resend_verification(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Resend email verification link for the current user."""

    if current_user.email_verified:
        return MessageResponse(message="Email is already verified.")

    send_verification_for_user(current_user, db)
    return MessageResponse(message="Verification email sent.")


@app.get("/api/auth/verify-email", response_model=MessageResponse)
def verify_email(token: str = Query(..., min_length=16), db: Session = Depends(get_db)) -> MessageResponse:
    """Verify a user email with a one-time token."""

    token_record = db.scalar(
        select(EmailVerificationToken).where(EmailVerificationToken.token_hash == hash_token(token))
    )
    if token_record is None or token_record.used_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Verification token is invalid.", "error_code": "INVALID_VERIFICATION_TOKEN"},
        )

    if normalize_datetime(token_record.expires_at) < utc_now():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Verification token has expired.", "error_code": "VERIFICATION_TOKEN_EXPIRED"},
        )

    user = db.get(User, token_record.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Verification token user was not found.", "error_code": "USER_NOT_FOUND"},
        )

    token_record.used_at = utc_now()
    user.email_verified = True
    user.email_verified_at = utc_now()
    db.commit()
    return MessageResponse(message="Email verified successfully.")


@app.post("/api/auth/forgot-password", response_model=MessageResponse)
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)) -> MessageResponse:
    """Request a password reset link without revealing account existence."""

    user = db.scalar(select(User).where(User.email == payload.email.lower().strip(), User.is_active.is_(True)))
    if user:
        send_password_reset_for_user(user, db)
    return MessageResponse(message="If an account exists for that email, a reset link has been sent.")


@app.post("/api/auth/reset-password", response_model=MessageResponse)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)) -> MessageResponse:
    """Reset a password with a valid one-time token."""

    token_record = db.scalar(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_token(payload.token))
    )
    if token_record is None or token_record.used_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Password reset token is invalid.", "error_code": "INVALID_RESET_TOKEN"},
        )

    if normalize_datetime(token_record.expires_at) < utc_now():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Password reset token has expired.", "error_code": "RESET_TOKEN_EXPIRED"},
        )

    user = db.get(User, token_record.user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Password reset token user was not found.", "error_code": "USER_NOT_FOUND"},
        )

    token_record.used_at = utc_now()
    user.password_hash = hash_password(payload.new_password)
    db.commit()
    return MessageResponse(message="Password has been reset successfully.")
# ==================== END AUTH ADDITION ====================


# ==================== AUTH ADDITION: questionnaire routes ====================
@app.get("/api/questionnaire", response_model=QuestionnaireResponse | None)
def get_questionnaire(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> QuestionnaireResponse | None:
    """Return the latest saved questionnaire for the current user."""

    questionnaire = db.scalar(
        select(Questionnaire)
        .where(Questionnaire.user_id == current_user.id)
        .order_by(Questionnaire.updated_at.desc(), Questionnaire.id.desc())
    )
    return QuestionnaireResponse.model_validate(questionnaire) if questionnaire else None


@app.post("/api/questionnaire", response_model=QuestionnaireResponse)
def save_questionnaire(
    payload: QuestionnaireRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> QuestionnaireResponse:
    """Create or update the current user's brand questionnaire."""

    questionnaire = db.scalar(
        select(Questionnaire)
        .where(Questionnaire.user_id == current_user.id)
        .order_by(Questionnaire.updated_at.desc(), Questionnaire.id.desc())
    )

    if questionnaire is None:
        questionnaire = Questionnaire(user_id=current_user.id)
        db.add(questionnaire)

    questionnaire.brand_name = payload.brand_name
    questionnaire.company_name = payload.brand_name
    questionnaire.brand_description = payload.brand_description
    questionnaire.target_audience = payload.target_audience
    questionnaire.video_style = payload.video_style
    questionnaire.industry = payload.additional_info.get("industry") if payload.additional_info else questionnaire.industry
    questionnaire.brand_tone = payload.video_style
    questionnaire.additional_info = payload.additional_info

    db.commit()
    db.refresh(questionnaire)
    return QuestionnaireResponse.model_validate(questionnaire)
# ==================== END AUTH ADDITION ====================


def get_current_brand_profile(db: Session, user_id: int) -> Questionnaire | None:
    """Return the latest Brand Profile row for a user."""

    return db.scalar(
        select(Questionnaire)
        .where(Questionnaire.user_id == user_id)
        .order_by(Questionnaire.updated_at.desc(), Questionnaire.id.desc())
    )


def upsert_brand_profile(db: Session, user: User, payload: BrandProfileRequest) -> Questionnaire:
    """Create or update the compatibility questionnaire row as a Brand Profile."""

    profile = get_current_brand_profile(db, user.id)
    if profile is None:
        profile = Questionnaire(user_id=user.id)
        db.add(profile)

    company_name = payload.company_name.strip()
    industry = payload.industry.strip()
    profile.company_name = company_name
    profile.brand_name = company_name
    profile.industry = industry
    profile.brand_description = payload.brand_description.strip()
    profile.brand_tone = payload.brand_tone
    profile.video_style = payload.brand_tone
    profile.use_logo_in_prompt = bool(payload.use_logo_in_prompt and profile.logo_url)
    profile.target_audience = industry
    profile.additional_info = {
        "source": "brand_profile",
        "industry": industry,
        "use_logo_requested": payload.use_logo_in_prompt,
        "logo_prompt_instruction": (
            "Subtly include the brand logo in the final end card or closing visual."
            if payload.use_logo_in_prompt and profile.logo_url
            else None
        ),
    }

    user.company_name = company_name
    db.commit()
    db.refresh(profile)
    db.refresh(user)
    return profile


@app.get("/api/brand-profile", response_model=BrandProfileResponse | None)
def get_brand_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BrandProfileResponse | None:
    """Return the current user's Brand Profile."""

    profile = get_current_brand_profile(db, current_user.id)
    return BrandProfileResponse.model_validate(profile) if profile else None


@app.post("/api/brand-profile", response_model=BrandProfileResponse, status_code=status.HTTP_201_CREATED)
def create_brand_profile(
    payload: BrandProfileRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BrandProfileResponse:
    """Create or update the current user's Brand Profile."""

    profile = upsert_brand_profile(db, current_user, payload)
    return BrandProfileResponse.model_validate(profile)


@app.put("/api/brand-profile", response_model=BrandProfileResponse)
def update_brand_profile(
    payload: BrandProfileRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BrandProfileResponse:
    """Update the current user's Brand Profile."""

    profile = upsert_brand_profile(db, current_user, payload)
    return BrandProfileResponse.model_validate(profile)


@app.post("/api/brand-profile/logo", response_model=BrandProfileResponse)
def upload_brand_profile_logo(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BrandProfileResponse:
    """Upload and attach a logo to the current user's Brand Profile."""

    profile = get_current_brand_profile(db, current_user.id)
    if profile is None:
        profile = Questionnaire(user_id=current_user.id)
        db.add(profile)
        db.flush()

    logo_path, logo_url = save_upload_file(file, current_user.id, "brand-logo")
    profile.logo_path = logo_path
    profile.logo_url = logo_url
    if profile.additional_info:
        profile.additional_info = {**profile.additional_info, "logo_url": logo_url}
    db.commit()
    db.refresh(profile)
    return BrandProfileResponse.model_validate(profile)


@app.get("/api/profile", response_model=ProfileResponse)
def get_profile(current_user: User = Depends(get_current_user)) -> ProfileResponse:
    """Return the current user's account profile."""

    return build_profile_response(current_user)


@app.patch("/api/profile", response_model=ProfileResponse)
def update_profile(
    payload: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProfileResponse:
    """Update profile fields that are safe for users to manage."""

    if payload.username and payload.username != current_user.username:
        existing_user = db.scalar(
            select(User).where(User.username == payload.username, User.id != current_user.id)
        )
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"detail": "Username is already taken.", "error_code": "USERNAME_TAKEN"},
            )
        current_user.username = payload.username

    if payload.email and payload.email.lower().strip() != current_user.email:
        email = payload.email.lower().strip()
        existing_user = db.scalar(
            select(User).where(User.email == email, User.id != current_user.id)
        )
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"detail": "Email is already taken.", "error_code": "EMAIL_TAKEN"},
            )
        current_user.email = email
        current_user.email_verified = False
        current_user.email_verified_at = None

    if payload.full_name is not None:
        current_user.full_name = payload.full_name.strip() or None
    if payload.company_name is not None:
        current_user.company_name = payload.company_name.strip() or None
    if payload.avatar_url is not None:
        current_user.avatar_url = payload.avatar_url.strip() or None

    db.commit()
    db.refresh(current_user)
    return build_profile_response(current_user)


@app.put("/api/profile", response_model=ProfileResponse)
def put_profile(
    payload: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProfileResponse:
    """PUT alias for updating profile settings."""

    return update_profile(payload, current_user, db)


@app.post("/api/profile/avatar", response_model=UploadResponse)
def upload_profile_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UploadResponse:
    """Upload an avatar for the current user's profile."""

    _avatar_path, avatar_url = save_upload_file(file, current_user.id, "avatar")
    current_user.avatar_url = avatar_url
    db.commit()
    db.refresh(current_user)
    return UploadResponse(url=avatar_url)


@app.post("/api/profile/change-password", response_model=MessageResponse)
def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Change the current user's password after verifying the old password."""

    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Current password is incorrect.", "error_code": "INVALID_CURRENT_PASSWORD"},
        )

    current_user.password_hash = hash_password(payload.new_password)
    db.commit()
    return MessageResponse(message="Password changed successfully.")


# ==================== AUTH ADDITION: social account routes ====================
@app.get("/api/social-accounts", response_model=list[SocialAccountResponse])
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


@app.post("/api/social-accounts", response_model=SocialAccountResponse, status_code=status.HTTP_201_CREATED)
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


@app.delete("/api/social-accounts/{account_id}", response_model=MessageResponse)
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


@app.get("/api/oauth/youtube/connect", response_model=YouTubeOAuthConnectResponse)
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


@app.get("/api/oauth/youtube/callback")
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
        account.scopes = youtube_oauth_service.serialize_scopes(token_payload.get("scopes"))
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


@app.post("/api/youtube/shorts/upload", response_model=PublishingJobResponse)
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


@app.get("/api/publishing-jobs", response_model=list[PublishingJobResponse])
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


@app.get("/api/publishing-jobs/{job_id}", response_model=PublishingJobResponse)
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


@app.post("/api/generate-outline", response_model=GenerateOutlineResponse)
def generate_outline(
    payload: GenerateOutlineRequest,
    current_user: User = Depends(get_current_user),  # AUTH ADDITION: protect this API
    db: Session = Depends(get_db),
) -> GenerateOutlineResponse:
    """Step 1: Generate a video outline from questionnaire input."""
    questionnaire_id = resolve_questionnaire_id(db, current_user.id, payload.questionnaire_id)
    job = GenerationJob(
        user_id=current_user.id,
        job_type="outline",
        status="running",
        provider="mock",
        input_json=model_to_json({**payload.model_dump(), "questionnaire_id": questionnaire_id}),
        started_at=utc_now(),
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    started = time.monotonic()
    service = BrandVideoAIService()
    try:
        outline, source = service.generate_outline(payload.questionnaire)
        outline_record = GeneratedOutline(
            user_id=current_user.id,
            questionnaire_id=questionnaire_id,
            source=source_provider(source),
            outline_json=model_to_json(outline),
        )
        db.add(outline_record)
        db.flush()
        job.status = "success"
        job.provider = source_provider(source)
        job.model = service.model
        job.latency_ms = int((time.monotonic() - started) * 1000)
        job.output_json = model_to_json({
            "outline": outline.model_dump(),
            "source": source,
            "generated_outline_id": outline_record.id,
            "questionnaire_id": questionnaire_id,
        })
        job.completed_at = utc_now()
        create_api_usage_log(
            db,
            operation="generate_outline",
            provider=job.provider,
            model=job.model,
            generation_job_id=job.id,
            user_id=current_user.id,
            latency_ms=job.latency_ms,
        )
        db.commit()
        db.refresh(outline_record)
        db.refresh(job)
        return GenerateOutlineResponse(
            outline=outline,
            source=source,
            generated_outline_id=outline_record.id,
            generation_job_id=job.id,
        )
    except AIServiceError as exc:
        job.status = "failed"
        job.error_message = str(exc)
        job.latency_ms = int((time.monotonic() - started) * 1000)
        job.completed_at = utc_now()
        create_api_usage_log(
            db,
            operation="generate_outline",
            provider=job.provider,
            model=job.model,
            generation_job_id=job.id,
            user_id=current_user.id,
            latency_ms=job.latency_ms,
        )
        db.commit()
        raise HTTPException(
            status_code=502,
            detail={"detail": str(exc), "error_code": "AI_GENERATION_FAILED"},
        ) from exc


@app.post("/api/generate-prompts", response_model=GeneratePromptsResponse)
def generate_prompts(
    payload: ReviewOutlineRequest,
    current_user: User = Depends(get_current_user),  # AUTH ADDITION: protect this API
    db: Session = Depends(get_db),
) -> GeneratePromptsResponse:
    """Step 3: Convert reviewed outline into English video-generation prompts."""
    questionnaire_id = resolve_questionnaire_id(db, current_user.id, payload.questionnaire_id)
    outline_id = payload.generated_outline_id or payload.outline_id
    if outline_id:
        outline_record = db.get(GeneratedOutline, outline_id)
        if outline_record is None or outline_record.user_id != current_user.id:
            outline_id = None
        elif questionnaire_id is None:
            questionnaire_id = outline_record.questionnaire_id

    job = GenerationJob(
        user_id=current_user.id,
        job_type="prompt",
        status="running",
        provider="mock",
        input_json=model_to_json({**payload.model_dump(), "questionnaire_id": questionnaire_id, "outline_id": outline_id}),
        started_at=utc_now(),
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    started = time.monotonic()
    service = BrandVideoAIService()
    try:
        prompt_package, source = service.generate_video_prompts(
            questionnaire=payload.questionnaire,
            outline=payload.outline,
            target_tool=payload.target_tool,
        )
        package_record = GeneratedPromptPackage(
            user_id=current_user.id,
            questionnaire_id=questionnaire_id,
            outline_id=outline_id,
            source=source_provider(source),
            prompt_package_json=model_to_json(prompt_package),
        )
        db.add(package_record)
        db.flush()
        job.status = "success"
        job.provider = source_provider(source)
        job.model = service.model
        job.latency_ms = int((time.monotonic() - started) * 1000)
        job.output_json = model_to_json({
            "prompt_package": prompt_package.model_dump(),
            "source": source,
            "generated_prompt_package_id": package_record.id,
            "generated_outline_id": outline_id,
            "questionnaire_id": questionnaire_id,
        })
        job.completed_at = utc_now()
        create_api_usage_log(
            db,
            operation="generate_prompts",
            provider=job.provider,
            model=job.model,
            generation_job_id=job.id,
            user_id=current_user.id,
            latency_ms=job.latency_ms,
        )
        db.commit()
        db.refresh(package_record)
        db.refresh(job)
        return GeneratePromptsResponse(
            prompt_package=prompt_package,
            source=source,
            generated_prompt_package_id=package_record.id,
            generation_job_id=job.id,
        )
    except AIServiceError as exc:
        job.status = "failed"
        job.error_message = str(exc)
        job.latency_ms = int((time.monotonic() - started) * 1000)
        job.completed_at = utc_now()
        create_api_usage_log(
            db,
            operation="generate_prompts",
            provider=job.provider,
            model=job.model,
            generation_job_id=job.id,
            user_id=current_user.id,
            latency_ms=job.latency_ms,
        )
        db.commit()
        raise HTTPException(
            status_code=502,
            detail={"detail": str(exc), "error_code": "AI_GENERATION_FAILED"},
        ) from exc


def run_video_generation_job(job_id: int) -> None:
    """Run one video job in the background.

    FastAPI BackgroundTasks is fine for the MVP. Celery or RQ should replace it
    for production-scale workloads so jobs survive process restarts.
    """

    from app.database import SessionLocal

    db = SessionLocal()
    started = time.monotonic()
    try:
        job = db.get(GenerationJob, job_id)
        if job is None:
            return
        if job.status == "success":
            return
        job.status = "running"
        job.started_at = utc_now()
        db.commit()

        input_payload = json.loads(job.input_json or "{}")
        allow_mock = os.getenv("ALLOW_MOCK_AI", "true").lower() == "true"
        openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
        is_placeholder_key = not openai_api_key or openai_api_key.startswith("sk-your")
        if allow_mock and is_placeholder_key:
            storage = VideoStorageService(base_dir=get_local_video_storage_dir())
            result = {
                "video_id": f"mock-video-{job.id}",
                "status": "completed",
                "video_url": "",
                "file_path": "",
                "storage_backend": storage.get_storage_backend(),
                "file_size": None,
                "model": "mock-sora-2",
                "size": os.getenv("OPENAI_VIDEO_SIZE", "720x1280"),
                "seconds": str(input_payload.get("duration_seconds", 4)),
            }
        else:
            service = OpenAIVideoService(output_dir=get_local_video_storage_dir())
            result = service.generate_scene_video(
                prompt=input_payload["prompt_en"],
                duration_seconds=float(input_payload.get("duration_seconds", 4)),
            )

        asset = VideoAsset(
            user_id=job.user_id,
            generation_job_id=job.id,
            prompt_package_id=input_payload.get("prompt_package_id"),
            scene_number=input_payload.get("scene_number"),
            provider_video_id=result.get("video_id"),
            storage_backend=result.get("storage_backend"),
            video_url=result.get("video_url"),
            file_path=result.get("file_path"),
            file_size=int(result["file_size"]) if result.get("file_size") else None,
            model=result.get("model"),
            size=result.get("size"),
            seconds=float(result.get("seconds") or input_payload.get("duration_seconds", 4)),
            status=result.get("status", "completed"),
        )
        db.add(asset)
        db.flush()
        job.status = "success"
        job.provider = "mock" if result.get("model") == "mock-sora-2" else "openai"
        job.model = result.get("model")
        job.latency_ms = int((time.monotonic() - started) * 1000)
        job.output_json = model_to_json({**result, "video_asset_id": asset.id})
        job.completed_at = utc_now()
        create_api_usage_log(
            db,
            operation="generate_video",
            provider=job.provider,
            model=job.model,
            generation_job_id=job.id,
            user_id=job.user_id,
            latency_ms=job.latency_ms,
        )
        db.commit()
    except Exception as exc:  # noqa: BLE001 - background errors must be captured in the job row.
        job = db.get(GenerationJob, job_id)
        if job:
            job.status = "failed"
            job.error_message = str(exc)
            job.latency_ms = int((time.monotonic() - started) * 1000)
            job.completed_at = utc_now()
            create_api_usage_log(
                db,
                operation="generate_video",
                provider=job.provider,
                model=job.model,
                generation_job_id=job.id,
                user_id=job.user_id,
                latency_ms=job.latency_ms,
            )
            db.commit()
    finally:
        db.close()


@app.post("/api/video-jobs", response_model=VideoJobCreateResponse, status_code=status.HTTP_201_CREATED)
def create_video_job(
    payload: VideoJobCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VideoJobCreateResponse:
    """Create an asynchronous scene video generation job."""

    payload_data = payload.model_dump()
    if payload.prompt_package_id:
        package = db.get(GeneratedPromptPackage, payload.prompt_package_id)
        if package is None or package.user_id != current_user.id:
            payload_data["prompt_package_id"] = None

    job = GenerationJob(
        user_id=current_user.id,
        job_type="video",
        status="pending",
        provider="mock",
        input_json=model_to_json(payload_data),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    background_tasks.add_task(run_video_generation_job, job.id)
    return VideoJobCreateResponse(job_id=job.id, status=job.status)


@app.get("/api/video-jobs/{job_id}", response_model=VideoJobStatusResponse)
def get_video_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VideoJobStatusResponse:
    """Return one video job if owned by the current user or requested by an admin."""

    job = db.get(GenerationJob, job_id)
    if job is None or job.job_type != "video":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Video job not found.", "error_code": "VIDEO_JOB_NOT_FOUND"},
        )
    if job.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"detail": "You cannot access this video job.", "error_code": "VIDEO_JOB_FORBIDDEN"},
        )

    asset = db.scalar(select(VideoAsset).where(VideoAsset.generation_job_id == job.id).order_by(VideoAsset.id.desc()))
    response = VideoJobStatusResponse.model_validate(job)
    response.video_asset = VideoAssetResponse.model_validate(asset) if asset else None
    return response


@app.post("/api/generate-scene-video", response_model=VideoJobCreateResponse)
def generate_scene_video(
    payload: GenerateSceneVideoRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),  # AUTH ADDITION: protect this API
    db: Session = Depends(get_db),
) -> VideoJobCreateResponse:
    """Backward-compatible wrapper that creates an async video job."""

    return create_video_job(
        VideoJobCreateRequest(
            prompt_en=payload.prompt_en,
            duration_seconds=payload.duration_seconds,
            scene_number=payload.scene_number,
            prompt_package_id=payload.prompt_package_id,
        ),
        background_tasks=background_tasks,
        current_user=current_user,
        db=db,
    )


@app.get("/api/generated/outlines", response_model=list[GeneratedOutlineResponse])
def list_generated_outlines(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[GeneratedOutlineResponse]:
    """List current user's generated outlines."""

    rows = db.scalars(
        select(GeneratedOutline)
        .where(GeneratedOutline.user_id == current_user.id)
        .order_by(GeneratedOutline.created_at.desc(), GeneratedOutline.id.desc())
    ).all()
    return [GeneratedOutlineResponse.model_validate(row) for row in rows]


@app.get("/api/generated/prompts", response_model=list[GeneratedPromptPackageResponse])
def list_generated_prompts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[GeneratedPromptPackageResponse]:
    """List current user's generated prompt packages."""

    rows = db.scalars(
        select(GeneratedPromptPackage)
        .where(GeneratedPromptPackage.user_id == current_user.id)
        .order_by(GeneratedPromptPackage.created_at.desc(), GeneratedPromptPackage.id.desc())
    ).all()
    return [GeneratedPromptPackageResponse.model_validate(row) for row in rows]


@app.get("/api/video-jobs", response_model=list[GenerationJobResponse])
def list_video_jobs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[GenerationJobResponse]:
    """List current user's video jobs."""

    rows = db.scalars(
        select(GenerationJob)
        .where(GenerationJob.user_id == current_user.id, GenerationJob.job_type == "video")
        .order_by(GenerationJob.created_at.desc(), GenerationJob.id.desc())
    ).all()
    return [GenerationJobResponse.model_validate(row) for row in rows]


@app.get("/api/video-assets", response_model=list[VideoAssetResponse])
def list_video_assets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[VideoAssetResponse]:
    """List current user's generated video assets."""

    rows = db.scalars(
        select(VideoAsset)
        .where(VideoAsset.user_id == current_user.id)
        .order_by(VideoAsset.created_at.desc(), VideoAsset.id.desc())
    ).all()
    return [VideoAssetResponse.model_validate(row) for row in rows]


@app.get("/api/system-prompts")
def get_system_prompts(_admin_user: User = Depends(get_current_admin_user)) -> dict[str, str]:
    """Expose core prompts for review during MVP development."""
    return {
        "outline_system_prompt": OUTLINE_SYSTEM_PROMPT,
        "video_prompt_system_prompt": VIDEO_PROMPT_SYSTEM_PROMPT,
    }


@app.get("/api/admin/metrics")
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


@app.get("/api/admin/users", response_model=list[UserResponse])
def list_admin_users(
    _admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[UserResponse]:
    """List users for admin management."""

    users = db.scalars(select(User).order_by(User.created_at.desc(), User.id.desc()).limit(limit).offset(offset)).all()
    return [UserResponse.model_validate(user) for user in users]


@app.get("/api/admin/users/{user_id}")
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


@app.patch("/api/admin/users/{user_id}", response_model=UserResponse)
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


@app.get("/api/admin/questionnaires", response_model=list[QuestionnaireResponse])
def list_admin_questionnaires(
    _admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[QuestionnaireResponse]:
    """List saved questionnaires for admins."""

    rows = db.scalars(select(Questionnaire).order_by(Questionnaire.updated_at.desc()).limit(limit).offset(offset)).all()
    return [QuestionnaireResponse.model_validate(row) for row in rows]


@app.get("/api/admin/generation-jobs", response_model=list[GenerationJobResponse])
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


@app.get("/api/admin/video-assets", response_model=list[VideoAssetResponse])
def list_admin_video_assets(
    _admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[VideoAssetResponse]:
    """List video assets for admins."""

    rows = db.scalars(select(VideoAsset).order_by(VideoAsset.created_at.desc(), VideoAsset.id.desc()).limit(limit).offset(offset)).all()
    return [VideoAssetResponse.model_validate(row) for row in rows]


@app.get("/api/admin/api-usage", response_model=list[ApiUsageLogResponse])
def list_admin_api_usage(
    _admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[ApiUsageLogResponse]:
    """List API usage and cost rows for admins."""

    rows = db.scalars(select(ApiUsageLog).order_by(ApiUsageLog.created_at.desc(), ApiUsageLog.id.desc()).limit(limit).offset(offset)).all()
    return [ApiUsageLogResponse.model_validate(row) for row in rows]


@app.get("/api/admin/action-logs", response_model=list[AdminActionLogResponse])
def list_admin_action_logs(
    _admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[AdminActionLogResponse]:
    """List admin audit events."""

    rows = db.scalars(select(AdminActionLog).order_by(AdminActionLog.created_at.desc(), AdminActionLog.id.desc()).limit(limit).offset(offset)).all()
    return [AdminActionLogResponse.model_validate(row) for row in rows]
