# Brand Video AI MVP

AI brand short-video generation SaaS MVP. Users register, verify email, save a Brand Profile / Company Profile, generate an AI video outline, review it, create Sora-ready scene prompts, queue async video generation jobs, and publish finished assets to YouTube Shorts.

The current stack is:

- FastAPI backend
- Static Tailwind frontend in `static/index.html` with modular scripts under `static/js/`
- JWT auth
- Email verification and password reset
- Profile and account settings
- Brand Profile / Company Profile with logo upload
- Admin dashboard
- Async video generation jobs
- YouTube OAuth connection and Shorts publishing through YouTube Data API v3
- SQLAlchemy ORM models with Pydantic API schemas
- Alembic migrations with SQLite locally and Neon PostgreSQL on Render

## Current Architecture

- Local development uses SQLite, defaulting to `sqlite:///./test.db`.
- Deployment uses a Render Web Service plus Neon PostgreSQL.
- DBeaver can inspect the Neon database with the same connection details used by Render.
- FastAPI route modules live under `app/routers/`.
- Shared runtime helpers live in `app/core.py`.
- Database tables are defined in `app/models.py`.
- API request/response schemas are defined in `app/schemas.py`.
- Video storage is local MVP storage through `app/services/storage_service.py`.
- Local video storage is fine for local development and demos, but Render local filesystem storage is not durable. Production video files should move to S3, Cloudflare R2, Supabase Storage, or another persistent object store.
- Alembic tracks database schema changes. The app still calls `init_db()` on startup for local MVP convenience, but deployed databases should be upgraded with `alembic upgrade head`.

## Environment Variables

Copy `.env.example` to `.env` for local development:

```bash
cp .env.example .env
```

Important variables:

```env
APP_ENV=development
DATABASE_URL=sqlite:///./test.db
JWT_SECRET_KEY=change-me
CORS_ALLOWED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000
ADMIN_EMAILS=admin@example.com
OPENAI_API_KEY=
OPENAI_MODEL=gpt-5.4-mini
ALLOW_MOCK_AI=true
SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=
APP_BASE_URL=http://localhost:8000
STORAGE_BACKEND=local
LOCAL_VIDEO_STORAGE_DIR=static/generated_videos
```

Notes:

- `APP_ENV=production` requires a strong `JWT_SECRET_KEY`, explicit `CORS_ALLOWED_ORIGINS`, and SMTP configuration.
- Development does not require SMTP. If SMTP is empty in development, verification and password reset links are printed to logs.
- Production requires SMTP or a transactional email provider for email verification.
- `ALLOW_MOCK_AI=true` lets the app run without a real OpenAI API key.
- `STORAGE_BACKEND=local` is the only implemented storage backend in this MVP pass.
- `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` come from a Google Cloud OAuth Web Client.
- `GOOGLE_OAUTH_REDIRECT_URI` must exactly match the redirect URI configured in Google Cloud Console.
- `TOKEN_ENCRYPTION_KEY` is required before saving OAuth access and refresh tokens.
- `YOUTUBE_UPLOAD_ALLOW_PUBLIC=false` blocks public uploads during development, even if the frontend sends `public`.

YouTube variables:

```env
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8000/api/oauth/youtube/callback
GOOGLE_OAUTH_SCOPES=https://www.googleapis.com/auth/youtube.upload
TOKEN_ENCRYPTION_KEY=
YOUTUBE_UPLOAD_DEFAULT_PRIVACY_STATUS=private
YOUTUBE_UPLOAD_ALLOW_PUBLIC=false
```

## Local Setup

