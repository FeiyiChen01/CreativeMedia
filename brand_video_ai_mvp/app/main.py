"""FastAPI entry point for the Brand Video AI MVP.

Run locally with:
    uvicorn app.main:app --reload --port 8000
"""

from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

# ==================== AUTH ADDITION: database/auth/schema imports ====================
from app.auth import ACCESS_TOKEN_EXPIRE_DAYS, create_access_token, get_current_user, hash_password, verify_password
from app.database import get_db, init_db
# ==================== END AUTH ADDITION ====================
from app.models import (
    GenerateOutlineRequest,
    GenerateOutlineResponse,
    GeneratePromptsResponse,
    GenerateSceneVideoRequest,
    GenerateSceneVideoResponse,
    Questionnaire,
    ReviewOutlineRequest,
    SocialAccount,
    User,
)
from app.prompts import OUTLINE_SYSTEM_PROMPT, VIDEO_PROMPT_SYSTEM_PROMPT
from app.schemas import (
    QuestionnaireRequest,
    QuestionnaireResponse,
    SocialAccountRequest,
    SocialAccountResponse,
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
)
from app.services.openai_service import AIServiceError, BrandVideoAIService
from app.services.openai_video_service import OpenAIVideoService, VideoGenerationError

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(
    title="Brand Video AI MVP",
    description="AI-powered TikTok outline and video prompt generator for brands.",
    version="0.2.0",
)

# CORS is useful if you later replace static HTML with a React/Vite frontend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
            "errors": exc.errors(),
        },
    )


@app.on_event("startup")
def on_startup() -> None:
    """Initialize SQLite tables when the app starts."""

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
def build_token_response(user: User) -> TokenResponse:
    """Build a JWT response for a successfully authenticated user."""

    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email, "username": user.username},
        expires_delta=timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS),
    )
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
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
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return build_token_response(user)


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

    return build_token_response(user)


@app.post("/api/auth/logout")
def logout_user(_current_user: User = Depends(get_current_user)) -> dict[str, str]:
    """JWT logout is handled by the frontend deleting its stored token."""

    return {"message": "logout success"}


@app.get("/api/auth/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """Return the currently authenticated user."""

    return UserResponse.model_validate(current_user)
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
    questionnaire.brand_description = payload.brand_description
    questionnaire.target_audience = payload.target_audience
    questionnaire.video_style = payload.video_style
    questionnaire.additional_info = payload.additional_info

    db.commit()
    db.refresh(questionnaire)
    return QuestionnaireResponse.model_validate(questionnaire)
# ==================== END AUTH ADDITION ====================


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
# ==================== END AUTH ADDITION ====================


@app.post("/api/generate-outline", response_model=GenerateOutlineResponse)
def generate_outline(
    payload: GenerateOutlineRequest,
    _current_user: User = Depends(get_current_user),  # AUTH ADDITION: protect this API
) -> GenerateOutlineResponse:
    """Step 1: Generate a video outline from questionnaire input."""
    service = BrandVideoAIService()
    try:
        outline, source = service.generate_outline(payload.questionnaire)
        return GenerateOutlineResponse(outline=outline, source=source)
    except AIServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/generate-prompts", response_model=GeneratePromptsResponse)
def generate_prompts(
    payload: ReviewOutlineRequest,
    _current_user: User = Depends(get_current_user),  # AUTH ADDITION: protect this API
) -> GeneratePromptsResponse:
    """Step 3: Convert reviewed outline into English video-generation prompts."""
    service = BrandVideoAIService()
    try:
        prompt_package, source = service.generate_video_prompts(
            questionnaire=payload.questionnaire,
            outline=payload.outline,
            target_tool=payload.target_tool,
        )
        return GeneratePromptsResponse(prompt_package=prompt_package, source=source)
    except AIServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/generate-scene-video", response_model=GenerateSceneVideoResponse)
def generate_scene_video(
    payload: GenerateSceneVideoRequest,
    _current_user: User = Depends(get_current_user),  # AUTH ADDITION: protect this API
) -> GenerateSceneVideoResponse:
    """Step 4: Generate one MP4 video clip from one approved scene prompt."""
    service = OpenAIVideoService(output_dir=STATIC_DIR / "generated_videos")
    try:
        result = service.generate_scene_video(
            prompt=payload.prompt_en,
            duration_seconds=payload.duration_seconds,
        )
        return GenerateSceneVideoResponse(**result)
    except VideoGenerationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/system-prompts")
def get_system_prompts() -> dict[str, str]:
    """Expose core prompts for review during MVP development."""
    return {
        "outline_system_prompt": OUTLINE_SYSTEM_PROMPT,
        "video_prompt_system_prompt": VIDEO_PROMPT_SYSTEM_PROMPT,
    }
