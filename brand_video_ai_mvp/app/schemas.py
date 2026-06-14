"""Pydantic schemas for authentication, questionnaire, and social accounts."""

from datetime import datetime
import re
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class UserRegister(BaseModel):
    """Request body for registering a new user."""

    USERNAME_PATTERN: ClassVar[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9_.@-]+$")

    email: EmailStr
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=8)
    password_confirm: str = Field(..., min_length=8)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        """Allow email-style usernames while blocking whitespace and unsafe symbols."""

        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Username cannot be empty.")
        if not cls.USERNAME_PATTERN.fullmatch(cleaned):
            raise ValueError("Username can only contain letters, numbers, underscores, hyphens, @, and periods.")
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


class ProfileResponse(BaseModel):
    """Profile payload for account settings."""

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
    display_name: str
    display_company_name: str | None = None


BRAND_TONES = (
    "Professional",
    "Friendly",
    "Luxury",
    "Bold",
    "Playful",
    "Educational",
    "Minimal",
    "Inspirational",
)


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


class BrandProfileRequest(BaseModel):
    """Company profile stored during onboarding."""

    company_name: str = Field(..., min_length=1, max_length=255)
    industry: str = Field(..., min_length=1, max_length=255)
    brand_description: str = Field(..., min_length=1)
    brand_tone: Literal[
        "Professional",
        "Friendly",
        "Luxury",
        "Bold",
        "Playful",
        "Educational",
        "Minimal",
        "Inspirational",
    ]
    use_logo_in_prompt: bool = False


class QuestionnaireResponse(BaseModel):
    """Questionnaire record returned from the database."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    brand_name: str | None = None
    company_name: str | None = None
    industry: str | None = None
    brand_description: str | None = None
    brand_tone: str | None = None
    target_audience: str | None = None
    video_style: str | None = None
    logo_url: str | None = None
    logo_path: str | None = None
    use_logo_in_prompt: bool = False
    additional_info: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class BrandProfileResponse(QuestionnaireResponse):
    """Brand Profile response using the compatibility questionnaire row."""


class UploadResponse(BaseModel):
    """Response for uploaded user-owned media."""

    url: str


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
    platform_user_id: str | None = None
    platform_account_name: str | None = None
    connection_status: str = "manual"
    token_expires_at: datetime | None = None
    last_synced_at: datetime | None = None
    linked_at: datetime
    updated_at: datetime | None = None


class YouTubeOAuthConnectResponse(BaseModel):
    """Authorization URL for starting the YouTube OAuth web flow."""

    auth_url: str


class YouTubeSocialAccountSummary(BaseModel):
    """Safe YouTube account summary for the dashboard."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    platform: str
    platform_user_id: str | None = None
    platform_account_name: str | None = None
    account_url: str | None = None
    connection_status: str
    last_synced_at: datetime | None = None
    scopes: str | None = None


class YouTubeChannelMetricResponse(BaseModel):
    """Cached YouTube channel metrics returned to the dashboard."""

    model_config = ConfigDict(from_attributes=True)

    channel_id: str
    channel_title: str
    subscriber_count: int | None = None
    video_count: int | None = None
    view_count: int | None = None
    synced_at: datetime


class YouTubeVideoMetricResponse(BaseModel):
    """Cached recent YouTube video metric returned to the dashboard."""

    model_config = ConfigDict(from_attributes=True)

    provider_video_id: str
    title: str
    thumbnail_url: str | None = None
    published_at: datetime | None = None
    view_count: int | None = None
    like_count: int | None = None
    comment_count: int | None = None
    provider_url: str | None = None
    synced_at: datetime


class YouTubeDashboardResponse(BaseModel):
    """Dashboard state for the current user's connected YouTube channel."""

    connected: bool
    reconnect_required: bool = False
    social_account: YouTubeSocialAccountSummary | None = None
    channel_metrics: YouTubeChannelMetricResponse | None = None
    recent_videos: list[YouTubeVideoMetricResponse] = Field(default_factory=list)
    message: str | None = None


class YouTubeShortUploadRequest(BaseModel):
    """Request body for publishing a generated asset to YouTube via videos.insert."""

    video_asset_id: int
    social_account_id: int
    title: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    tags: list[str] = Field(default_factory=list, max_length=30)
    privacy_status: Literal["private", "unlisted", "public"] = "private"
    contains_synthetic_media: bool = False

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, tags: list[str]) -> list[str]:
        """Trim tags, remove empties, and keep the request small for YouTube."""

        cleaned: list[str] = []
        for tag in tags:
            value = str(tag).strip().lstrip("#")
            if value and value not in cleaned:
                cleaned.append(value[:100])
        return cleaned[:30]


