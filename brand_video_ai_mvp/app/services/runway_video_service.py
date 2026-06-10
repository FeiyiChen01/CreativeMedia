"""Runway video generation service.

This service converts approved scene-level prompts into generated video clips.
For the MVP, it returns video URLs for each scene instead of editing them into
one final video.
"""

import os
from typing import Any

try:
    from runwayml import RunwayML, TaskFailedError
except ImportError:
    RunwayML = None  # type: ignore[assignment]
    TaskFailedError = Exception  # type: ignore[assignment]


class VideoGenerationError(RuntimeError):
    """Raised when video generation fails."""


class RunwayVideoService:
    """Service for generating videos from scene prompts using Runway."""

    def __init__(self) -> None:
        self.api_key = os.getenv("RUNWAYML_API_SECRET", "").strip()
        self.model = os.getenv("RUNWAY_MODEL", "gen4.5").strip()
        self.ratio = os.getenv("RUNWAY_RATIO", "720:1280").strip()

        if not self.api_key:
            raise VideoGenerationError(
                "RUNWAYML_API_SECRET is missing. Add it to .env before generating videos."
            )

        if RunwayML is None:
            raise VideoGenerationError(
                "The runwayml package is not installed. Run: pip install runwayml"
            )

        self.client = RunwayML(api_key=self.api_key)

    def generate_scene_video(
        self,
        prompt: str,
        duration_seconds: int,
    ) -> dict[str, Any]:
        """Generate one video clip from one scene prompt."""
        try:
            # Keep MVP durations short to reduce cost and waiting time.
            duration = max(5, min(duration_seconds, 10))

            task = self.client.image_to_video.create(
                model=self.model,
                prompt_text=prompt,
                ratio=self.ratio,
                duration=duration,
            ).wait_for_task_output()

            video_url = task.output[0] if task.output else None

            if not video_url:
                raise VideoGenerationError("Runway completed the task but returned no video URL.")

            return {
                "video_url": video_url,
                "duration_seconds": duration,
                "provider": "runway",
                "model": self.model,
            }

        except TaskFailedError as exc:
            raise VideoGenerationError(f"Runway task failed: {exc}") from exc
        except Exception as exc:
            raise VideoGenerationError(f"Runway video generation failed: {exc}") from exc