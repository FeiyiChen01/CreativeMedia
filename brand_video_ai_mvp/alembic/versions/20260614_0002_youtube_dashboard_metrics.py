"""Add YouTube dashboard metric tables.

Revision ID: 20260614_0002
Revises: 20260614_0001
Create Date: 2026-06-14
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260614_0002"
down_revision: str | None = "20260614_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())

    if not inspector.has_table("youtube_channel_metrics"):
        op.create_table(
            "youtube_channel_metrics",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("social_account_id", sa.Integer(), sa.ForeignKey("social_accounts.id"), nullable=False),
            sa.Column("platform", sa.String(length=50), server_default="youtube", nullable=False),
            sa.Column("channel_id", sa.String(length=255), nullable=False),
            sa.Column("channel_title", sa.String(length=255), nullable=False),
            sa.Column("subscriber_count", sa.Integer(), nullable=True),
            sa.Column("video_count", sa.Integer(), nullable=True),
            sa.Column("view_count", sa.Integer(), nullable=True),
            sa.Column("raw_response_json", sa.Text(), nullable=True),
            sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index(op.f("ix_youtube_channel_metrics_channel_id"), "youtube_channel_metrics", ["channel_id"], unique=False)
        op.create_index(op.f("ix_youtube_channel_metrics_platform"), "youtube_channel_metrics", ["platform"], unique=False)
        op.create_index(op.f("ix_youtube_channel_metrics_social_account_id"), "youtube_channel_metrics", ["social_account_id"], unique=False)
        op.create_index(op.f("ix_youtube_channel_metrics_synced_at"), "youtube_channel_metrics", ["synced_at"], unique=False)
        op.create_index(op.f("ix_youtube_channel_metrics_user_id"), "youtube_channel_metrics", ["user_id"], unique=False)

    if not inspector.has_table("youtube_video_metrics"):
        op.create_table(
            "youtube_video_metrics",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("social_account_id", sa.Integer(), sa.ForeignKey("social_accounts.id"), nullable=False),
            sa.Column("platform", sa.String(length=50), server_default="youtube", nullable=False),
            sa.Column("provider_video_id", sa.String(length=255), nullable=False),
            sa.Column("title", sa.String(length=500), nullable=False),
            sa.Column("thumbnail_url", sa.String(length=1000), nullable=True),
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("view_count", sa.Integer(), nullable=True),
            sa.Column("like_count", sa.Integer(), nullable=True),
            sa.Column("comment_count", sa.Integer(), nullable=True),
            sa.Column("provider_url", sa.String(length=1000), nullable=True),
            sa.Column("raw_response_json", sa.Text(), nullable=True),
            sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index(op.f("ix_youtube_video_metrics_platform"), "youtube_video_metrics", ["platform"], unique=False)
        op.create_index(op.f("ix_youtube_video_metrics_provider_video_id"), "youtube_video_metrics", ["provider_video_id"], unique=False)
        op.create_index(op.f("ix_youtube_video_metrics_social_account_id"), "youtube_video_metrics", ["social_account_id"], unique=False)
        op.create_index(op.f("ix_youtube_video_metrics_synced_at"), "youtube_video_metrics", ["synced_at"], unique=False)
        op.create_index(op.f("ix_youtube_video_metrics_user_id"), "youtube_video_metrics", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_youtube_video_metrics_user_id"), table_name="youtube_video_metrics")
    op.drop_index(op.f("ix_youtube_video_metrics_synced_at"), table_name="youtube_video_metrics")
    op.drop_index(op.f("ix_youtube_video_metrics_social_account_id"), table_name="youtube_video_metrics")
    op.drop_index(op.f("ix_youtube_video_metrics_provider_video_id"), table_name="youtube_video_metrics")
    op.drop_index(op.f("ix_youtube_video_metrics_platform"), table_name="youtube_video_metrics")
    op.drop_table("youtube_video_metrics")

    op.drop_index(op.f("ix_youtube_channel_metrics_user_id"), table_name="youtube_channel_metrics")
    op.drop_index(op.f("ix_youtube_channel_metrics_synced_at"), table_name="youtube_channel_metrics")
    op.drop_index(op.f("ix_youtube_channel_metrics_social_account_id"), table_name="youtube_channel_metrics")
    op.drop_index(op.f("ix_youtube_channel_metrics_platform"), table_name="youtube_channel_metrics")
    op.drop_index(op.f("ix_youtube_channel_metrics_channel_id"), table_name="youtube_channel_metrics")
    op.drop_table("youtube_channel_metrics")
