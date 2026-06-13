"""Storage abstraction for generated video files.

Local storage is acceptable for local development and MVP demos. Render's local
filesystem is not durable, so production should move generated videos to S3,
Cloudflare R2, Supabase Storage, or another persistent object store.
"""

import os
import uuid
from pathlib import Path


class StorageServiceError(RuntimeError):
    """Raised when a storage operation cannot be completed."""


class VideoStorageService:
    """Small storage interface ready for future remote backends."""

    def __init__(self, base_dir: Path | None = None) -> None:
        self.backend = os.getenv("STORAGE_BACKEND", "local").strip().lower() or "local"
        if self.backend != "local":
            raise StorageServiceError(f"Unsupported STORAGE_BACKEND '{self.backend}'. Only 'local' is implemented.")

        configured_dir = os.getenv("LOCAL_VIDEO_STORAGE_DIR", "static/generated_videos").strip()
        self.base_dir = base_dir or Path(configured_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def get_storage_backend(self) -> str:
        """Return the active storage backend name."""

        return self.backend

    def save_video_file(self, content: bytes, file_name: str | None = None) -> dict[str, object]:
        """Persist MP4 bytes and return storage metadata."""

        safe_name = file_name or f"video_{uuid.uuid4().hex}.mp4"
        destination = self.base_dir / safe_name
        destination.write_bytes(content)
        return {
            "storage_backend": self.backend,
            "file_path": str(destination),
            "video_url": self.get_public_url(destination),
            "file_size": destination.stat().st_size,
        }

    def get_public_url(self, file_path: str | Path) -> str:
        """Return the public URL for a locally stored static file."""

        path = Path(file_path)
        parts = path.as_posix().split("/static/", 1)
        if len(parts) == 2:
            return f"/static/{parts[1]}"
        return f"/static/generated_videos/{path.name}"
