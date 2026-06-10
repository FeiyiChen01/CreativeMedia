// Minimal frontend state. This keeps the MVP simple and easy to debug.
let currentQuestionnaire = null;
let currentOutline = null;
let currentOutlineSource = null;
let currentPromptPackage = null;
let currentPromptSource = null;
let currentLanguage = localStorage.getItem("brandVideoAiLanguage") || "zh";

const translations = {
  zh: {
    "app.eyebrow": "AI Brand Video Generator · MVP",
    "app.title": "品牌 TikTok 短视频脚本 & 视频 Prompt 生成器",
    "app.subtitle": "填写品牌问卷后，AI 自动生成视频大纲。人工审查修改后，再生成适配 OpenAI Sora-2 的英文视频生成 Prompt。",
    "language.label": "语言",
    "language.changedNotice": "语言已切换。要让 AI 输出内容也变成当前语言，请重新生成视频大纲。",

    "step.one": "Step 1",
    "step.two": "Step 2",
    "step.three": "Step 3",

    "section.questionnaire": "品牌问卷输入",
    "section.reviewOutline": "人工审查视频大纲",
    "section.promptsAndVideo": "视频生成 Prompt & 视频片段生成",

    "form.brandName": "品牌名称",
    "form.industry": "行业 / 业务类型",
    "form.targetAudience": "目标受众",
    "form.brandKeywords": "品牌关键词（3个形容词，用逗号分隔）",
    "form.promotionTheme": "近期推广主题或活动",
    "form.videoLength": "视频时长",

    "placeholder.brandName": "例如：Luna Bloom",
    "placeholder.industry": "例如：咖啡店 / 珠宝 / 健身房",
    "placeholder.targetAudience": "例如：18-30 岁学生和年轻上班族",
    "placeholder.brandKeywords": "例如：高级,年轻,环保",
    "placeholder.promotionTheme": "例如：新品发布 / 节日折扣 / 开业活动",

    "duration.15": "15 秒",
    "duration.15to30": "15-30 秒",
    "duration.30": "30 秒",

    "button.generateOutline": "生成视频大纲",
    "button.regenerateOutline": "重新生成大纲",
    "button.approveGeneratePrompts": "通过并生成视频 Prompt",
    "button.copyPrompts": "复制全部 Prompt",
    "button.generateSceneVideo": "生成这个 Scene 的视频片段",
    "button.regenerateSceneVideo": "重新生成这个 Scene 的视频片段",

    "loading.generatingOutline": "生成中...",
    "loading.regeneratingOutline": "重新生成中...",
    "loading.generatingPrompts": "生成 Prompt 中...",
    "loading.generatingVideo": "视频生成中...",

    "outline.hook": "Hook（前3秒开场）",
    "outline.summary": "视频结构概述",
    "outline.scenes": "分镜场景",
    "outline.sceneHelp": "可以直接修改每个场景描述和字幕",
    "outline.voiceover": "完整配音 / 字幕文案",
    "outline.music": "推荐背景音乐风格",
    "outline.hashtags": "TikTok Hashtags（用逗号分隔）",
    "outline.notes": "创意备注",
    "outline.targetTool": "目标视频工具",
    "outline.sceneTitle": "场景标题",
    "outline.duration": "秒数",
    "outline.visual": "画面描述",
    "outline.copy": "配音 / 字幕",
    "outline.mockMeta": "当前使用 Mock AI 输出：你还没有配置 OPENAI_API_KEY，但可以先测试完整流程。",
    "outline.openaiMeta": "已使用 OpenAI 生成大纲。你可以直接修改任意内容后再生成视频 Prompt。",

    "prompt.help": "生成 Prompt 后，每个 Scene 下方会出现“生成这个 Scene 的视频片段”按钮。",
    "prompt.platform": "平台",
    "prompt.aspectRatio": "画幅",
    "prompt.source": "来源",
    "prompt.globalStyle": "全局风格",
    "prompt.editingNotes": "剪辑备注",
    "prompt.missingScene": "没有找到这个 Scene 的 Prompt",

    "video.generatingNotice": "OpenAI 正在生成视频片段，这可能需要一段时间。请先只测试一个 Scene。",
    "video.videoId": "Video ID",
    "video.model": "Model",
    "video.size": "Size",
    "video.duration": "Duration",
    "video.download": "下载 MP4",

    "toast.promptsCopied": "已复制全部视频 Prompt",
    "toast.videoGenerated": "Scene {sceneNumber} 视频生成完成",
    "error.requestFailed": "请求失败：{status}",
  },
  en: {
    "app.eyebrow": "AI Brand Video Generator · MVP",
    "app.title": "TikTok Script & Video Prompt Generator for Brands",
    "app.subtitle": "Fill out a brand questionnaire, generate an AI video outline, review the scenes, and create English prompts for OpenAI Sora-2 video generation.",
    "language.label": "Language",
    "language.changedNotice": "Language changed. Regenerate the video outline to make the AI output use the selected language.",

    "step.one": "Step 1",
    "step.two": "Step 2",
    "step.three": "Step 3",

    "section.questionnaire": "Brand Questionnaire",
    "section.reviewOutline": "Review Video Outline",
    "section.promptsAndVideo": "Video Prompts & Clip Generation",

    "form.brandName": "Brand Name",
    "form.industry": "Industry / Business Type",
    "form.targetAudience": "Target Audience",
    "form.brandKeywords": "Brand Keywords (3 adjectives, separated by commas)",
    "form.promotionTheme": "Current Campaign or Promotion",
    "form.videoLength": "Video Length",

    "placeholder.brandName": "Example: Luna Bloom",
    "placeholder.industry": "Example: coffee shop / jewelry / gym",
    "placeholder.targetAudience": "Example: students and young professionals aged 18-30",
    "placeholder.brandKeywords": "Example: premium, youthful, eco-friendly",
    "placeholder.promotionTheme": "Example: product launch / holiday discount / grand opening",

    "duration.15": "15 seconds",
    "duration.15to30": "15-30 seconds",
    "duration.30": "30 seconds",

    "button.generateOutline": "Generate Video Outline",
    "button.regenerateOutline": "Regenerate Outline",
    "button.approveGeneratePrompts": "Approve and Generate Video Prompts",
    "button.copyPrompts": "Copy All Prompts",
    "button.generateSceneVideo": "Generate Video Clip for This Scene",
    "button.regenerateSceneVideo": "Regenerate Video Clip for This Scene",

    "loading.generatingOutline": "Generating...",
    "loading.regeneratingOutline": "Regenerating...",
    "loading.generatingPrompts": "Generating prompts...",
    "loading.generatingVideo": "Generating video...",

    "outline.hook": "Hook (first 3 seconds)",
    "outline.summary": "Video Structure Summary",
    "outline.scenes": "Scene Breakdown",
    "outline.sceneHelp": "You can directly edit each scene description and caption.",
    "outline.voiceover": "Full Voiceover / Caption Script",
    "outline.music": "Recommended Music Style",
    "outline.hashtags": "TikTok Hashtags (separated by commas)",
    "outline.notes": "Creative Notes",
    "outline.targetTool": "Target Video Tool",
    "outline.sceneTitle": "Scene Title",
    "outline.duration": "Duration",
    "outline.visual": "Visual Description",
    "outline.copy": "Voiceover / Caption",
    "outline.mockMeta": "Currently using Mock AI output: OPENAI_API_KEY is not configured yet, but you can test the full workflow.",
    "outline.openaiMeta": "Outline generated with OpenAI. You can edit any field before generating video prompts.",

    "prompt.help": "After generating prompts, each scene will show a “Generate Video Clip for This Scene” button.",
    "prompt.platform": "Platform",
    "prompt.aspectRatio": "Aspect Ratio",
    "prompt.source": "Source",
    "prompt.globalStyle": "Global Style",
    "prompt.editingNotes": "Editing Notes",
    "prompt.missingScene": "Could not find the prompt for this scene.",

    "video.generatingNotice": "OpenAI is generating the video clip. This may take a while. Test only one scene first.",
    "video.videoId": "Video ID",
    "video.model": "Model",
    "video.size": "Size",
    "video.duration": "Duration",
    "video.download": "Download MP4",

    "toast.promptsCopied": "All video prompts copied",
    "toast.videoGenerated": "Scene {sceneNumber} video generated",
    "error.requestFailed": "Request failed: {status}",
  },
};

