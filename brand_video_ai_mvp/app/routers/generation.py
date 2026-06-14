"""AI outline, prompt, video job, and asset routes."""

import json
import os
import time

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_admin_user, get_current_user
from app.core import create_api_usage_log, get_local_video_storage_dir, model_to_json, resolve_questionnaire_id, source_provider, utc_now
from app.database import get_db
from app.models import GeneratedOutline, GeneratedPromptPackage, GenerationJob, User, VideoAsset
from app.prompts import OUTLINE_SYSTEM_PROMPT, VIDEO_PROMPT_SYSTEM_PROMPT
from app.schemas import GenerateOutlineRequest, GenerateOutlineResponse, GeneratePromptsResponse, GenerateSceneVideoRequest, GeneratedOutlineResponse, GeneratedPromptPackageResponse, GenerationJobResponse, ReviewOutlineRequest, VideoAssetResponse, VideoJobCreateRequest, VideoJobCreateResponse, VideoJobStatusResponse
from app.services.openai_service import AIServiceError, BrandVideoAIService
from app.services.openai_video_service import OpenAIVideoService
from app.services.storage_service import VideoStorageService

router = APIRouter()

@router.post("/api/generate-outline", response_model=GenerateOutlineResponse)
def generate_outline(
    payload: GenerateOutlineRequest,
    current_user: User = Depends(get_current_user),  # AUTH ADDITION: protect this API
    db: Session = Depends(get_db),
) -> GenerateOutlineResponse:
    """Step 1: Generate a video outline from questionnaire input."""
    questionnaire_id = resolve_questionnaire_id(db, current_user.id, payload.questionnaire_id)
    job = GenerationJob(
        user_id=current_user.id,
        job_type="outline",
        status="running",
        provider="mock",
        input_json=model_to_json({**payload.model_dump(), "questionnaire_id": questionnaire_id}),
        started_at=utc_now(),
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    started = time.monotonic()
    service = BrandVideoAIService()
    try:
        outline, source = service.generate_outline(payload.questionnaire)
        outline_record = GeneratedOutline(
            user_id=current_user.id,
            questionnaire_id=questionnaire_id,
            source=source_provider(source),
            outline_json=model_to_json(outline),
        )
        db.add(outline_record)
        db.flush()
        job.status = "success"
        job.provider = source_provider(source)
        job.model = service.model
        job.latency_ms = int((time.monotonic() - started) * 1000)
        job.output_json = model_to_json({
            "outline": outline.model_dump(),
            "source": source,
            "generated_outline_id": outline_record.id,
            "questionnaire_id": questionnaire_id,
        })
        job.completed_at = utc_now()
        create_api_usage_log(
            db,
            operation="generate_outline",
            provider=job.provider,
            model=job.model,
            generation_job_id=job.id,
            user_id=current_user.id,
            latency_ms=job.latency_ms,
        )
        db.commit()
        db.refresh(outline_record)
        db.refresh(job)
        return GenerateOutlineResponse(
            outline=outline,
            source=source,
            generated_outline_id=outline_record.id,
            generation_job_id=job.id,
        )
    except AIServiceError as exc:
        job.status = "failed"
        job.error_message = str(exc)
        job.latency_ms = int((time.monotonic() - started) * 1000)
        job.completed_at = utc_now()
        create_api_usage_log(
            db,
            operation="generate_outline",
            provider=job.provider,
            model=job.model,
            generation_job_id=job.id,
            user_id=current_user.id,
            latency_ms=job.latency_ms,
        )
        db.commit()
        raise HTTPException(
            status_code=502,
            detail={"detail": str(exc), "error_code": "AI_GENERATION_FAILED"},
        ) from exc


@router.post("/api/generate-prompts", response_model=GeneratePromptsResponse)
def generate_prompts(
    payload: ReviewOutlineRequest,
    current_user: User = Depends(get_current_user),  # AUTH ADDITION: protect this API
    db: Session = Depends(get_db),
) -> GeneratePromptsResponse:
    """Step 3: Convert reviewed outline into English video-generation prompts."""
    questionnaire_id = resolve_questionnaire_id(db, current_user.id, payload.questionnaire_id)
    outline_id = payload.generated_outline_id or payload.outline_id
    if outline_id:
        outline_record = db.get(GeneratedOutline, outline_id)
        if outline_record is None or outline_record.user_id != current_user.id:
            outline_id = None
        elif questionnaire_id is None:
            questionnaire_id = outline_record.questionnaire_id

    job = GenerationJob(
        user_id=current_user.id,
        job_type="prompt",
        status="running",
        provider="mock",
        input_json=model_to_json({**payload.model_dump(), "questionnaire_id": questionnaire_id, "outline_id": outline_id}),
        started_at=utc_now(),
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    started = time.monotonic()
    service = BrandVideoAIService()
    try:
        prompt_package, source = service.generate_video_prompts(
            questionnaire=payload.questionnaire,
            outline=payload.outline,
            target_tool=payload.target_tool,
        )
        package_record = GeneratedPromptPackage(
            user_id=current_user.id,
            questionnaire_id=questionnaire_id,
            outline_id=outline_id,
            source=source_provider(source),
            prompt_package_json=model_to_json(prompt_package),
        )
        db.add(package_record)
        db.flush()
        job.status = "success"
        job.provider = source_provider(source)
        job.model = service.model
        job.latency_ms = int((time.monotonic() - started) * 1000)
        job.output_json = model_to_json({
            "prompt_package": prompt_package.model_dump(),
            "source": source,
            "generated_prompt_package_id": package_record.id,
            "generated_outline_id": outline_id,
            "questionnaire_id": questionnaire_id,
        })
        job.completed_at = utc_now()
        create_api_usage_log(
            db,
            operation="generate_prompts",
            provider=job.provider,
            model=job.model,
            generation_job_id=job.id,
            user_id=current_user.id,
            latency_ms=job.latency_ms,
        )
        db.commit()
        db.refresh(package_record)
        db.refresh(job)
        return GeneratePromptsResponse(
            prompt_package=prompt_package,
            source=source,
            generated_prompt_package_id=package_record.id,
            generation_job_id=job.id,
        )
    except AIServiceError as exc:
        job.status = "failed"
        job.error_message = str(exc)
        job.latency_ms = int((time.monotonic() - started) * 1000)
        job.completed_at = utc_now()
        create_api_usage_log(
            db,
            operation="generate_prompts",
            provider=job.provider,
            model=job.model,
            generation_job_id=job.id,
            user_id=current_user.id,
            latency_ms=job.latency_ms,
        )
        db.commit()
        raise HTTPException(
            status_code=502,
            detail={"detail": str(exc), "error_code": "AI_GENERATION_FAILED"},
        ) from exc


def run_video_generation_job(job_id: int) -> None:
    """Run one video job in the background.

    FastAPI BackgroundTasks is fine for the MVP. Celery or RQ should replace it
    for production-scale workloads so jobs survive process restarts.
    """

    from app.database import SessionLocal

    db = SessionLocal()
    started = time.monotonic()
    try:
        job = db.get(GenerationJob, job_id)
        if job is None:
            return
        if job.status == "success":
            return
        job.status = "running"
        job.started_at = utc_now()
        db.commit()

        input_payload = json.loads(job.input_json or "{}")
        allow_mock = os.getenv("ALLOW_MOCK_AI", "true").lower() == "true"
        openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
        is_placeholder_key = not openai_api_key or openai_api_key.startswith("sk-your")
        if allow_mock and is_placeholder_key:
            storage = VideoStorageService(base_dir=get_local_video_storage_dir())
            result = {
                "video_id": f"mock-video-{job.id}",
                "status": "completed",
                "video_url": "",
                "file_path": "",
                "storage_backend": storage.get_storage_backend(),
                "file_size": None,
                "model": "mock-sora-2",
                "size": os.getenv("OPENAI_VIDEO_SIZE", "720x1280"),
                "seconds": str(input_payload.get("duration_seconds", 4)),
            }
        else:
            service = OpenAIVideoService(output_dir=get_local_video_storage_dir())
            result = service.generate_scene_video(
                prompt=input_payload["prompt_en"],
                duration_seconds=float(input_payload.get("duration_seconds", 4)),
            )

        asset = VideoAsset(
            user_id=job.user_id,
            generation_job_id=job.id,
            prompt_package_id=input_payload.get("prompt_package_id"),
            scene_number=input_payload.get("scene_number"),
            provider_video_id=result.get("video_id"),
            storage_backend=result.get("storage_backend"),
            video_url=result.get("video_url"),
            file_path=result.get("file_path"),
            file_size=int(result["file_size"]) if result.get("file_size") else None,
            model=result.get("model"),
            size=result.get("size"),
            seconds=float(result.get("seconds") or input_payload.get("duration_seconds", 4)),
            status=result.get("status", "completed"),
        )
        db.add(asset)
        db.flush()
        job.status = "success"
        job.provider = "mock" if result.get("model") == "mock-sora-2" else "openai"
        job.model = result.get("model")
        job.latency_ms = int((time.monotonic() - started) * 1000)
        job.output_json = model_to_json({**result, "video_asset_id": asset.id})
        job.completed_at = utc_now()
        create_api_usage_log(
            db,
            operation="generate_video",
            provider=job.provider,
            model=job.model,
            generation_job_id=job.id,
            user_id=job.user_id,
            latency_ms=job.latency_ms,
        )
        db.commit()
    except Exception as exc:  # noqa: BLE001 - background errors must be captured in the job row.
        job = db.get(GenerationJob, job_id)
        if job:
            job.status = "failed"
            job.error_message = str(exc)
            job.latency_ms = int((time.monotonic() - started) * 1000)
            job.completed_at = utc_now()
            create_api_usage_log(
                db,
                operation="generate_video",
                provider=job.provider,
                model=job.model,
                generation_job_id=job.id,
                user_id=job.user_id,
                latency_ms=job.latency_ms,
            )
            db.commit()
    finally:
        db.close()


@router.post("/api/video-jobs", response_model=VideoJobCreateResponse, status_code=status.HTTP_201_CREATED)
def create_video_job(
    payload: VideoJobCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VideoJobCreateResponse:
    """Create an asynchronous scene video generation job."""

    payload_data = payload.model_dump()
    if payload.prompt_package_id:
        package = db.get(GeneratedPromptPackage, payload.prompt_package_id)
        if package is None or package.user_id != current_user.id:
            payload_data["prompt_package_id"] = None

    job = GenerationJob(
        user_id=current_user.id,
        job_type="video",
        status="pending",
        provider="mock",
        input_json=model_to_json(payload_data),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    background_tasks.add_task(run_video_generation_job, job.id)
    return VideoJobCreateResponse(job_id=job.id, status=job.status)


@router.get("/api/video-jobs/{job_id}", response_model=VideoJobStatusResponse)
def get_video_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VideoJobStatusResponse:
    """Return one video job if owned by the current user or requested by an admin."""

    job = db.get(GenerationJob, job_id)
    if job is None or job.job_type != "video":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Video job not found.", "error_code": "VIDEO_JOB_NOT_FOUND"},
        )
    if job.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"detail": "You cannot access this video job.", "error_code": "VIDEO_JOB_FORBIDDEN"},
        )

    asset = db.scalar(select(VideoAsset).where(VideoAsset.generation_job_id == job.id).order_by(VideoAsset.id.desc()))
    response = VideoJobStatusResponse.model_validate(job)
    response.video_asset = VideoAssetResponse.model_validate(asset) if asset else None
    return response


@router.post("/api/generate-scene-video", response_model=VideoJobCreateResponse)
def generate_scene_video(
    payload: GenerateSceneVideoRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),  # AUTH ADDITION: protect this API
    db: Session = Depends(get_db),
) -> VideoJobCreateResponse:
    """Backward-compatible wrapper that creates an async video job."""

    return create_video_job(
        VideoJobCreateRequest(
            prompt_en=payload.prompt_en,
            duration_seconds=payload.duration_seconds,
            scene_number=payload.scene_number,
            prompt_package_id=payload.prompt_package_id,
        ),
        background_tasks=background_tasks,
        current_user=current_user,
        db=db,
    )


