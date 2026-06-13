"""Pydantic request/response models for the Brand Video AI MVP.

Keeping these models in one file makes the API contract easy to understand
and easy to change when the questionnaire grows later.
"""


# ==================== AUTH / DATABASE MODELS ADDITION ====================
# These SQLAlchemy ORM models back the new user authentication, questionnaire,
# and social account features. Existing Pydantic video-generation schemas below
# are intentionally preserved for the current AI workflow.

import json
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Integer, Numeric, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    """Application user."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role in ('user', 'admin')", name="ck_users_role"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=text("false"),
        nullable=False,
    )
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    role: Mapped[str] = mapped_column(String(20), default="user", server_default="user", nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=text("true"),
        nullable=False,
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    questionnaires: Mapped[list["Questionnaire"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    social_accounts: Mapped[list["SocialAccount"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    email_verification_tokens: Mapped[list["EmailVerificationToken"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    password_reset_tokens: Mapped[list["PasswordResetToken"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    generated_outlines: Mapped[list["GeneratedOutline"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    generated_prompt_packages: Mapped[list["GeneratedPromptPackage"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    generation_jobs: Mapped[list["GenerationJob"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    video_assets: Mapped[list["VideoAsset"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    api_usage_logs: Mapped[list["ApiUsageLog"]] = relationship(back_populates="user")
    admin_action_logs: Mapped[list["AdminActionLog"]] = relationship(back_populates="admin_user")


class Questionnaire(Base):
    """Saved brand onboarding questionnaire for one user."""

    __tablename__ = "questionnaires"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    brand_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    brand_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_audience: Mapped[str | None] = mapped_column(String(500), nullable=True)
    video_style: Mapped[str | None] = mapped_column(String(100), nullable=True)
    additional_info_raw: Mapped[str | None] = mapped_column("additional_info", Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped[User] = relationship(back_populates="questionnaires")

    @property
    def additional_info(self) -> dict | None:
        """Return additional_info JSON text as a Python dict for Pydantic responses."""

        if not self.additional_info_raw:
            return None
        try:
            return json.loads(self.additional_info_raw)
        except json.JSONDecodeError:
            return None

    @additional_info.setter
    def additional_info(self, value: dict | None) -> None:
        """Store a Python dict as JSON text in SQLite."""

        self.additional_info_raw = json.dumps(value, ensure_ascii=False) if value else None


class SocialAccount(Base):
    """Manual social media account link for one user."""

    __tablename__ = "social_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    account_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    account_handle: Mapped[str | None] = mapped_column(String(100), nullable=True)
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="social_accounts")


class EmailVerificationToken(Base):
    """Hashed one-time token for future email verification flows."""

    __tablename__ = "email_verification_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="email_verification_tokens")


class PasswordResetToken(Base):
    """Hashed one-time token for future password reset flows."""

    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="password_reset_tokens")


class GeneratedOutline(Base):
    """Persistable AI/mock outline payload for a future generation history."""

    __tablename__ = "generated_outlines"
    __table_args__ = (
        CheckConstraint("source in ('openai', 'mock')", name="ck_generated_outlines_source"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    questionnaire_id: Mapped[int | None] = mapped_column(ForeignKey("questionnaires.id"), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    outline_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="generated_outlines")
    questionnaire: Mapped[Questionnaire | None] = relationship()
    prompt_packages: Mapped[list["GeneratedPromptPackage"]] = relationship(back_populates="outline")


class GeneratedPromptPackage(Base):
    """Persistable prompt-package payload for a future generation history."""

    __tablename__ = "generated_prompt_packages"
    __table_args__ = (
        CheckConstraint("source in ('openai', 'mock')", name="ck_generated_prompt_packages_source"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    questionnaire_id: Mapped[int | None] = mapped_column(ForeignKey("questionnaires.id"), nullable=True, index=True)
    outline_id: Mapped[int | None] = mapped_column(ForeignKey("generated_outlines.id"), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    prompt_package_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="generated_prompt_packages")
    questionnaire: Mapped[Questionnaire | None] = relationship()
    outline: Mapped[GeneratedOutline | None] = relationship(back_populates="prompt_packages")


class GenerationJob(Base):
    """Track future outline, prompt, and video generation jobs."""

    __tablename__ = "generation_jobs"
    __table_args__ = (
        CheckConstraint("job_type in ('outline', 'prompt', 'video')", name="ck_generation_jobs_job_type"),
        CheckConstraint("status in ('pending', 'running', 'success', 'failed')", name="ck_generation_jobs_status"),
        CheckConstraint("provider in ('openai', 'mock')", name="ck_generation_jobs_provider"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    job_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    input_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="generation_jobs")
    video_assets: Mapped[list["VideoAsset"]] = relationship(back_populates="generation_job")
    api_usage_logs: Mapped[list["ApiUsageLog"]] = relationship(back_populates="generation_job")


class VideoAsset(Base):
    """Metadata for future generated video clips."""

    __tablename__ = "video_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    generation_job_id: Mapped[int] = mapped_column(ForeignKey("generation_jobs.id"), nullable=False, index=True)
    scene_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provider_video_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    video_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    size: Mapped[str | None] = mapped_column(String(50), nullable=True)
    seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="video_assets")
    generation_job: Mapped[GenerationJob] = relationship(back_populates="video_assets")


class ApiUsageLog(Base):
    """Provider usage and cost accounting for future analytics."""

    __tablename__ = "api_usage_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    generation_job_id: Mapped[int | None] = mapped_column(ForeignKey("generation_jobs.id"), nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    operation: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User | None] = relationship(back_populates="api_usage_logs")
    generation_job: Mapped[GenerationJob | None] = relationship(back_populates="api_usage_logs")


class AdminActionLog(Base):
    """Audit trail for future admin actions."""

    __tablename__ = "admin_action_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    admin_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    target_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    admin_user: Mapped[User] = relationship(back_populates="admin_action_logs")

# ==================== END AUTH / DATABASE MODELS ADDITION ====================

from typing import Literal

from pydantic import BaseModel, Field, field_validator


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
    questionnaire: BrandQuestionnaire


class GenerateOutlineResponse(BaseModel):
    outline: VideoOutline
    source: Literal["openai", "mock"]
    generated_outline_id: int | None = None
    generation_job_id: int | None = None


class ReviewOutlineRequest(BaseModel):
    """Reviewed outline sent back from the frontend after manual edits."""

    questionnaire: BrandQuestionnaire
    outline: VideoOutline
    target_tool: Literal["sora-2"] = "sora-2"


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
