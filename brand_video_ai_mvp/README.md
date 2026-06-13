# Brand Video AI MVP

一个 AI 驱动的品牌 TikTok 短视频内容生成工具。商家填写品牌问卷后，系统自动生成短视频大纲；用户可以人工审查和修改大纲；通过后系统再生成适配 Runway Gen-3 / Kling / Pika 的英文视频生成 Prompt。

> MVP 当前跑通：注册/登录 → 邮箱验证 → 问卷 → AI 大纲 → Prompt → 异步视频 job → 轮询结果，并提供 Profile 与 Admin 管理区。

---

## 1. 功能范围

### 已完成

- 品牌问卷输入界面
- AI 生成视频大纲
  - Hook
  - 3-5 个分镜场景
  - 配音 / 字幕文案
  - 背景音乐风格
  - TikTok Hashtags
- 人工审查界面
  - 修改 Hook
  - 修改视频结构
  - 修改每个场景画面描述
  - 修改每个场景字幕 / 配音
  - 一键重新生成
  - 一键通过并生成 Prompt
- 视频 Prompt 生成
  - 每个场景输出一条英文 Prompt
  - 格式适配 AI 视频生成工具
  - 默认竖屏 `vertical 9:16`
- 本地 Mock 模式
  - 没有 API Key 时，也能测试完整流程
- Email verification and password reset
  - SMTP 未配置且 `APP_ENV=development` 时，验证/重置链接会打印到终端日志
- Profile / Account Settings
  - 基础资料、邮箱验证状态、重发验证邮件、修改密码
- Generated history persistence
  - Outline、prompt package、video job、video asset 都会按当前用户保存
- Async video job flow
  - 前端创建 `/api/video-jobs` 后轮询 job 状态；本地 mock 模式不需要真实 OpenAI 视频调用
- Admin dashboard
  - 仅 admin 可见，展示用户、问卷、生成任务、视频资产、API usage、action logs、system prompts

### 暂未完成 / 后续扩展

- 视频片段自动拼接
- 品牌素材上传，如 Logo、产品图、品牌色
- Prompt 版本管理

---

## 2. 技术栈

为了保证 2-3 天内快速完成 MVP，本项目使用轻量全栈方案：

- Backend: Python + FastAPI
- AI Provider: OpenAI API
- Frontend: 原生 HTML / CSS / JavaScript
- Data Model: SQLAlchemy ORM + Pydantic
- Database: SQLite for local development, Neon PostgreSQL for Render deployment
- Local Server: Uvicorn

为什么这样选：

- 启动简单，不需要 React / Vite / Node 环境
- 前后端在同一个 FastAPI 项目内，方便演示和部署
- 后续如果要升级成 React 前端，也可以直接复用现有 API

---

## 3. 项目结构

```text
brand_video_ai_mvp/
├── app/
│   ├── main.py                    # FastAPI 路由入口
│   ├── models.py                  # SQLAlchemy ORM + AI 请求/响应数据模型
│   ├── schemas.py                 # Auth / questionnaire / persistence schemas
│   ├── database.py                # SQLite/PostgreSQL engine and sessions
│   ├── auth.py                    # Password hashing, JWT auth, admin dependency
│   ├── prompts.py                 # 核心 System Prompt
│   └── services/
│       ├── email_service.py       # SMTP delivery + development log fallback
│       ├── openai_service.py      # OpenAI 调用逻辑 + Mock fallback
│       └── openai_video_service.py
├── static/
│   ├── index.html                 # 前端页面
│   ├── style.css                  # 页面样式
│   └── app.js                     # 前端交互逻辑
├── .env.example                   # 环境变量示例
├── requirements.txt               # Python 依赖
└── README.md
```

---

## 4. 本地启动方式

### Step 1：进入项目目录

```bash
cd brand_video_ai_mvp
```

### Step 2：创建虚拟环境

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### Step 3：安装依赖

```bash
pip install -r requirements.txt
```

### Step 4：配置环境变量

复制 `.env.example` 为 `.env`：

```bash
cp .env.example .env
```

然后打开 `.env`，填入：

```env
APP_ENV=development
DATABASE_URL=sqlite:///./test.db
JWT_SECRET_KEY=change-me
CORS_ALLOWED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000
ADMIN_EMAILS=
APP_BASE_URL=http://localhost:8000
SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=no-reply@example.com
OPENAI_API_KEY=sk-your-openai-api-key-here
OPENAI_MODEL=gpt-5.4-mini
ALLOW_MOCK_AI=true
```

说明：

