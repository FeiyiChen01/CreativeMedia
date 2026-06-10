"""OpenAI Sora video generation service."""

import os
import time
import uuid
from pathlib import Path
from typing import Literal

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None  # type: ignore[assignment]


AllowedVideoModel = Literal["sora-2", "sora-2-pro"]
AllowedVideoSize = Literal["720x1280", "1280x720", "1024x1792", "1792x1024"]


class VideoGenerationError(RuntimeError):
    """Raised when OpenAI video generation fails."""


class OpenAIVideoService:
    """Generate short video clips from scene-level prompts using OpenAI Videos API."""

    def __init__(self, output_dir: Path) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.model = os.getenv("OPENAI_VIDEO_MODEL", "sora-2").strip()
        self.size = os.getenv("OPENAI_VIDEO_SIZE", "720x1280").strip()
        self.poll_interval_seconds = float(os.getenv("VIDEO_POLL_INTERVAL_SECONDS", "5"))
        self.timeout_seconds = int(os.getenv("VIDEO_TIMEOUT_SECONDS", "600"))
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        if not self.api_key or self.api_key.startswith("sk-your"):
            raise VideoGenerationError("OPENAI_API_KEY is missing. Add it to .env before generating videos.")
        if OpenAI is None:
            raise VideoGenerationError("The openai package is not installed. Run: pip install -r requirements.txt")

        self.client = OpenAI(api_key=self.api_key)

        if not hasattr(self.client, "videos"):
            raise VideoGenerationError("Your openai package is too old. Run: pip install --upgrade openai")

    def generate_scene_video(self, prompt: str, duration_seconds: float) -> dict[str, str]:
        """Create, poll, download, and return metadata for one generated scene video."""
        seconds = self._normalize_seconds(duration_seconds)
        size = self._normalize_size(self.size)
        model = self._normalize_model(self.model)

        try:
            video = self.client.videos.create(
                model=model,
                prompt=prompt,
                seconds=seconds,
                size=size,
            )

            completed_video = self._wait_until_done(video.id)
            file_name = f"{completed_video.id}_{uuid.uuid4().hex[:8]}.mp4"
            output_path = self.output_dir / file_name

            video_content = self.client.videos.download_content(video_id=completed_video.id)
            output_path.write_bytes(video_content.read())

            return {
                "video_id": completed_video.id,
                "status": completed_video.status,
                "video_url": f"/static/generated_videos/{file_name}",
                "model": model,
                "size": size,
                "seconds": seconds,
            }
        except VideoGenerationError:
            raise
        except Exception as exc:
            raise VideoGenerationError(f"OpenAI video generation failed: {exc}") from exc

    def _wait_until_done(self, video_id: str):
        """Poll the OpenAI video job until it finishes, fails, or times out."""
        deadline = time.monotonic() + self.timeout_seconds

        while time.monotonic() < deadline:
            video = self.client.videos.retrieve(video_id)
            status = getattr(video, "status", "unknown")

            if status == "completed":
                return video
            if status == "failed":
                error = getattr(video, "error", None)
                message = getattr(error, "message", "Unknown video generation error")
                raise VideoGenerationError(f"OpenAI video job failed: {message}")

            time.sleep(self.poll_interval_seconds)

        raise VideoGenerationError(f"Timed out waiting for OpenAI video job {video_id}.")

    @staticmethod
    def _normalize_seconds(duration_seconds: float) -> Literal["4", "8", "12"]:
        if duration_seconds <= 4:
            return "4"
        if duration_seconds <= 8:
            return "8"
        return "12"

    @staticmethod
    def _normalize_size(size: str) -> AllowedVideoSize:
        allowed = {"720x1280", "1280x720", "1024x1792", "1792x1024"}
        if size not in allowed:
            return "720x1280"
        return size  # type: ignore[return-value]

    @staticmethod
    def _normalize_model(model: str) -> AllowedVideoModel:
        if model not in {"sora-2", "sora-2-pro"}:
            return "sora-2"
        return model  # type: ignore[return-value]