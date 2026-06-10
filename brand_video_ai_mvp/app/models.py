"""Pydantic request/response models for the Brand Video AI MVP.

Keeping these models in one file makes the API contract easy to understand
and easy to change when the questionnaire grows later.
"""

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
    target_tool: Literal["Runway Gen-3", "Kling", "Pika", "Generic"] = "Generic"


class ScenePrompt(BaseModel):
    """One English video-generation prompt for a single scene."""

    scene_number: int
    prompt_en: str
    duration_seconds: float = Field(..., gt=0)


class VideoPromptPackage(BaseModel):
    """Final prompt package for video generation tools."""

    platform: Literal["Runway Gen-3", "Kling", "Pika", "Generic"]
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

