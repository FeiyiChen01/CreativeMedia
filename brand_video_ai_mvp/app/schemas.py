"""Pydantic schemas for authentication, questionnaire, and social accounts."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class UserRegister(BaseModel):
    """Request body for registering a new user."""

    email: EmailStr
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=8)
    password_confirm: str = Field(..., min_length=8)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        """Allow simple usernames that are safe to display and query."""

        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Username cannot be empty.")
        if not cleaned.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Username can only contain letters, numbers, underscores, and hyphens.")
        return cleaned

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        """Require at least 1 uppercase, 1 lowercase, and 1 digit."""

        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        if not any(char.isupper() for char in value):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not any(char.islower() for char in value):
            raise ValueError("Password must contain at least one lowercase letter.")
        if not any(char.isdigit() for char in value):
            raise ValueError("Password must contain at least one number.")
        return value

    @model_validator(mode="after")
    def validate_passwords_match(self) -> "UserRegister":
        """Ensure password and confirmation match."""

        if self.password != self.password_confirm:
            raise ValueError("Password confirmation does not match.")
        return self


class UserLogin(BaseModel):
    """Request body for logging in."""

    email: EmailStr
    password: str = Field(..., min_length=1)


class UserResponse(BaseModel):
    """Safe user payload returned to the frontend. Password hashes are excluded."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    username: str
    full_name: str | None = None
    company_name: str | None = None
    avatar_url: str | None = None
    phone: str | None = None
    email_verified: bool = False
    email_verified_at: datetime | None = None
    role: Literal["user", "admin"] = "user"
    is_active: bool = True
    last_login_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class TokenResponse(BaseModel):
    """JWT response returned after register/login."""

    access_token: str
    token_type: Literal["bearer"] = "bearer"
    user: UserResponse
    message: str | None = None


class MessageResponse(BaseModel):
    """Simple API message response."""

    message: str


class QuestionnaireRequest(BaseModel):
    """Brand questionnaire stored per user after registration/onboarding."""

    brand_name: str = Field(..., min_length=1, max_length=255)
    brand_description: str = Field(..., min_length=1)
    target_audience: str = Field(..., min_length=1, max_length=500)
    video_style: str = Field(..., min_length=1, max_length=100)
    additional_info: dict[str, Any] | None = None


class QuestionnaireResponse(BaseModel):
    """Questionnaire record returned from the database."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    brand_name: str | None = None
    brand_description: str | None = None
    target_audience: str | None = None
    video_style: str | None = None
    additional_info: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class SocialAccountRequest(BaseModel):
    """Manual social account binding. OAuth can be added later."""

    platform: Literal["instagram", "tiktok", "youtube", "facebook", "x", "linkedin"]
    account_url: str | None = Field(default=None, max_length=500)
    account_handle: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def require_url_or_handle(self) -> "SocialAccountRequest":
        """Require at least one identifier for a linked social account."""

        if not self.account_url and not self.account_handle:
            raise ValueError("Please provide either account_url or account_handle.")
        return self


class SocialAccountResponse(BaseModel):
    """Stored social media account returned to the frontend."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    platform: str
    account_url: str | None = None
    account_handle: str | None = None
    linked_at: datetime


class EmailVerificationTokenResponse(BaseModel):
    """Stored email verification token metadata. Token hashes stay server-side."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    expires_at: datetime
    used_at: datetime | None = None
    created_at: datetime


class PasswordResetTokenResponse(BaseModel):
    """Stored password reset token metadata. Token hashes stay server-side."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    expires_at: datetime
    used_at: datetime | None = None
    created_at: datetime


