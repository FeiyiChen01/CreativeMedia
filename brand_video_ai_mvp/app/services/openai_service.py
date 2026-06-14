"""AI service layer for generating outlines and video prompts.

The route layer should not know how OpenAI is called. This file is the only
place that talks to the AI provider, which makes it easy to swap OpenAI for
Claude later.
"""

import json
import os
import re
from typing import Any, TypeVar

try:
    from openai import OpenAI
except ImportError:  # Allows mock mode even before dependencies are installed.
    OpenAI = None  # type: ignore[assignment]
from pydantic import BaseModel, ValidationError

from app.schemas import (
    BrandQuestionnaire,
    SceneOutline,
    ScenePrompt,
    VideoOutline,
    VideoPromptPackage,
)
from app.prompts import OUTLINE_SYSTEM_PROMPT, VIDEO_PROMPT_SYSTEM_PROMPT

T = TypeVar("T", bound=BaseModel)


class AIServiceError(RuntimeError):
    """Raised when the AI provider fails or returns invalid data."""


class BrandVideoAIService:
    """Service for Step 1 and Step 3 of the MVP workflow."""

    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.model = os.getenv("OPENAI_MODEL", "gpt-5.4-mini").strip()
        self.allow_mock = os.getenv("ALLOW_MOCK_AI", "true").lower() == "true"
        self.client = self._build_client()

    def generate_outline(self, questionnaire: BrandQuestionnaire) -> tuple[VideoOutline, str]:
        """Generate Step 1 video outline from questionnaire data."""
        if not self.client:
            return self._mock_outline(questionnaire), "mock"

        user_prompt = {
            "task": "Generate a TikTok short-form video outline from this questionnaire.",
            "output_language": questionnaire.language,
            "language_instruction": self._language_instruction(questionnaire.language),
            "questionnaire": questionnaire.model_dump(),
        }
        return self._call_json_model(
            system_prompt=OUTLINE_SYSTEM_PROMPT,
            user_payload=user_prompt,
            response_model=VideoOutline,
        ), "openai"

    def generate_video_prompts(
        self,
        questionnaire: BrandQuestionnaire,
        outline: VideoOutline,
        target_tool: str,
    ) -> tuple[VideoPromptPackage, str]:
        """Generate Step 3 English video-generation prompts from approved outline."""
        if not self.client:
            return self._mock_prompt_package(outline, target_tool, questionnaire.language), "mock"

        user_prompt = {
            "task": "Convert the approved outline into English video-generation prompts.",
            "target_tool": target_tool,
            "output_language": questionnaire.language,
            "language_instruction": self._language_instruction(questionnaire.language),
            "questionnaire": questionnaire.model_dump(),
            "approved_outline": outline.model_dump(),
        }
        return self._call_json_model(
            system_prompt=VIDEO_PROMPT_SYSTEM_PROMPT,
            user_payload=user_prompt,
            response_model=VideoPromptPackage,
        ), "openai"

    def _build_client(self):
        """Create the OpenAI client only when a real API key is available."""
        if not self.api_key or self.api_key.startswith("sk-your"):
            if self.allow_mock:
                return None
            raise AIServiceError("OPENAI_API_KEY is missing. Add it to .env or set ALLOW_MOCK_AI=true.")
        if OpenAI is None:
            raise AIServiceError("The openai package is not installed. Run: pip install -r requirements.txt")
        return OpenAI(api_key=self.api_key)

    def _call_json_model(self, system_prompt: str, user_payload: dict[str, Any], response_model: type[T]) -> T:
        """Call OpenAI Responses API and validate the JSON response with Pydantic."""
        try:
            # Responses API uses `input`, not `messages`.
            # JSON mode for Responses API uses `text={"format": {"type": "json_object"}}`,
            # not the older Chat Completions `response_format={...}` style.
            response = self.client.responses.create(  # type: ignore[union-attr]
                model=self.model,
                input=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": json.dumps(user_payload, ensure_ascii=False),
                    },
                ],
                text={"format": {"type": "json_object"}},
            )

            content = response.output_text or "{}"
            data = self._parse_json_object(content)
            return response_model.model_validate(data)
        except ValidationError as exc:
            raise AIServiceError(f"AI returned JSON, but it did not match the expected schema: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise AIServiceError(f"AI returned text, but it was not valid JSON: {exc}") from exc
        except Exception as exc:  # noqa: BLE001 - keep API errors readable for MVP users.
            raise AIServiceError(f"AI generation failed: {exc}") from exc

    @staticmethod
    def _language_instruction(language: str) -> str:
        """Return a plain-language instruction for bilingual output behavior."""
        if language == "en":
            return "Write all user-facing outline fields and editing notes in English. Keep video prompt fields in English."
        if language == "bilingual":
            return "Write user-facing outline fields and editing notes in both Simplified Chinese and English. Keep video prompt fields in English."
        return "Write all user-facing outline fields and editing notes in Simplified Chinese. Keep video prompt fields in English."

    @staticmethod
    def _parse_json_object(content: str) -> dict[str, Any]:
        """Parse JSON even if the provider accidentally returns fenced code."""
        cleaned = content.strip()
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
        return json.loads(cleaned)

    @staticmethod
    def _mock_outline(questionnaire: BrandQuestionnaire) -> VideoOutline:
        """Local demo output so teammates can test the UI without an API key."""
        if questionnaire.language == "en":
            return BrandVideoAIService._mock_outline_en(questionnaire)
        if questionnaire.language == "bilingual":
            return BrandVideoAIService._mock_outline_bilingual(questionnaire)
        return BrandVideoAIService._mock_outline_zh(questionnaire)

    @staticmethod
    def _mock_outline_zh(questionnaire: BrandQuestionnaire) -> VideoOutline:
        """Chinese mock outline."""
        brand = questionnaire.brand_name
        audience = questionnaire.target_audience
        theme = questionnaire.promotion_theme
        keywords = "、".join(questionnaire.brand_keywords) or "专业、可信、有记忆点"
        first_keyword = questionnaire.brand_keywords[0] if questionnaire.brand_keywords else "省心"
        return VideoOutline(
            hook_zh=f"你是不是也在找一个更{first_keyword}的选择？",
            structure_summary_zh=f"用问题开场引起{audience}共鸣，再展示 {brand} 的核心卖点，最后用 {theme} 引导行动。",
            scenes=[
                SceneOutline(
                    scene_number=1,
                    title="痛点开场",
                    visual_description_zh=f"快速切入目标用户的日常场景，突出他们正在遇到的问题。品牌调性：{keywords}。",
                    voiceover_or_subtitle_zh=f"还在为这个问题浪费时间吗？{brand} 可能正是你需要的答案。",
                    duration_seconds=4,
                ),
                SceneOutline(
                    scene_number=2,
                    title="品牌出现",
                    visual_description_zh=f"展示 {brand} 的产品/服务细节，用干净的近景镜头建立信任感。",
                    voiceover_or_subtitle_zh=f"我们为{audience}打造更简单、更直接的体验。",
                    duration_seconds=5,
                ),
                SceneOutline(
                    scene_number=3,
                    title="活动强化",
                    visual_description_zh=f"用动态画面展示近期推广主题：{theme}，强化限时感和行动理由。",
                    voiceover_or_subtitle_zh=f"现在参与：{theme}，让你的选择更轻松。",
                    duration_seconds=5,
                ),
                SceneOutline(
                    scene_number=4,
                    title="行动号召",
                    visual_description_zh="结尾展示品牌 Logo 或产品 Hero Shot，画面干净、有记忆点。",
                    voiceover_or_subtitle_zh=f"关注 {brand}，现在就了解更多。",
                    duration_seconds=4,
                ),
            ],
            voiceover_full_zh=(
                f"还在为这个问题浪费时间吗？{brand} 可能正是你需要的答案。"
                f"我们为{audience}打造更简单、更直接的体验。"
                f"现在参与：{theme}，让你的选择更轻松。关注 {brand}，现在就了解更多。"
            ),
            music_style_zh="节奏轻快、现代感强的 TikTok 流行电子/轻鼓点背景音乐",
            hashtags=["#TikTokMadeMeBuyIt", "#SmallBusiness", "#BrandStory", "#DailyFinds", "#ForYou"],
            creative_notes_zh="这是 Mock 输出，用于本地测试。切换到英文页面后，Mock 也会返回英文内容。",
        )

    @staticmethod
    def _mock_outline_en(questionnaire: BrandQuestionnaire) -> VideoOutline:
        """English mock outline. Field names stay the same for API compatibility."""
        brand = questionnaire.brand_name
        audience = questionnaire.target_audience
        theme = questionnaire.promotion_theme
        keywords = ", ".join(questionnaire.brand_keywords) or "professional, trustworthy, memorable"
        first_keyword = questionnaire.brand_keywords[0] if questionnaire.brand_keywords else "effortless"
        return VideoOutline(
            hook_zh=f"Looking for a more {first_keyword} way to upgrade your routine?",
            structure_summary_zh=f"Open with a relatable problem for {audience}, introduce {brand}'s key value, then use {theme} as the call-to-action.",
            scenes=[
                SceneOutline(
                    scene_number=1,
                    title="Problem Hook",
                    visual_description_zh=f"Quickly show the target customer's everyday pain point in a vertical TikTok-style shot. Brand tone: {keywords}.",
                    voiceover_or_subtitle_zh=f"Still spending too much time on this problem? {brand} might be exactly what you need.",
                    duration_seconds=4,
                ),
                SceneOutline(
                    scene_number=2,
                    title="Brand Reveal",
                    visual_description_zh=f"Show clean product or service details from {brand} with close-up shots that build trust.",
                    voiceover_or_subtitle_zh=f"Designed for {audience}, with a simpler and more direct experience.",
                    duration_seconds=5,
                ),
                SceneOutline(
                    scene_number=3,
                    title="Campaign Moment",
                    visual_description_zh=f"Use dynamic visuals to highlight the campaign: {theme}, creating a clear reason to act now.",
                    voiceover_or_subtitle_zh=f"Now featuring: {theme}. Make your next choice feel easier.",
                    duration_seconds=5,
                ),
                SceneOutline(
                    scene_number=4,
                    title="Call to Action",
                    visual_description_zh="End with a clean hero shot of the brand, product, or service with a memorable final frame.",
                    voiceover_or_subtitle_zh=f"Follow {brand} to learn more today.",
                    duration_seconds=4,
                ),
            ],
            voiceover_full_zh=(
                f"Still spending too much time on this problem? {brand} might be exactly what you need. "
                f"Designed for {audience}, with a simpler and more direct experience. "
                f"Now featuring: {theme}. Make your next choice feel easier. Follow {brand} to learn more today."
            ),
            music_style_zh="Upbeat modern TikTok pop-electronic track with light percussion and a clean commercial feel",
            hashtags=["#TikTokMadeMeBuyIt", "#SmallBusiness", "#BrandStory", "#DailyFinds", "#ForYou"],
            creative_notes_zh="This is Mock output for local testing. In English mode, the outline content is returned in English while the video prompts remain English as well.",
        )

    @staticmethod
    def _mock_outline_bilingual(questionnaire: BrandQuestionnaire) -> VideoOutline:
        """Simple bilingual mock outline."""
        zh = BrandVideoAIService._mock_outline_zh(questionnaire)
        en = BrandVideoAIService._mock_outline_en(questionnaire)
        return VideoOutline(
            hook_zh=f"{zh.hook_zh}\n{en.hook_zh}",
            structure_summary_zh=f"{zh.structure_summary_zh}\n{en.structure_summary_zh}",
            scenes=[
                SceneOutline(
                    scene_number=z.scene_number,
                    title=f"{z.title} / {e.title}",
                    visual_description_zh=f"{z.visual_description_zh}\n{e.visual_description_zh}",
                    voiceover_or_subtitle_zh=f"{z.voiceover_or_subtitle_zh}\n{e.voiceover_or_subtitle_zh}",
                    duration_seconds=z.duration_seconds,
                )
                for z, e in zip(zh.scenes, en.scenes)
            ],
            voiceover_full_zh=f"{zh.voiceover_full_zh}\n{en.voiceover_full_zh}",
            music_style_zh=f"{zh.music_style_zh}\n{en.music_style_zh}",
            hashtags=zh.hashtags,
            creative_notes_zh=f"{zh.creative_notes_zh}\n{en.creative_notes_zh}",
        )

    @staticmethod
    def _mock_prompt_package(outline: VideoOutline, target_tool: str, language: str = "zh") -> VideoPromptPackage:
        """Local demo video prompts generated from the reviewed outline."""
        scene_prompts = []
        for scene in outline.scenes:
            scene_prompts.append(
                ScenePrompt(
                    scene_number=scene.scene_number,
                    prompt_en=(
                        f"[Scene {scene.scene_number}] smooth handheld push-in, a modern commercial shot "
                        f"inspired by the scene '{scene.title}', clean subject composition, energetic TikTok "
                        f"atmosphere, soft natural lighting, {scene.duration_seconds} seconds, cinematic, "
                        f"vertical 9:16, no readable text, no distorted hands, no extra limbs"
                    ),
                    duration_seconds=scene.duration_seconds,
                )
            )

        if language == "en":
            editing_notes = "This is a Mock prompt package. For final videos, add captions, pricing, and CTA text during editing instead of asking the video model to generate readable text."
        elif language == "bilingual":
            editing_notes = (
                "这是 Mock Prompt。正式使用时建议把字幕、价格、CTA 文案放到剪辑阶段添加，而不是直接要求视频模型生成可读文字。\n"
                "This is a Mock prompt package. For final videos, add captions, pricing, and CTA text during editing instead of asking the video model to generate readable text."
            )
        else:
            editing_notes = "这是 Mock Prompt。正式使用时建议把字幕、价格、CTA 文案放到剪辑阶段添加，而不是直接要求视频模型生成可读文字。"

        return VideoPromptPackage(
            platform=target_tool,  # type: ignore[arg-type]
            aspect_ratio="vertical 9:16",
            global_style_prompt_en="Modern TikTok brand commercial, clean composition, energetic pacing, polished but natural, mobile-first vertical video.",
            scene_prompts=scene_prompts,
            editing_notes_zh=editing_notes,
        )