const form = document.getElementById("questionnaireForm");
const outlineSection = document.getElementById("outlineSection");
const promptSection = document.getElementById("promptSection");
const generateOutlineButton = document.getElementById("generateOutlineButton");
const approveButton = document.getElementById("approveButton");
const regenerateButton = document.getElementById("regenerateButton");
const copyPromptsButton = document.getElementById("copyPromptsButton");
const languageSelect = document.getElementById("languageSelect");

initializeLanguage();

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  currentQuestionnaire = readQuestionnaireFromForm();
  await generateOutline();
});

regenerateButton.addEventListener("click", async () => {
  currentQuestionnaire = readQuestionnaireFromForm();
  await generateOutline();
});

approveButton.addEventListener("click", async () => {
  currentOutline = readOutlineFromReviewForm();
  await generatePrompts();
});

copyPromptsButton.addEventListener("click", async () => {
  if (!currentPromptPackage) {
    return;
  }

  const text = currentPromptPackage.scene_prompts
    .map((scene) => scene.prompt_en)
    .join("\n\n");

  await navigator.clipboard.writeText(text);
  showToast(t("toast.promptsCopied"));
});

if (languageSelect) {
  languageSelect.addEventListener("change", (event) => {
    applyLanguage(event.target.value);

    if (currentOutline) {
      showToast(t("language.changedNotice"));
    }
  });
}

