"""Initial database schema.

Revision ID: 20260614_0001
Revises:
Create Date: 2026-06-14
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260614_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("users"):
        return

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("company_name", sa.String(length=255), nullable=True),
        sa.Column("avatar_url", sa.String(length=500), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("email_verified", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("role", sa.String(length=20), server_default="user", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("role in ('user', 'admin')", name="ck_users_role"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)

    op.create_table(
        "questionnaires",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("brand_name", sa.String(length=255), nullable=True),
        sa.Column("company_name", sa.String(length=255), nullable=True),
        sa.Column("industry", sa.String(length=255), nullable=True),
        sa.Column("brand_description", sa.Text(), nullable=True),
        sa.Column("brand_tone", sa.String(length=100), nullable=True),
        sa.Column("target_audience", sa.String(length=500), nullable=True),
        sa.Column("video_style", sa.String(length=100), nullable=True),
        sa.Column("logo_url", sa.String(length=500), nullable=True),
        sa.Column("logo_path", sa.String(length=1000), nullable=True),
        sa.Column("use_logo_in_prompt", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("additional_info", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f("ix_questionnaires_user_id"), "questionnaires", ["user_id"], unique=False)

    op.create_table(
        "social_accounts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("platform", sa.String(length=50), nullable=False),
        sa.Column("account_url", sa.String(length=500), nullable=True),
        sa.Column("account_handle", sa.String(length=100), nullable=True),
        sa.Column("platform_user_id", sa.String(length=255), nullable=True),
        sa.Column("platform_account_name", sa.String(length=255), nullable=True),
        sa.Column("access_token_encrypted", sa.Text(), nullable=True),
        sa.Column("refresh_token_encrypted", sa.Text(), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scopes", sa.Text(), nullable=True),
        sa.Column("connection_status", sa.String(length=20), server_default="manual", nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("linked_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )
    op.create_index(op.f("ix_social_accounts_platform"), "social_accounts", ["platform"], unique=False)
    op.create_index(op.f("ix_social_accounts_platform_user_id"), "social_accounts", ["platform_user_id"], unique=False)
    op.create_index(op.f("ix_social_accounts_user_id"), "social_accounts", ["user_id"], unique=False)

    op.create_table(
        "oauth_states",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("state_hash", sa.String(length=255), nullable=False),
        sa.Column("return_to", sa.String(length=500), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f("ix_oauth_states_provider"), "oauth_states", ["provider"], unique=False)
    op.create_index(op.f("ix_oauth_states_state_hash"), "oauth_states", ["state_hash"], unique=True)
    op.create_index(op.f("ix_oauth_states_user_id"), "oauth_states", ["user_id"], unique=False)

    op.create_table(
        "email_verification_tokens",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f("ix_email_verification_tokens_token_hash"), "email_verification_tokens", ["token_hash"], unique=True)
    op.create_index(op.f("ix_email_verification_tokens_user_id"), "email_verification_tokens", ["user_id"], unique=False)

    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f("ix_password_reset_tokens_token_hash"), "password_reset_tokens", ["token_hash"], unique=True)
    op.create_index(op.f("ix_password_reset_tokens_user_id"), "password_reset_tokens", ["user_id"], unique=False)

    op.create_table(
        "generated_outlines",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("questionnaire_id", sa.Integer(), sa.ForeignKey("questionnaires.id"), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("outline_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("source in ('openai', 'mock')", name="ck_generated_outlines_source"),
    )
    op.create_index(op.f("ix_generated_outlines_questionnaire_id"), "generated_outlines", ["questionnaire_id"], unique=False)
    op.create_index(op.f("ix_generated_outlines_user_id"), "generated_outlines", ["user_id"], unique=False)

    op.create_table(
        "generation_jobs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("job_type", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("input_json", sa.Text(), nullable=True),
        sa.Column("output_json", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("estimated_cost", sa.Numeric(10, 6), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("job_type in ('outline', 'prompt', 'video')", name="ck_generation_jobs_job_type"),
        sa.CheckConstraint("provider in ('openai', 'mock')", name="ck_generation_jobs_provider"),
        sa.CheckConstraint("status in ('pending', 'running', 'success', 'failed')", name="ck_generation_jobs_status"),
    )
    op.create_index(op.f("ix_generation_jobs_job_type"), "generation_jobs", ["job_type"], unique=False)
    op.create_index(op.f("ix_generation_jobs_status"), "generation_jobs", ["status"], unique=False)
    op.create_index(op.f("ix_generation_jobs_user_id"), "generation_jobs", ["user_id"], unique=False)

    op.create_table(
        "generated_prompt_packages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("questionnaire_id", sa.Integer(), sa.ForeignKey("questionnaires.id"), nullable=True),
        sa.Column("outline_id", sa.Integer(), sa.ForeignKey("generated_outlines.id"), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("prompt_package_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("source in ('openai', 'mock')", name="ck_generated_prompt_packages_source"),
    )
    op.create_index(op.f("ix_generated_prompt_packages_outline_id"), "generated_prompt_packages", ["outline_id"], unique=False)
    op.create_index(op.f("ix_generated_prompt_packages_questionnaire_id"), "generated_prompt_packages", ["questionnaire_id"], unique=False)
    op.create_index(op.f("ix_generated_prompt_packages_user_id"), "generated_prompt_packages", ["user_id"], unique=False)

    op.create_table(
        "video_assets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("generation_job_id", sa.Integer(), sa.ForeignKey("generation_jobs.id"), nullable=False),
        sa.Column("prompt_package_id", sa.Integer(), sa.ForeignKey("generated_prompt_packages.id"), nullable=True),
        sa.Column("scene_number", sa.Integer(), nullable=True),
        sa.Column("provider_video_id", sa.String(length=255), nullable=True),
        sa.Column("storage_backend", sa.String(length=50), nullable=True),
        sa.Column("video_url", sa.String(length=1000), nullable=True),
        sa.Column("file_path", sa.String(length=1000), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("size", sa.String(length=50), nullable=True),
        sa.Column("seconds", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f("ix_video_assets_generation_job_id"), "video_assets", ["generation_job_id"], unique=False)
    op.create_index(op.f("ix_video_assets_prompt_package_id"), "video_assets", ["prompt_package_id"], unique=False)
    op.create_index(op.f("ix_video_assets_provider_video_id"), "video_assets", ["provider_video_id"], unique=False)
    op.create_index(op.f("ix_video_assets_status"), "video_assets", ["status"], unique=False)
    op.create_index(op.f("ix_video_assets_user_id"), "video_assets", ["user_id"], unique=False)

    op.create_table(
        "api_usage_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("generation_job_id", sa.Integer(), sa.ForeignKey("generation_jobs.id"), nullable=True),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("operation", sa.String(length=100), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("estimated_cost", sa.Numeric(10, 6), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f("ix_api_usage_logs_generation_job_id"), "api_usage_logs", ["generation_job_id"], unique=False)
    op.create_index(op.f("ix_api_usage_logs_operation"), "api_usage_logs", ["operation"], unique=False)
    op.create_index(op.f("ix_api_usage_logs_provider"), "api_usage_logs", ["provider"], unique=False)
    op.create_index(op.f("ix_api_usage_logs_user_id"), "api_usage_logs", ["user_id"], unique=False)

    op.create_table(
        "admin_action_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("admin_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("target_type", sa.String(length=100), nullable=True),
        sa.Column("target_id", sa.String(length=100), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f("ix_admin_action_logs_action"), "admin_action_logs", ["action"], unique=False)
    op.create_index(op.f("ix_admin_action_logs_admin_user_id"), "admin_action_logs", ["admin_user_id"], unique=False)

    op.create_table(
        "publishing_jobs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("video_asset_id", sa.Integer(), sa.ForeignKey("video_assets.id"), nullable=False),
        sa.Column("social_account_id", sa.Integer(), sa.ForeignKey("social_accounts.id"), nullable=False),
        sa.Column("platform", sa.String(length=50), server_default="youtube", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("tags_json", sa.Text(), nullable=True),
        sa.Column("privacy_status", sa.String(length=20), server_default="private", nullable=False),
        sa.Column("provider_post_id", sa.String(length=255), nullable=True),
        sa.Column("provider_post_url", sa.String(length=1000), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("request_json", sa.Text(), nullable=True),
        sa.Column("response_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("privacy_status in ('private', 'unlisted', 'public')", name="ck_publishing_jobs_privacy_status"),
        sa.CheckConstraint("status in ('pending', 'running', 'success', 'failed')", name="ck_publishing_jobs_status"),
    )
    op.create_index(op.f("ix_publishing_jobs_platform"), "publishing_jobs", ["platform"], unique=False)
    op.create_index(op.f("ix_publishing_jobs_provider_post_id"), "publishing_jobs", ["provider_post_id"], unique=False)
    op.create_index(op.f("ix_publishing_jobs_social_account_id"), "publishing_jobs", ["social_account_id"], unique=False)
    op.create_index(op.f("ix_publishing_jobs_status"), "publishing_jobs", ["status"], unique=False)
    op.create_index(op.f("ix_publishing_jobs_user_id"), "publishing_jobs", ["user_id"], unique=False)
    op.create_index(op.f("ix_publishing_jobs_video_asset_id"), "publishing_jobs", ["video_asset_id"], unique=False)


def downgrade() -> None:
    op.drop_table("publishing_jobs")
    op.drop_table("admin_action_logs")
    op.drop_table("api_usage_logs")
    op.drop_table("video_assets")
    op.drop_table("generated_prompt_packages")
    op.drop_table("generation_jobs")
    op.drop_table("generated_outlines")
    op.drop_table("password_reset_tokens")
    op.drop_table("email_verification_tokens")
    op.drop_table("oauth_states")
    op.drop_table("social_accounts")
    op.drop_table("questionnaires")
    op.drop_table("users")
