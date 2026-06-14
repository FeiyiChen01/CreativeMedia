"""FastAPI entry point for the Brand Video AI MVP.

Run locally with:
    uvicorn app.main:app --reload --port 8000
"""

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core import STATIC_DIR, get_cors_allowed_origins, json_safe
from app.database import init_db
from app.routers import admin, auth, brand_profile, generation, social_youtube
from app.routers.generation import run_video_generation_job
from app.services.email_service import EmailService

app = FastAPI(
    title="Brand Video AI MVP",
    description="AI-powered TikTok outline and video prompt generator for brands.",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    """Return API errors in a consistent top-level JSON format."""

    if isinstance(exc.detail, dict) and "detail" in exc.detail:
        content = exc.detail
    elif exc.status_code == status.HTTP_401_UNAUTHORIZED:
        content = {
            "detail": str(exc.detail),
            "error_code": "INVALID_TOKEN",
        }
    else:
        content = {
            "detail": str(exc.detail),
            "error_code": "HTTP_ERROR",
        }
    return JSONResponse(status_code=exc.status_code, content=content, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    """Return request validation errors with a stable error_code."""

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Invalid request body.",
            "error_code": "VALIDATION_ERROR",
            "errors": json_safe(exc.errors()),
        },
    )


@app.on_event("startup")
def on_startup() -> None:
    """Initialize tables and validate production email configuration."""

    EmailService().require_production_config()
    init_db()


@app.get("/")
def serve_index() -> FileResponse:
    """Serve the MVP web UI."""

    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health_check() -> dict[str, str]:
    """Simple health check endpoint for local testing."""

    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(brand_profile.router)
app.include_router(social_youtube.router)
app.include_router(generation.router)
app.include_router(admin.router)
