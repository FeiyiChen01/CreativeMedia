"""FastAPI entry point for the Brand Video AI MVP.

Run locally with:
    uvicorn app.main:app --reload --port 8000
"""

from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.models import (
    GenerateOutlineRequest,
    GenerateOutlineResponse,
    GeneratePromptsResponse,
    GenerateSceneVideoRequest,
    GenerateSceneVideoResponse,
    ReviewOutlineRequest,
)
from app.prompts import OUTLINE_SYSTEM_PROMPT, VIDEO_PROMPT_SYSTEM_PROMPT
from app.services.openai_service import AIServiceError, BrandVideoAIService
from app.services.openai_video_service import OpenAIVideoService, VideoGenerationError

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(
    title="Brand Video AI MVP",
    description="AI-powered TikTok outline and video prompt generator for brands.",
    version="0.1.0",
)

# CORS is useful if you later replace static HTML with a React/Vite frontend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def serve_index() -> FileResponse:
    """Serve the MVP web UI."""
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health_check() -> dict[str, str]:
    """Simple health check endpoint for local testing."""
    return {"status": "ok"}


@app.post("/api/generate-outline", response_model=GenerateOutlineResponse)
def generate_outline(payload: GenerateOutlineRequest) -> GenerateOutlineResponse:
    """Step 1: Generate a video outline from questionnaire input."""
    service = BrandVideoAIService()
    try:
        outline, source = service.generate_outline(payload.questionnaire)
        return GenerateOutlineResponse(outline=outline, source=source)
    except AIServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/generate-prompts", response_model=GeneratePromptsResponse)
def generate_prompts(payload: ReviewOutlineRequest) -> GeneratePromptsResponse:
    """Step 3: Convert reviewed outline into English video-generation prompts."""
    service = BrandVideoAIService()
    try:
        prompt_package, source = service.generate_video_prompts(
            questionnaire=payload.questionnaire,
            outline=payload.outline,
            target_tool=payload.target_tool,
        )
        return GeneratePromptsResponse(prompt_package=prompt_package, source=source)
    except AIServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

@app.post("/api/generate-scene-video", response_model=GenerateSceneVideoResponse)
def generate_scene_video(payload: GenerateSceneVideoRequest) -> GenerateSceneVideoResponse:
    """Step 4: Generate one MP4 video clip from one approved scene prompt."""
    service = OpenAIVideoService(output_dir=STATIC_DIR / "generated_videos")
    try:
        result = service.generate_scene_video(
            prompt=payload.prompt_en,
            duration_seconds=payload.duration_seconds,
        )
        return GenerateSceneVideoResponse(**result)
    except VideoGenerationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

@app.get("/api/system-prompts")
def get_system_prompts() -> dict[str, str]:
    """Expose core prompts for review during MVP development."""
    return {
        "outline_system_prompt": OUTLINE_SYSTEM_PROMPT,
        "video_prompt_system_prompt": VIDEO_PROMPT_SYSTEM_PROMPT,
    }