function initializeLanguage() {
  applyLanguage(currentLanguage);
}

function t(key, values = {}) {
  const template = translations[currentLanguage]?.[key] || translations.zh[key] || key;
  return Object.entries(values).reduce(
    (text, [name, value]) => text.replaceAll(`{${name}}`, String(value)),
    template
  );
}

function applyLanguage(language) {
  currentLanguage = translations[language] ? language : "zh";
  localStorage.setItem("brandVideoAiLanguage", currentLanguage);

  document.documentElement.lang = currentLanguage === "zh" ? "zh-CN" : "en";

  if (languageSelect) {
    languageSelect.value = currentLanguage;
  }

  applyStaticTranslations();
  refreshOutlineMeta();
  refreshPromptMeta();
}

function applyStaticTranslations() {
  document.querySelectorAll("[data-i18n]").forEach((element) => {
    element.textContent = t(element.dataset.i18n);
  });

  document.querySelectorAll("[data-i18n-placeholder]").forEach((element) => {
    element.placeholder = t(element.dataset.i18nPlaceholder);
  });
}


function readQuestionnaireFromForm() {
  const keywords = document
    .getElementById("brandKeywords")
    .value.split(/[,，]/)
    .map((item) => item.trim())
    .filter(Boolean);

  return {
    brand_name: document.getElementById("brandName").value.trim(),
    industry: document.getElementById("industry").value.trim(),
    target_audience: document.getElementById("targetAudience").value.trim(),
    brand_keywords: keywords,
    promotion_theme: document.getElementById("promotionTheme").value.trim(),
    video_length: document.getElementById("videoLength").value,
    language: currentLanguage,
  };
}

async function generateOutline() {
  setLoading(generateOutlineButton, true, t("loading.generatingOutline"));
  setLoading(regenerateButton, true, t("loading.regeneratingOutline"));
  promptSection.hidden = true;

  try {
    const result = await postJSON("/api/generate-outline", {
      questionnaire: currentQuestionnaire,
    });

    currentOutline = result.outline;
    currentOutlineSource = result.source;
    renderOutline(currentOutline, currentOutlineSource);
    outlineSection.hidden = false;
    outlineSection.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    showToast(error.message, true);
  } finally {
    setLoading(generateOutlineButton, false, t("button.generateOutline"));
    setLoading(regenerateButton, false, t("button.regenerateOutline"));
  }
}

