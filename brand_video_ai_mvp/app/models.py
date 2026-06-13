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

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    """Application user stored in SQLite."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1", nullable=False)

    questionnaires: Mapped[list["Questionnaire"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    social_accounts: Mapped[list["SocialAccount"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


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



class GenerateSceneVideoRequest(BaseModel):
    """Request body for generating one video clip from one scene prompt."""

    prompt_en: str = Field(..., min_length=1, description="English prompt for one scene")
    duration_seconds: float = Field(default=4, gt=0, description="Requested duration from the scene prompt")


class GenerateSceneVideoResponse(BaseModel):
    """Response returned after one scene video is generated and saved locally."""

    video_id: str
    status: str
    video_url: str
    model: str
    size: str
    seconds: str
