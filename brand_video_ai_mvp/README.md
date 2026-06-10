# Brand Video AI MVP

一个 AI 驱动的品牌 TikTok 短视频内容生成工具。商家填写品牌问卷后，系统自动生成短视频大纲；用户可以人工审查和修改大纲；通过后系统再生成适配 Runway Gen-3 / Kling / Pika 的英文视频生成 Prompt。

> MVP 当前重点跑通 Step 1-3：问卷输入 → AI 视频大纲 → 人工审查 → 英文视频 Prompt。Step 4 自动生成视频片段暂未接入，后续可扩展 Kling / Runway API。

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

### 暂未完成 / 后续扩展

- 自动调用 Kling API / Runway API 生成视频
- 视频片段自动拼接
- 用户登录与项目保存
- 品牌素材上传，如 Logo、产品图、品牌色
- Prompt 版本管理

---

## 2. 技术栈

为了保证 2-3 天内快速完成 MVP，本项目使用轻量全栈方案：

- Backend: Python + FastAPI
- AI Provider: OpenAI API
- Frontend: 原生 HTML / CSS / JavaScript
- Data Model: Pydantic
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
│   ├── models.py                  # 请求/响应数据模型
│   ├── prompts.py                 # 核心 System Prompt
│   └── services/
│       └── openai_service.py      # OpenAI 调用逻辑 + Mock fallback
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
OPENAI_API_KEY=sk-your-openai-api-key-here
OPENAI_MODEL=gpt-4o-mini
ALLOW_MOCK_AI=true
```

说明：

- `OPENAI_API_KEY`：你的 OpenAI API Key。
- `OPENAI_MODEL`：默认使用 `gpt-4o-mini`，你可以改成其他支持文本生成的模型。
- `ALLOW_MOCK_AI=true`：如果没有 API Key，系统会返回 Mock 数据，方便本地测试 UI 流程。

### Step 5：启动项目

```bash
uvicorn app.main:app --reload --port 8000
```

打开浏览器访问：

```text
http://localhost:8000
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