function renderOutline(outline, source) {
  currentOutlineSource = source;
  refreshOutlineMeta();

  document.getElementById("hookInput").value = outline.hook_zh;
  document.getElementById("summaryInput").value = outline.structure_summary_zh;
  document.getElementById("voiceoverInput").value = outline.voiceover_full_zh;
  document.getElementById("musicInput").value = outline.music_style_zh;
  document.getElementById("hashtagsInput").value = outline.hashtags.join(", ");
  document.getElementById("notesInput").value = outline.creative_notes_zh;

  const scenesContainer = document.getElementById("scenesContainer");
  scenesContainer.innerHTML = "";

  outline.scenes.forEach((scene, index) => {
    const card = document.createElement("div");
    card.className = "scene-card";
    card.dataset.index = index;
    card.innerHTML = `
      <h4>Scene ${scene.scene_number}</h4>
      <div class="scene-grid">
        <label>
          <span data-i18n="outline.sceneTitle">${t("outline.sceneTitle")}</span>
          <input class="scene-title" value="${escapeHTML(scene.title)}" />
        </label>
        <label>
          <span data-i18n="outline.duration">${t("outline.duration")}</span>
          <input class="scene-duration" type="number" min="1" step="0.5" value="${scene.duration_seconds}" />
        </label>
      </div>
      <label>
        <span data-i18n="outline.visual">${t("outline.visual")}</span>
        <textarea class="scene-visual" rows="3">${escapeHTML(scene.visual_description_zh)}</textarea>
      </label>
      <label>
        <span data-i18n="outline.copy">${t("outline.copy")}</span>
        <textarea class="scene-copy" rows="3">${escapeHTML(scene.voiceover_or_subtitle_zh)}</textarea>
      </label>
    `;
    scenesContainer.appendChild(card);
  });

  applyStaticTranslations();
}

function refreshOutlineMeta() {
  const outlineMeta = document.getElementById("outlineMeta");
  if (!outlineMeta || !currentOutlineSource) {
    return;
  }

  outlineMeta.textContent =
    currentOutlineSource === "mock" ? t("outline.mockMeta") : t("outline.openaiMeta");
}

function readOutlineFromReviewForm() {
  const sceneCards = [...document.querySelectorAll(".scene-card")];
  const scenes = sceneCards.map((card, index) => ({
    scene_number: index + 1,
    title: card.querySelector(".scene-title").value.trim(),
    visual_description_zh: card.querySelector(".scene-visual").value.trim(),
    voiceover_or_subtitle_zh: card.querySelector(".scene-copy").value.trim(),
    duration_seconds: Number(card.querySelector(".scene-duration").value || 3),
  }));

  return {
    hook_zh: document.getElementById("hookInput").value.trim(),
    structure_summary_zh: document.getElementById("summaryInput").value.trim(),
    scenes,
    voiceover_full_zh: document.getElementById("voiceoverInput").value.trim(),
    music_style_zh: document.getElementById("musicInput").value.trim(),
    hashtags: document
      .getElementById("hashtagsInput")
      .value.split(/[,，\s]+/)
      .map((item) => item.trim())
      .filter(Boolean),
    creative_notes_zh: document.getElementById("notesInput").value.trim(),
  };
}

async function generatePrompts() {
  setLoading(approveButton, true, t("loading.generatingPrompts"));

  try {
    const result = await postJSON("/api/generate-prompts", {
      questionnaire: currentQuestionnaire,
      outline: currentOutline,
      target_tool: document.getElementById("targetTool")?.value || "sora-2",
    });

    currentPromptPackage = result.prompt_package;
    currentPromptSource = result.source;
    renderPrompts(currentPromptPackage, currentPromptSource);
    promptSection.hidden = false;
    promptSection.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    showToast(error.message, true);
  } finally {
    setLoading(approveButton, false, t("button.approveGeneratePrompts"));
  }
}