- `APP_ENV=development`：本地开发模式。生产环境必须设置为 `production`。
- `DATABASE_URL=sqlite:///./test.db`：本地默认 SQLite 数据库。如果不设置，应用也会默认使用这个地址。
- `JWT_SECRET_KEY`：本地可以使用示例值，生产环境必须换成强随机字符串，建议至少 32 个字符。
- `CORS_ALLOWED_ORIGINS`：逗号分隔的允许来源。生产环境不要使用 `*`。
- `ADMIN_EMAILS`：逗号分隔的管理员邮箱。用户用这些邮箱注册时会自动获得 `admin` 角色。
- `APP_BASE_URL`：用于生成邮箱验证与密码重置链接。本地默认 `http://localhost:8000`。
- `SMTP_HOST` / `SMTP_PORT` / `SMTP_USERNAME` / `SMTP_PASSWORD` / `SMTP_FROM_EMAIL`：SMTP 邮件配置。本地开发可以留空，系统会把链接打印到终端。
- `OPENAI_API_KEY`：你的 OpenAI API Key。
- `OPENAI_MODEL`：默认使用 `gpt-5.4-mini`，你可以改成其他支持文本生成的模型。
- `ALLOW_MOCK_AI=true`：如果没有 API Key，系统会返回 Mock 数据，方便本地测试 UI 流程。

本地 SQLite 会创建 `test.db`。如果你之前已经运行过旧版本，旧表结构不会被 `create_all` 自动修改；开发时可以停止服务后删除 `test.db`，让应用重新创建最新表结构。

### Step 5：启动项目

```bash
uvicorn app.main:app --reload --port 8000
```

打开浏览器访问：

```text
http://localhost:8000
```

### Step 6：本地 SQLite 验证

```bash
python3 -c "from app.database import init_db; init_db(); print('database ok')"
uvicorn app.main:app --reload --port 8000
```

打开 `http://localhost:8000`，注册、登录、填写 questionnaire，然后进入当前 dashboard/app 流程。

### Step 7：运行测试

```bash
pytest
```

测试使用临时 SQLite 数据库，不会连接 Render/Neon，也不会发真实 SMTP 或真实 OpenAI 请求。

---

## 4.1 Render Web Service + Neon PostgreSQL

### Render Web Service 设置

1. 在 Render 创建新的 Web Service，连接你的 GitHub 仓库。
2. Root Directory 设置为：

```text
brand_video_ai_mvp
```

3. Build Command：

```bash
pip install -r requirements.txt
```

4. Start Command：

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

5. 在 Render 的 Environment 里设置：

```env
APP_ENV=production
DATABASE_URL=你的 Neon PostgreSQL 连接字符串
JWT_SECRET_KEY=至少 32 个字符的强随机密钥
CORS_ALLOWED_ORIGINS=https://你的-render-service.onrender.com
ADMIN_EMAILS=founder@example.com
OPENAI_API_KEY=sk-your-openai-api-key-here
APP_BASE_URL=https://你的-render-service.onrender.com
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=smtp-user
SMTP_PASSWORD=smtp-password
SMTP_FROM_EMAIL=no-reply@example.com
ALLOW_MOCK_AI=false
```

生产环境中，如果 `JWT_SECRET_KEY` 缺失、太短，或仍然是示例值，应用会拒绝启动。

### Neon Free PostgreSQL 设置

1. 在 Neon 创建免费项目。
2. 创建或选择默认 database。
3. 打开 Neon Dashboard 的 Connection Details。
4. 复制 PostgreSQL connection string，通常形如：

```text
postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require
```

5. 粘贴到 Render Web Service 的 `DATABASE_URL` 环境变量。

Render 部署启动后，应用会执行 `Base.metadata.create_all(bind=engine)` 创建当前表。这个 pass 暂时没有引入 Alembic；后续正式迁移再添加。

### DBeaver 连接 Neon PostgreSQL

1. 打开 DBeaver，选择 `New Database Connection`。
2. 选择 PostgreSQL。
3. 从 Neon connection string 中填写：
   - Host：`@` 后、数据库名前的主机名
   - Port：通常是 `5432`
   - Database：连接字符串路径中的数据库名
   - Username：连接字符串中的 USER
   - Password：连接字符串中的 PASSWORD
4. SSL 设置选择 `require`，或在 Driver properties 中设置 `sslmode=require`。
5. 点击 `Test Connection`，成功后保存。

### 不要提交的文件

不要提交 `.env`、`test.db`、`.venv`、`youtubeAPI.json` 或任何 secrets/API keys。当前 `.gitignore` 已覆盖这些本地文件，但提交前仍建议检查：

```bash
git status --short
```

---

## 5. 使用流程