class BrandQuestionnaire(BaseModel):
    """Structured input collected from the merchant questionnaire."""

    brand_name: str = Field(..., min_length=1, description="Brand or store name")
    industry: str = Field(..., min_length=1, description="Industry or business type")
    target_audience: str = Field(..., min_length=1, description="Target audience description")
    brand_keywords: list[str] = Field(
        default_factory=list,
        description="Three adjectives or short brand keywords",
    )
    promotion_theme: str = Field(..., min_length=1, description="Campaign, offer, or topic to promote")
    video_length: str = Field(default="15-30 seconds", description="Preferred TikTok video length")
    language: Literal["zh", "en", "bilingual"] = Field(
        default="zh",
        description="Language for the outline. Video prompts are always English.",
    )

    @field_validator("brand_keywords")
    @classmethod
    def clean_keywords(cls, keywords: list[str]) -> list[str]:
        """Remove empty keywords and keep the first three for MVP consistency."""

        cleaned = [keyword.strip() for keyword in keywords if keyword.strip()]
        return cleaned[:3]


class SceneOutline(BaseModel):
    """One scene in the short-form video outline."""

    scene_number: int
    title: str
    visual_description_zh: str
    voiceover_or_subtitle_zh: str
    duration_seconds: float = Field(..., gt=0)


class VideoOutline(BaseModel):
    """AI-generated video outline shown to the user for human review."""

    hook_zh: str
    structure_summary_zh: str
    scenes: list[SceneOutline] = Field(..., min_length=3, max_length=5)
    voiceover_full_zh: str
    music_style_zh: str
    hashtags: list[str]
    creative_notes_zh: str


class GenerateOutlineRequest(BaseModel):
    """Request body for outline generation."""

    questionnaire: BrandQuestionnaire
    questionnaire_id: int | None = None


class GenerateOutlineResponse(BaseModel):
    """Response returned after outline generation."""

    outline: VideoOutline
    source: Literal["openai", "mock"]
    generated_outline_id: int | None = None
    generation_job_id: int | None = None


class ReviewOutlineRequest(BaseModel):
    """Reviewed outline sent back from the frontend after manual edits."""

    questionnaire: BrandQuestionnaire
    outline: VideoOutline
    target_tool: Literal["sora-2"] = "sora-2"
    questionnaire_id: int | None = None
    generated_outline_id: int | None = None
    outline_id: int | None = None


class ScenePrompt(BaseModel):
    """One English video-generation prompt for a single scene."""

    scene_number: int
    prompt_en: str
    duration_seconds: float = Field(..., gt=0)


class VideoPromptPackage(BaseModel):
    """Final prompt package for video generation tools."""

    platform: Literal["sora-2"]
    aspect_ratio: str = "vertical 9:16"
    global_style_prompt_en: str
    scene_prompts: list[ScenePrompt]
    editing_notes_zh: str


class GeneratePromptsResponse(BaseModel):
    """Response returned after prompt-package generation."""

    prompt_package: VideoPromptPackage
    source: Literal["openai", "mock"]
    generated_prompt_package_id: int | None = None
    generation_job_id: int | None = None


class GenerateSceneVideoRequest(BaseModel):
    """Request body for generating one video clip from one scene prompt."""

    prompt_en: str = Field(..., min_length=1, description="English prompt for one scene")
    duration_seconds: float = Field(default=4, gt=0, description="Requested duration from the scene prompt")
    scene_number: int | None = None
    prompt_package_id: int | None = None


class GenerateSceneVideoResponse(BaseModel):
    """Response returned after one scene video is generated and saved locally."""

    video_id: str
    status: str
    video_url: str
    model: str
    size: str
    seconds: str


class PublishingJobResponse(BaseModel):
    """Publishing job status returned to the frontend."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    video_asset_id: int
    social_account_id: int
    platform: str
    status: Literal["pending", "running", "success", "failed"]
    title: str
    description: str | None = None
    tags_json: str | None = None
    privacy_status: Literal["private", "unlisted", "public"]
    provider_post_id: str | None = None
    provider_post_url: str | None = None
    error_message: str | None = None
    request_json: str | None = None
    response_json: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


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

    email: EmailStr | None = None
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
    prompt_package_id: int | None = None
    scene_number: int | None = None
    provider_video_id: str | None = None
    storage_backend: str | None = None
    video_url: str | None = None
    file_path: str | None = None
    file_size: int | None = None
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