```bash
cd brand_video_ai_mvp
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

Initialize or upgrade the local database schema:

```bash
alembic upgrade head
```

Open:

```text
http://localhost:8000
```

To test YouTube locally:

1. Register or log in.
2. Complete the brand questionnaire.
3. Open Social Accounts and click Connect YouTube.
4. Generate or prepare a `VideoAsset` with a local video file.
5. Open Studio and use Publish to YouTube Shorts.

Run tests:

```bash
pytest -q
```

Tests are split by feature area:

- `tests/test_auth.py`
- `tests/test_profile.py`
- `tests/test_brand_profile.py`
- `tests/test_generation.py`
- `tests/test_youtube.py`
- `tests/test_admin.py`

## Render + Neon Setup

1. Create a Neon PostgreSQL database.
2. Copy the Neon connection string, including `sslmode=require`.
3. Create a Render Web Service connected to this repository.
4. Set Render Root Directory to:

```text
brand_video_ai_mvp
```

5. Set Build Command:

```bash
pip install -r requirements.txt && alembic upgrade head
```

6. Set Start Command:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

7. Configure Render environment variables:

```env
APP_ENV=production
DATABASE_URL=postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require
JWT_SECRET_KEY=use-a-long-random-secret
CORS_ALLOWED_ORIGINS=https://your-render-service.onrender.com
ADMIN_EMAILS=founder@example.com
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-5.4-mini
ALLOW_MOCK_AI=false
APP_BASE_URL=https://your-render-service.onrender.com
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=smtp-user
SMTP_PASSWORD=smtp-password
SMTP_FROM_EMAIL=no-reply@example.com
STORAGE_BACKEND=local
LOCAL_VIDEO_STORAGE_DIR=static/generated_videos
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_OAUTH_REDIRECT_URI=https://your-render-service.onrender.com/api/oauth/youtube/callback
GOOGLE_OAUTH_SCOPES=https://www.googleapis.com/auth/youtube.upload
TOKEN_ENCRYPTION_KEY=use-a-long-random-secret
YOUTUBE_UPLOAD_DEFAULT_PRIVACY_STATUS=private
YOUTUBE_UPLOAD_ALLOW_PUBLIC=false
```

Production startup will fail with a clear error if SMTP is missing:

```text
SMTP is required in production for email verification.
```

## DBeaver + Neon

In DBeaver, create a PostgreSQL connection:

- Host: Neon host from the connection string
- Port: `5432`
- Database: database name from the connection string
- Username: Neon username
- Password: Neon password
- SSL: require, or set driver property `sslmode=require`

Use this connection to inspect users, questionnaires, generation jobs, generated outlines, prompt packages, video assets, API usage logs, and admin action logs.

## YouTube Cloud Setup

1. Create a Google Cloud Project.
2. Enable YouTube Data API v3.
3. Create an OAuth Client ID.
4. Set Application type to Web application.
5. Add this local Authorized redirect URI:

```text
http://localhost:8000/api/oauth/youtube/callback
```

6. For Render, add the deployed redirect URI:

```text
https://your-render-domain.com/api/oauth/youtube/callback
```

The app uses the server-side OAuth web flow. The frontend receives only an authorization URL; Google tokens are exchanged and encrypted by the FastAPI backend. YouTube Shorts does not have a separate upload API. This app uploads videos with `videos.insert`; YouTube classifies eligible vertical short videos as Shorts.

## Main API Flow

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/profile`
- `PUT /api/profile`
- `POST /api/profile/avatar`
- `GET /api/brand-profile`
- `POST /api/brand-profile`
- `PUT /api/brand-profile`
- `POST /api/brand-profile/logo`
- `POST /api/generate-outline`
- `POST /api/generate-prompts`
- `POST /api/video-jobs`
- `GET /api/video-jobs/{job_id}`
- `GET /api/oauth/youtube/connect`
- `GET /api/oauth/youtube/callback`
- `POST /api/youtube/shorts/upload`
- `GET /api/publishing-jobs`
- `GET /api/admin/api-usage`
- `PATCH /api/admin/users/{user_id}`

Generation creates traceable records:

- `GenerationJob`
- `GeneratedOutline`
- `GeneratedPromptPackage`
- `VideoAsset`
- `PublishingJob`
- `ApiUsageLog`
- `AdminActionLog` for admin user changes

## Local Database Notes

Alembic is the source of truth for database schema changes:

```bash
alembic upgrade head
```

The first migration creates the current MVP schema for empty databases. If a database already has the `users` table, the initial migration treats it as an existing baseline and records the Alembic version without trying to recreate tables. Future field/table changes should be added as new Alembic revisions instead of relying on deleting `test.db`. The app still calls `Base.metadata.create_all(bind=engine)` on startup for local MVP convenience and keeps a small SQLite compatibility helper for older local databases. Do not delete production data.

To create a future migration after changing SQLAlchemy models:

```bash
alembic revision --autogenerate -m "describe schema change"
alembic upgrade head
```

## Testing

```bash
pytest -q
```

Tests use isolated temporary SQLite databases and mock AI behavior. They do not send real SMTP, call Render/Neon, or make paid OpenAI video requests.

## Security Notes

- Store secrets only in environment variables.
- Do not commit `.env`, `test.db`, `.venv`, `youtubeAPI.json`, generated videos, API keys, or credentials.
- Do not use `youtubeAPI.json` as the production OAuth solution.
- OAuth access tokens and refresh tokens are encrypted before database storage.
- Keep development uploads private unless you deliberately enable public uploads with `YOUTUBE_UPLOAD_ALLOW_PUBLIC=true`.
- Use a strong unique `JWT_SECRET_KEY` in production.
- Keep `CORS_ALLOWED_ORIGINS` explicit in production.
- Development logs may contain verification and password reset links when SMTP is not configured.
- Local generated video storage is not production-durable, especially on Render. Move videos to S3, Cloudflare R2, Supabase Storage, or equivalent object storage before relying on generated MP4 persistence.

## Current Limitations

- This release only integrates YouTube. Instagram, TikTok, and Xiaohongshu can be added later.
- Production YouTube usage may require Google OAuth verification and YouTube API quota review.
- Render local filesystem storage is not durable, so production publishing should use persistent object storage for generated videos.