@router.get("/api/generated/outlines", response_model=list[GeneratedOutlineResponse])
def list_generated_outlines(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[GeneratedOutlineResponse]:
    """List current user's generated outlines."""

    rows = db.scalars(
        select(GeneratedOutline)
        .where(GeneratedOutline.user_id == current_user.id)
        .order_by(GeneratedOutline.created_at.desc(), GeneratedOutline.id.desc())
    ).all()
    return [GeneratedOutlineResponse.model_validate(row) for row in rows]


@router.get("/api/generated/prompts", response_model=list[GeneratedPromptPackageResponse])
def list_generated_prompts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[GeneratedPromptPackageResponse]:
    """List current user's generated prompt packages."""

    rows = db.scalars(
        select(GeneratedPromptPackage)
        .where(GeneratedPromptPackage.user_id == current_user.id)
        .order_by(GeneratedPromptPackage.created_at.desc(), GeneratedPromptPackage.id.desc())
    ).all()
    return [GeneratedPromptPackageResponse.model_validate(row) for row in rows]


@router.get("/api/video-jobs", response_model=list[GenerationJobResponse])
def list_video_jobs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[GenerationJobResponse]:
    """List current user's video jobs."""

    rows = db.scalars(
        select(GenerationJob)
        .where(GenerationJob.user_id == current_user.id, GenerationJob.job_type == "video")
        .order_by(GenerationJob.created_at.desc(), GenerationJob.id.desc())
    ).all()
    return [GenerationJobResponse.model_validate(row) for row in rows]


@router.get("/api/video-assets", response_model=list[VideoAssetResponse])
def list_video_assets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[VideoAssetResponse]:
    """List current user's generated video assets."""

    rows = db.scalars(
        select(VideoAsset)
        .where(VideoAsset.user_id == current_user.id)
        .order_by(VideoAsset.created_at.desc(), VideoAsset.id.desc())
    ).all()
    return [VideoAssetResponse.model_validate(row) for row in rows]


@router.get("/api/system-prompts")
def get_system_prompts(_admin_user: User = Depends(get_current_admin_user)) -> dict[str, str]:
    """Expose core prompts for review during MVP development."""
    return {
        "outline_system_prompt": OUTLINE_SYSTEM_PROMPT,
        "video_prompt_system_prompt": VIDEO_PROMPT_SYSTEM_PROMPT,
    }