function renderPrompts(packageData, source) {
  currentPromptSource = source;
  refreshPromptMeta();

  const container = document.getElementById("promptsContainer");
  container.innerHTML = "";

  packageData.scene_prompts.forEach((scene) => {
    const card = document.createElement("div");
    card.className = "prompt-card";
    card.innerHTML = `
      <h4>Scene ${scene.scene_number} · ${scene.duration_seconds}s</h4>
      <div class="prompt-text">${escapeHTML(scene.prompt_en)}</div>
      <div class="tool-row">
        <button class="generate-video-button" type="button" data-scene-number="${scene.scene_number}" data-i18n="button.generateSceneVideo">
          ${t("button.generateSceneVideo")}
        </button>
      </div>
      <div class="video-result" id="videoResult-${scene.scene_number}"></div>
    `;
    container.appendChild(card);
  });

  document.querySelectorAll(".generate-video-button").forEach((button) => {
    button.addEventListener("click", async () => {
      const sceneNumber = Number(button.dataset.sceneNumber);
      const scene = currentPromptPackage.scene_prompts.find(
        (item) => item.scene_number === sceneNumber
      );

      if (!scene) {
        showToast(t("prompt.missingScene"), true);
        return;
      }

      await generateSceneVideo(scene, button);
    });
  });

  applyStaticTranslations();
}

function refreshPromptMeta() {
  const promptMeta = document.getElementById("promptMeta");
  if (!promptMeta || !currentPromptPackage) {
    return;
  }

  promptMeta.innerHTML = `
    <strong>${t("prompt.platform")}：</strong>${escapeHTML(currentPromptPackage.platform)}　
    <strong>${t("prompt.aspectRatio")}：</strong>${escapeHTML(currentPromptPackage.aspect_ratio)}　
    <strong>${t("prompt.source")}：</strong>${currentPromptSource === "mock" ? "Mock AI" : "OpenAI"}<br />
    <strong>${t("prompt.globalStyle")}：</strong>${escapeHTML(currentPromptPackage.global_style_prompt_en)}<br />
    <strong>${t("prompt.editingNotes")}：</strong>${escapeHTML(currentPromptPackage.editing_notes_zh)}
  `;
}

async function generateSceneVideo(scene, button) {
  button.removeAttribute("data-i18n");
  setLoading(button, true, t("loading.generatingVideo"));

  const resultBox = document.getElementById(`videoResult-${scene.scene_number}`);
  resultBox.innerHTML = `<p class="muted" data-i18n="video.generatingNotice">${t("video.generatingNotice")}</p>`;

  try {
    const result = await postJSON("/api/generate-scene-video", {
      prompt_en: scene.prompt_en,
      duration_seconds: scene.duration_seconds,
    });

    resultBox.innerHTML = `
      <div class="video-preview">
        <video src="${escapeHTML(result.video_url)}" controls playsinline></video>
        <p>
          <strong data-i18n="video.videoId">${t("video.videoId")}</strong>: ${escapeHTML(result.video_id)}<br />
          <strong data-i18n="video.model">${t("video.model")}</strong>: ${escapeHTML(result.model)} ·
          <strong data-i18n="video.size">${t("video.size")}</strong>: ${escapeHTML(result.size)} ·
          <strong data-i18n="video.duration">${t("video.duration")}</strong>: ${escapeHTML(result.seconds)}s
        </p>
        <a href="${escapeHTML(result.video_url)}" download data-i18n="video.download">${t("video.download")}</a>
      </div>
    `;
    applyStaticTranslations();
    showToast(t("toast.videoGenerated", { sceneNumber: scene.scene_number }));
  } catch (error) {
    resultBox.innerHTML = "";
    showToast(error.message, true);
  } finally {
    button.setAttribute("data-i18n", "button.regenerateSceneVideo");
    setLoading(button, false, t("button.regenerateSceneVideo"));
  }
}

async function postJSON(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || t("error.requestFailed", { status: response.status }));
  }

  return response.json();
}

function setLoading(button, isLoading, text) {
  button.disabled = isLoading;
  button.textContent = text;
}

function showToast(message, isError = false) {
  const toast = document.getElementById("toast");
  toast.textContent = message;
  toast.className = isError ? "toast error" : "toast";
  toast.hidden = false;

  setTimeout(() => {
    toast.hidden = true;
  }, 3800);
}

function escapeHTML(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
