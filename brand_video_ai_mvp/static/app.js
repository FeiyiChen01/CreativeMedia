// Minimal frontend state. This keeps the MVP simple and easy to debug.
let currentQuestionnaire = null;
let currentOutline = null;
let currentPromptPackage = null;

const form = document.getElementById("questionnaireForm");
const outlineSection = document.getElementById("outlineSection");
const promptSection = document.getElementById("promptSection");
const generateOutlineButton = document.getElementById("generateOutlineButton");
const approveButton = document.getElementById("approveButton");
const regenerateButton = document.getElementById("regenerateButton");
const copyPromptsButton = document.getElementById("copyPromptsButton");

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
  showToast("已复制全部视频 Prompt");
});

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
    language: "zh",
  };
}

async function generateOutline() {
  setLoading(generateOutlineButton, true, "生成中...");
  setLoading(regenerateButton, true, "重新生成中...");
  promptSection.hidden = true;

  try {
    const result = await postJSON("/api/generate-outline", {
      questionnaire: currentQuestionnaire,
    });

    currentOutline = result.outline;
    renderOutline(currentOutline, result.source);
    outlineSection.hidden = false;
    outlineSection.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    showToast(error.message, true);
  } finally {
    setLoading(generateOutlineButton, false, "生成视频大纲");
    setLoading(regenerateButton, false, "重新生成大纲");
  }
}

function renderOutline(outline, source) {
  document.getElementById("outlineMeta").textContent =
    source === "mock"
      ? "当前使用 Mock AI 输出：你还没有配置 OPENAI_API_KEY，但可以先测试完整流程。"
      : "已使用 OpenAI 生成大纲。你可以直接修改任意内容后再生成视频 Prompt。";

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
          场景标题
          <input class="scene-title" value="${escapeHTML(scene.title)}" />
        </label>
        <label>
          秒数
          <input class="scene-duration" type="number" min="1" step="0.5" value="${scene.duration_seconds}" />
        </label>
      </div>
      <label>
        画面描述
        <textarea class="scene-visual" rows="3">${escapeHTML(scene.visual_description_zh)}</textarea>
      </label>
      <label>
        配音 / 字幕
        <textarea class="scene-copy" rows="3">${escapeHTML(scene.voiceover_or_subtitle_zh)}</textarea>
      </label>
    `;
    scenesContainer.appendChild(card);
  });
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
  setLoading(approveButton, true, "生成 Prompt 中...");

  try {
    const result = await postJSON("/api/generate-prompts", {
      questionnaire: currentQuestionnaire,
      outline: currentOutline,
      target_tool: document.getElementById("targetTool").value,
    });

    currentPromptPackage = result.prompt_package;
    renderPrompts(currentPromptPackage, result.source);
    promptSection.hidden = false;
    promptSection.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    showToast(error.message, true);
  } finally {
    setLoading(approveButton, false, "通过并生成视频 Prompt");
  }
}

function renderPrompts(packageData, source) {
  document.getElementById("promptMeta").innerHTML = `
    <strong>平台：</strong>${escapeHTML(packageData.platform)}　
    <strong>画幅：</strong>${escapeHTML(packageData.aspect_ratio)}　
    <strong>来源：</strong>${source === "mock" ? "Mock AI" : "OpenAI"}<br />
    <strong>全局风格：</strong>${escapeHTML(packageData.global_style_prompt_en)}<br />
    <strong>剪辑备注：</strong>${escapeHTML(packageData.editing_notes_zh)}
  `;

  const container = document.getElementById("promptsContainer");
  container.innerHTML = "";

  packageData.scene_prompts.forEach((scene) => {
    const card = document.createElement("div");
    card.className = "prompt-card";
    card.innerHTML = `
      <h4>Scene ${scene.scene_number} · ${scene.duration_seconds}s</h4>
      <div class="prompt-text">${escapeHTML(scene.prompt_en)}</div>
      <div class="tool-row">
        <button class="generate-video-button" type="button" data-scene-number="${scene.scene_number}">
          生成这个 Scene 的视频片段
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
        showToast("没有找到这个 Scene 的 Prompt", true);
        return;
      }

      await generateSceneVideo(scene, button);
    });
  });
}

async function generateSceneVideo(scene, button) {
  setLoading(button, true, "视频生成中...");

  const resultBox = document.getElementById(`videoResult-${scene.scene_number}`);
  resultBox.innerHTML = `<p class="muted">OpenAI 正在生成视频片段，这可能需要一段时间。请先只测试一个 Scene。</p>`;

  try {
    const result = await postJSON("/api/generate-scene-video", {
      prompt_en: scene.prompt_en,
      duration_seconds: scene.duration_seconds,
    });

    resultBox.innerHTML = `
      <div class="video-preview">
        <video src="${escapeHTML(result.video_url)}" controls playsinline></video>
        <p>
          <strong>Video ID:</strong> ${escapeHTML(result.video_id)}<br />
          <strong>Model:</strong> ${escapeHTML(result.model)} ·
          <strong>Size:</strong> ${escapeHTML(result.size)} ·
          <strong>Duration:</strong> ${escapeHTML(result.seconds)}s
        </p>
        <a href="${escapeHTML(result.video_url)}" download>下载 MP4</a>
      </div>
    `;
    showToast(`Scene ${scene.scene_number} 视频生成完成`);
  } catch (error) {
    resultBox.innerHTML = "";
    showToast(error.message, true);
  } finally {
    setLoading(button, false, "重新生成这个 Scene 的视频片段");
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
    throw new Error(errorData.detail || `请求失败：${response.status}`);
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
