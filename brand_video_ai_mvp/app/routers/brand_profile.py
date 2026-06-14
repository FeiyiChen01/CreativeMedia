"""Questionnaire, Brand Profile, and account profile routes."""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user, hash_password, verify_password
from app.core import build_profile_response, save_upload_file
from app.database import get_db
from app.models import Questionnaire, User
from app.schemas import BrandProfileRequest, BrandProfileResponse, ChangePasswordRequest, MessageResponse, ProfileResponse, ProfileUpdateRequest, QuestionnaireRequest, QuestionnaireResponse, UploadResponse

router = APIRouter()

@router.get("/api/questionnaire", response_model=QuestionnaireResponse | None)
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


@router.post("/api/questionnaire", response_model=QuestionnaireResponse)
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


@router.get("/api/brand-profile", response_model=BrandProfileResponse | None)
def get_brand_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BrandProfileResponse | None:
    """Return the current user's Brand Profile."""

    profile = get_current_brand_profile(db, current_user.id)
    return BrandProfileResponse.model_validate(profile) if profile else None


@router.post("/api/brand-profile", response_model=BrandProfileResponse, status_code=status.HTTP_201_CREATED)
def create_brand_profile(
    payload: BrandProfileRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BrandProfileResponse:
    """Create or update the current user's Brand Profile."""

    profile = upsert_brand_profile(db, current_user, payload)
    return BrandProfileResponse.model_validate(profile)


@router.put("/api/brand-profile", response_model=BrandProfileResponse)
def update_brand_profile(
    payload: BrandProfileRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BrandProfileResponse:
    """Update the current user's Brand Profile."""

    profile = upsert_brand_profile(db, current_user, payload)
    return BrandProfileResponse.model_validate(profile)


@router.post("/api/brand-profile/logo", response_model=BrandProfileResponse)
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


@router.get("/api/profile", response_model=ProfileResponse)
def get_profile(current_user: User = Depends(get_current_user)) -> ProfileResponse:
    """Return the current user's account profile."""

    return build_profile_response(current_user)


@router.patch("/api/profile", response_model=ProfileResponse)
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


@router.put("/api/profile", response_model=ProfileResponse)
def put_profile(
    payload: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProfileResponse:
    """PUT alias for updating profile settings."""

    return update_profile(payload, current_user, db)


@router.post("/api/profile/avatar", response_model=UploadResponse)
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


@router.post("/api/profile/change-password", response_model=MessageResponse)
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