1. 在首页填写品牌问卷。
2. 点击 `生成视频大纲`。
3. 在人工审查区修改 Hook、分镜、字幕、音乐、Hashtags。
4. 选择目标视频工具：`Generic` / `Runway Gen-3` / `Kling` / `Pika`。
5. 点击 `通过并生成视频 Prompt`。
6. 复制每个 Scene Prompt，粘贴到对应视频生成工具中。

---

## 6. API 说明

### Health Check

```http
GET /api/health
```

返回：

```json
{
  "status": "ok"
}
```

### 生成视频大纲

```http
POST /api/generate-outline
```

请求示例：

```json
{
  "questionnaire": {
    "brand_name": "Luna Bloom",
    "industry": "自然灵感首饰品牌",
    "target_audience": "喜欢自然、可持续生活方式的年轻女性消费者",
    "brand_keywords": ["优雅", "自然", "可持续"],
    "promotion_theme": "春季新品上线，首单九折",
    "video_length": "15-30 seconds",
    "language": "zh"
  }
}
```

### 生成视频 Prompt

```http
POST /api/generate-prompts
```

请求内容包括：

- 原始 `questionnaire`
- 人工审查后的 `outline`
- `target_tool`

目标工具可选：

```text
Generic
Runway Gen-3
Kling
Pika
```

---

## 7. 核心 System Prompt

### 7.1 视频大纲生成 Prompt

```text
You are a senior TikTok creative strategist and short-form video scriptwriter.
Your job is to turn a structured merchant brand questionnaire into a practical
15-30 second TikTok video outline.

Rules:
1. Output must be valid JSON only. Do not wrap JSON in Markdown.
2. The outline should be practical for a small business or ecommerce brand.
3. Generate 3 to 5 scenes only.
4. The first 3 seconds must have a strong hook.
5. Make the concept specific to the brand, industry, audience, keywords, and promotion theme.
6. Avoid unsafe, misleading, medical, financial, or exaggerated claims.
7. Hashtags should be realistic TikTok-style hashtags, not random spam.
8. Keep the outline in Chinese unless the user explicitly asks otherwise.

Required JSON shape:
{
  "hook_zh": "string",
  "structure_summary_zh": "string",
  "scenes": [
    {
      "scene_number": 1,
      "title": "string",
      "visual_description_zh": "string",
      "voiceover_or_subtitle_zh": "string",
      "duration_seconds": 3
    }
  ],
  "voiceover_full_zh": "string",
  "music_style_zh": "string",
  "hashtags": ["#tag"],
  "creative_notes_zh": "string"
}
```

### 7.2 视频生成 Prompt 转换 Prompt

```text
You are a professional AI video prompt engineer for Runway Gen-3, Kling, and Pika.
Your job is to convert an approved short-form video outline into English scene prompts.

Rules:
1. Output must be valid JSON only. Do not wrap JSON in Markdown.
2. Every scene must become one independent English video-generation prompt.
3. Keep each scene prompt visually concrete and production-ready.
4. Each scene prompt must follow this structure:
   [Scene X] [camera movement], [subject description], [environment/atmosphere],
   [lighting style], [duration], cinematic, vertical 9:16
5. Do not include Chinese inside prompt_en.
6. Do not ask the video model to render readable text unless essential; text is better added in editing.
7. The output must preserve the same number and order of scenes from the approved outline.
8. Keep the style TikTok-friendly, commercial, clean, modern, and brand-safe.

Required JSON shape:
{
  "platform": "Runway Gen-3" | "Kling" | "Pika" | "Generic",
  "aspect_ratio": "vertical 9:16",
  "global_style_prompt_en": "string",
  "scene_prompts": [
    {
      "scene_number": 1,
      "prompt_en": "[Scene 1] slow push-in, ... cinematic, vertical 9:16",
      "duration_seconds": 3
    }
  ],
  "editing_notes_zh": "string"
}
```

---

## 8. 后续迭代建议

### 优先级 P0

- 保存每次生成结果到数据库
- 支持用户上传品牌 Logo / 产品图
- 每个场景增加 `regenerate scene only` 功能
- 增加 Prompt 复制按钮和 JSON 导出

### 优先级 P1

- 接入视频生成 API
- 自动下载每个视频片段
- 使用 MoviePy / FFmpeg 拼接视频
- 自动生成字幕 SRT

### 优先级 P2

- 多品牌 workspace
- 用户登录
- 项目历史记录
- A/B 测试多个 Hook
- 根据 TikTok 数据反馈优化 Prompt

---

## 9. 注意事项

- 不建议让视频生成模型直接生成大量可读文字，因为 AI 视频模型经常把文字渲染错。字幕、价格、CTA 最好在剪辑阶段添加。
- 本 MVP 不会保存用户数据，刷新页面后内容会丢失。
- `.env` 不要提交到 GitHub；只提交 `.env.example`。