class ForgotPasswordRequest(BaseModel):
    """Request a password reset email without revealing account existence."""

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Complete password reset with a one-time token."""

    token: str = Field(..., min_length=16)
    new_password: str = Field(..., min_length=8)
    new_password_confirm: str = Field(..., min_length=8)

    @field_validator("new_password")
    @classmethod
    def validate_new_password_strength(cls, value: str) -> str:
        """Reuse the registration password strength rules."""

        return UserRegister.validate_password_strength(value)

    @model_validator(mode="after")
    def validate_new_passwords_match(self) -> "ResetPasswordRequest":
        """Ensure new password and confirmation match."""

        if self.new_password != self.new_password_confirm:
            raise ValueError("Password confirmation does not match.")
        return self


class ProfileUpdateRequest(BaseModel):
    """Fields a user may update on their own profile."""

    username: str | None = Field(default=None, min_length=3, max_length=100)
    full_name: str | None = Field(default=None, max_length=255)
    company_name: str | None = Field(default=None, max_length=255)
    avatar_url: str | None = Field(default=None, max_length=500)

    @field_validator("username")
    @classmethod
    def validate_optional_username(cls, value: str | None) -> str | None:
        """Use the same username format rules as registration when provided."""

        if value is None:
            return value
        return UserRegister.validate_username(value)


class ChangePasswordRequest(BaseModel):
    """Authenticated password change request."""

    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8)
    new_password_confirm: str = Field(..., min_length=8)

    @field_validator("new_password")
    @classmethod
    def validate_new_password_strength(cls, value: str) -> str:
        """Reuse the registration password strength rules."""

        return UserRegister.validate_password_strength(value)

    @model_validator(mode="after")
    def validate_new_passwords_match(self) -> "ChangePasswordRequest":
        """Ensure new password and confirmation match."""

        if self.new_password != self.new_password_confirm:
            raise ValueError("Password confirmation does not match.")
        return self


class GeneratedOutlineResponse(BaseModel):
    """Future generated outline persistence response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    questionnaire_id: int | None = None
    source: Literal["openai", "mock"]
    outline_json: str
    created_at: datetime


class GeneratedPromptPackageResponse(BaseModel):
    """Future generated prompt package persistence response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    questionnaire_id: int | None = None
    outline_id: int | None = None
    source: Literal["openai", "mock"]
    prompt_package_json: str
    created_at: datetime


class GenerationJobResponse(BaseModel):
    """Future generation job response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    job_type: Literal["outline", "prompt", "video"]
    status: Literal["pending", "running", "success", "failed"]
    provider: Literal["openai", "mock"]
    model: str | None = None
    input_json: str | None = None
    output_json: str | None = None
    error_message: str | None = None
    latency_ms: int | None = None
    estimated_cost: float | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class VideoJobCreateRequest(BaseModel):
    """Create an asynchronous video generation job."""

    prompt_en: str = Field(..., min_length=1)
    duration_seconds: float = Field(default=4, gt=0)
    scene_number: int | None = None
    prompt_package_id: int | None = None


class VideoJobCreateResponse(BaseModel):
    """Initial video job creation response."""

    job_id: int
    status: Literal["pending", "running", "success", "failed"]


class VideoJobStatusResponse(GenerationJobResponse):
    """Video job status plus generated asset when complete."""

    video_asset: "VideoAssetResponse | None" = None


class AdminUserUpdateRequest(BaseModel):
    """Admin-manageable user fields."""

    is_active: bool | None = None
    role: Literal["user", "admin"] | None = None
    email_verified: bool | None = None


class VideoAssetResponse(BaseModel):
    """Future generated video asset response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    generation_job_id: int
    scene_number: int | None = None
    provider_video_id: str | None = None
    video_url: str | None = None
    file_path: str | None = None
    model: str | None = None
    size: str | None = None
    seconds: float | None = None
    status: str
    created_at: datetime


class ApiUsageLogResponse(BaseModel):
    """Future API usage log response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int | None = None
    generation_job_id: int | None = None
    provider: str
    model: str
    operation: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost: float | None = None
    latency_ms: int | None = None
    created_at: datetime


class AdminActionLogResponse(BaseModel):
    """Future admin action audit response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    admin_user_id: int
    action: str
    target_type: str | None = None
    target_id: str | None = None
    metadata_json: str | None = None
    created_at: datetime
