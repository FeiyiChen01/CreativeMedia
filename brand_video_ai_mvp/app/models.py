"""SQLAlchemy ORM models for the Brand Video AI MVP."""

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
    oauth_states: Mapped[list["OAuthState"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    publishing_jobs: Mapped[list["PublishingJob"]] = relationship(
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
    youtube_channel_metrics: Mapped[list["YouTubeChannelMetric"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    youtube_video_metrics: Mapped[list["YouTubeVideoMetric"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class Questionnaire(Base):
    """Saved brand/company profile for one user.

    The table name stays ``questionnaires`` for compatibility with the older
    AI outline/prompt workflow that still references questionnaire_id.
    """

    __tablename__ = "questionnaires"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    brand_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(255), nullable=True)
    brand_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    brand_tone: Mapped[str | None] = mapped_column(String(100), nullable=True)
    target_audience: Mapped[str | None] = mapped_column(String(500), nullable=True)
    video_style: Mapped[str | None] = mapped_column(String(100), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    logo_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    use_logo_in_prompt: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"), nullable=False)
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
    """Manual or OAuth-backed social media account link for one user."""

    __tablename__ = "social_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    account_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    account_handle: Mapped[str | None] = mapped_column(String(100), nullable=True)
    platform_user_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    platform_account_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    access_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scopes: Mapped[str | None] = mapped_column(Text, nullable=True)
    connection_status: Mapped[str] = mapped_column(String(20), default="manual", server_default="manual", nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped[User] = relationship(back_populates="social_accounts")
    publishing_jobs: Mapped[list["PublishingJob"]] = relationship(back_populates="social_account")
    youtube_channel_metrics: Mapped[list["YouTubeChannelMetric"]] = relationship(
        back_populates="social_account",
        cascade="all, delete-orphan",
    )
    youtube_video_metrics: Mapped[list["YouTubeVideoMetric"]] = relationship(
        back_populates="social_account",
        cascade="all, delete-orphan",
    )


class OAuthState(Base):
    """Hashed OAuth state values used to protect callback flows from CSRF."""

    __tablename__ = "oauth_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    state_hash: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    return_to: Mapped[str | None] = mapped_column(String(500), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="oauth_states")


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
    prompt_package_id: Mapped[int | None] = mapped_column(ForeignKey("generated_prompt_packages.id"), nullable=True, index=True)
    scene_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provider_video_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    storage_backend: Mapped[str | None] = mapped_column(String(50), nullable=True)
    video_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    size: Mapped[str | None] = mapped_column(String(50), nullable=True)
    seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="video_assets")
    generation_job: Mapped[GenerationJob] = relationship(back_populates="video_assets")
    publishing_jobs: Mapped[list["PublishingJob"]] = relationship(back_populates="video_asset")


class PublishingJob(Base):
    """Track one attempt to publish a generated video to an external platform."""

    __tablename__ = "publishing_jobs"
    __table_args__ = (
        CheckConstraint("status in ('pending', 'running', 'success', 'failed')", name="ck_publishing_jobs_status"),
        CheckConstraint("privacy_status in ('private', 'unlisted', 'public')", name="ck_publishing_jobs_privacy_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    video_asset_id: Mapped[int] = mapped_column(ForeignKey("video_assets.id"), nullable=False, index=True)
    social_account_id: Mapped[int] = mapped_column(ForeignKey("social_accounts.id"), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(50), default="youtube", server_default="youtube", nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending", nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    privacy_status: Mapped[str] = mapped_column(String(20), default="private", server_default="private", nullable=False)
    provider_post_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    provider_post_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="publishing_jobs")
    video_asset: Mapped[VideoAsset] = relationship(back_populates="publishing_jobs")
    social_account: Mapped[SocialAccount] = relationship(back_populates="publishing_jobs")


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


class YouTubeChannelMetric(Base):
    """Cached YouTube channel metrics for the dashboard."""

    __tablename__ = "youtube_channel_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    social_account_id: Mapped[int] = mapped_column(ForeignKey("social_accounts.id"), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(50), default="youtube", server_default="youtube", nullable=False, index=True)
    channel_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    channel_title: Mapped[str] = mapped_column(String(255), nullable=False)
    subscriber_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    video_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    view_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_response_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped[User] = relationship(back_populates="youtube_channel_metrics")
    social_account: Mapped[SocialAccount] = relationship(back_populates="youtube_channel_metrics")


class YouTubeVideoMetric(Base):
    """Cached recent YouTube video metrics for the dashboard."""

    __tablename__ = "youtube_video_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    social_account_id: Mapped[int] = mapped_column(ForeignKey("social_accounts.id"), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(50), default="youtube", server_default="youtube", nullable=False, index=True)
    provider_video_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    thumbnail_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    view_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    like_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comment_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provider_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    raw_response_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped[User] = relationship(back_populates="youtube_video_metrics")
    social_account: Mapped[SocialAccount] = relationship(back_populates="youtube_video_metrics")
