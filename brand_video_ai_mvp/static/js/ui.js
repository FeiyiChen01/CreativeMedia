(function () {
  const studioState = {
    outline: null,
    outlineSource: null,
    promptPackage: null,
    generatedVideos: 0,
    socialAccounts: []
  };

  function $(id) {
    return document.getElementById(id);
  }

  function showElement(element) {
    if (element) element.classList.remove('hidden');
  }

  function hideElement(element) {
    if (element) element.classList.add('hidden');
  }

  function setText(id, value) {
    const element = $(id);
    if (element) element.textContent = value;
  }

  function setHtml(id, value) {
    const element = $(id);
    if (element) element.innerHTML = value;
  }

  function escapeHtml(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function showPage(pageId) {
    ['page-auth', 'page-questionnaire', 'page-main'].forEach((id) => {
      const page = $(id);
      if (page) page.classList.toggle('hidden', id !== pageId);
    });
  }

  function showError(containerId, message) {
    const container = $(containerId);
    if (!container) return;
    container.textContent = message;
    container.classList.remove('hidden');
  }

  function clearError(containerId) {
    const container = $(containerId);
    if (!container) return;
    container.textContent = '';
    container.classList.add('hidden');
  }

  function setButtonLoading(button, isLoading, loadingText) {
    if (!button) return;

    if (isLoading) {
      button.dataset.originalHtml = button.innerHTML;
      button.disabled = true;
      button.innerHTML = `<i class="fa-solid fa-spinner animate-spin"></i><span>${escapeHtml(loadingText)}</span>`;
      return;
    }

    button.disabled = false;
    if (button.dataset.originalHtml) {
      button.innerHTML = button.dataset.originalHtml;
      delete button.dataset.originalHtml;
    }
  }

  function validateEmail(email) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
  }

  function validatePassword(password) {
    return password.length >= 8 && /[A-Z]/.test(password) && /[a-z]/.test(password) && /\d/.test(password);
  }

  function getFormData(form) {
    return Object.fromEntries(new FormData(form).entries());
  }

  function showAuthPage() {
    showPage('page-auth');
    clearError('auth-error');
    switchAuthTab('login');
  }

  function showQuestionnairePage(isEditing = false) {
    showPage('page-questionnaire');
    clearError('questionnaire-error');
    prefillQuestionnaireForm();
    updateQuestionnairePreview();

    if (isEditing) {
      const title = document.querySelector('#page-questionnaire h2');
      if (title) title.textContent = '编辑你的品牌问卷';
    }
  }

  function showMainPage() {
    showPage('page-main');
    hydrateUserInterface();
    renderQuestionnaireSummary();
    loadSocialAccounts();
    switchTab('studio');
  }

  function switchAuthTab(type) {
    const isLogin = type === 'login';
    $('login-form')?.classList.toggle('hidden', !isLogin);
    $('register-form')?.classList.toggle('hidden', isLogin);
    $('auth-tab-login')?.classList.toggle('auth-tab-active', isLogin);
    $('auth-tab-register')?.classList.toggle('auth-tab-active', !isLogin);
    clearError('auth-error');
  }

  async function routeAfterAuth(forceQuestionnaire = false) {
    if (!window.authState.isAuthenticated) {
      showAuthPage();
      return;
    }

    if (forceQuestionnaire) {
      window.setQuestionnaire(null);
      showQuestionnairePage();
      return;
    }

    try {
      const questionnaire = await window.Api.getQuestionnaire();
      if (questionnaire && questionnaire.id) {
        window.setQuestionnaire(questionnaire);
        showMainPage();
      } else {
        window.setQuestionnaire(null);
        showQuestionnairePage();
      }
    } catch (error) {
      if (error.status === 404) {
        window.setQuestionnaire(null);
        showQuestionnairePage();
        return;
      }

      const cachedQuestionnaire = window.getQuestionnaireFromStorage ? window.getQuestionnaireFromStorage() : null;
      if (cachedQuestionnaire) {
        window.setQuestionnaire(cachedQuestionnaire);
        showMainPage();
        return;
      }

      showQuestionnairePage();
    }
  }

  async function handleLogin(event) {
    event.preventDefault();
    clearError('auth-error');

    const form = event.currentTarget;
    const data = getFormData(form);
    const email = String(data.email || '').trim().toLowerCase();
    const password = String(data.password || '');

    if (!validateEmail(email)) {
      showError('auth-error', 'Please enter a valid email address.');
      return;
    }

    if (!password) {
      showError('auth-error', 'Please enter your password.');
      return;
    }

    const button = $('login-submit-btn');
    setButtonLoading(button, true, 'Logging in...');

    try {
      const response = await window.Api.login(email, password);
      window.setToken(response.access_token, response.user);
      await routeAfterAuth(false);
    } catch (error) {
      showError('auth-error', error.message || 'Login failed.');
    } finally {
      setButtonLoading(button, false);
    }
  }

  async function handleRegister(event) {
    event.preventDefault();
    clearError('auth-error');

    const form = event.currentTarget;
    const data = getFormData(form);
    const username = String(data.username || '').trim();
    const email = String(data.email || '').trim().toLowerCase();
    const password = String(data.password || '');
    const passwordConfirm = String(data.password_confirm || '');
    const termsChecked = $('register-terms')?.checked;

    if (username.length < 3) {
      showError('auth-error', 'Username must be at least 3 characters.');
      return;
    }

    if (!validateEmail(email)) {
      showError('auth-error', 'Please enter a valid email address.');
      return;
    }

    if (!validatePassword(password)) {
      showError('auth-error', 'Password must be at least 8 characters and include uppercase, lowercase, and number.');
      return;
    }

    if (password !== passwordConfirm) {
      showError('auth-error', 'Password confirmation does not match.');
      return;
    }

    if (!termsChecked) {
      showError('auth-error', 'Please agree to the Terms of Service.');
      return;
    }

    const button = $('register-submit-btn');
    setButtonLoading(button, true, 'Creating account...');

    try {
      const response = await window.Api.register(email, username, password, passwordConfirm);
      window.setToken(response.access_token, response.user);
      window.setQuestionnaire(null);
      showQuestionnairePage();
    } catch (error) {
      showError('auth-error', error.message || 'Registration failed.');
    } finally {
      setButtonLoading(button, false);
    }
  }

  function getQuestionnaireFormPayload() {
    const form = $('questionnaire-form');
    const data = getFormData(form);
    const selectedStyle = String(data.video_style || '').trim();
    const customStyle = String(data.custom_video_style || '').trim();
    const finalStyle = selectedStyle === '其他' && customStyle ? customStyle : selectedStyle;

    return {
      brand_name: String(data.brand_name || '').trim(),
      brand_description: String(data.brand_description || '').trim(),
      target_audience: String(data.target_audience || '').trim(),
      video_style: finalStyle,
      additional_info: {
        source: 'frontend_onboarding',
        preferred_language: 'zh'
      }
    };
  }

  async function handleQuestionnaireSubmit(event) {
    event.preventDefault();
    clearError('questionnaire-error');

    const payload = getQuestionnaireFormPayload();

    if (!payload.brand_name || !payload.brand_description || !payload.target_audience || !payload.video_style) {
      showError('questionnaire-error', 'Please complete all required fields before continuing.');
      return;
    }

    const button = $('questionnaire-submit-btn');
    setButtonLoading(button, true, 'Saving profile...');

    try {
      const questionnaire = await window.Api.saveQuestionnaire(payload);
      window.setQuestionnaire(questionnaire);
      showMainPage();
    } catch (error) {
      showError('questionnaire-error', error.message || 'Failed to save questionnaire.');
    } finally {
      setButtonLoading(button, false);
    }
  }

  async function handleLogout() {
    try {
      if (window.authState.isAuthenticated) {
        await window.Api.logout();
      }
    } catch (error) {
      console.warn('Logout API failed. Local session will still be cleared.', error);
    } finally {
      window.clearAuth();
      resetStudioState();
      showAuthPage();
    }
  }

  function updateQuestionnairePreview() {
    const brandName = $('brand-name')?.value.trim() || '未填写品牌名称';
    const brandDescription = $('brand-description')?.value.trim() || '品牌描述会显示在这里。';
    const targetAudience = $('target-audience')?.value.trim() || '未填写';
    const selectedStyle = $('video-style')?.value || '';
    const customStyle = $('custom-video-style')?.value.trim() || '';
    const videoStyle = selectedStyle === '其他' && customStyle ? customStyle : selectedStyle || '未选择';

    setText('preview-brand-name', brandName);
    setText('preview-brand-description', brandDescription);
    setText('preview-target-audience', targetAudience);
    setText('preview-video-style', videoStyle);

    const requiredValues = [
      $('brand-name')?.value.trim(),
      $('brand-description')?.value.trim(),
      $('target-audience')?.value.trim(),
      videoStyle !== '未选择' ? videoStyle : ''
    ];
    const completed = requiredValues.filter(Boolean).length;
    const progressPercent = Math.round((completed / 4) * 100);

    setText('questionnaire-progress-label', `${completed}/4`);
    const bar = $('questionnaire-progress-bar');
    if (bar) bar.style.width = `${progressPercent}%`;
  }

  function prefillQuestionnaireForm() {
    const questionnaire = window.authState.questionnaire || window.getQuestionnaireFromStorage?.();
    if (!questionnaire) return;

    if ($('brand-name')) $('brand-name').value = questionnaire.brand_name || '';
    if ($('brand-description')) $('brand-description').value = questionnaire.brand_description || '';
    if ($('target-audience')) $('target-audience').value = questionnaire.target_audience || '';

    const styleSelect = $('video-style');
    const customStyleWrapper = $('custom-style-wrapper');
    const customStyleInput = $('custom-video-style');
    const knownStyles = ['专业商务风', '创意潮流风', '温暖人文风', '科技未来风'];
    const style = questionnaire.video_style || '';

    if (styleSelect) {
      if (knownStyles.includes(style)) {
        styleSelect.value = style;
        if (customStyleWrapper) customStyleWrapper.classList.add('hidden');
      } else if (style) {
        styleSelect.value = '其他';
        if (customStyleWrapper) customStyleWrapper.classList.remove('hidden');
        if (customStyleInput) customStyleInput.value = style;
      }
    }
  }

  function hydrateUserInterface() {
    const user = window.authState.user || window.getCurrentUser?.();
    if (!user) return;

    setText('sidebar-username', user.username || 'User');
    setText('sidebar-email', user.email || '');
    setText('user-avatar-letter', (user.username || user.email || 'U').charAt(0).toUpperCase());
  }

  function renderQuestionnaireSummary() {
    const questionnaire = window.authState.questionnaire;
    if (!questionnaire) return;

    setText('studio-brand-name', questionnaire.brand_name || '-');
    setText('studio-video-style', questionnaire.video_style || '-');
    setText('studio-target-audience', questionnaire.target_audience || '-');
    setText('studio-brand-description', questionnaire.brand_description || '-');

    setText('dashboard-summary', `${questionnaire.brand_name || 'Your brand'} targets ${questionnaire.target_audience || 'your audience'} with a ${questionnaire.video_style || 'custom'} video style. ${questionnaire.brand_description || ''}`);
  }

  function switchTab(tabId) {
    ['dashboard', 'studio', 'social', 'calendar'].forEach((tab) => {
      const tabEl = $(`tab-${tab}`);
      const navEl = $(`nav-${tab}`);
      if (tabEl) tabEl.classList.toggle('hidden', tab !== tabId);
      if (navEl) navEl.classList.toggle('nav-active', tab === tabId);
    });

    const titles = {
      dashboard: '品牌全渠道监控看板',
      studio: 'AI 创作实验室',
      social: '关联社交媒体',
      calendar: '多端自动发布排期'
    };
    setText('workspace-title', titles[tabId] || 'OmniSocial AI');

    if (tabId === 'social') {
      loadSocialAccounts();
    }
  }

  function mapQuestionnaireToAiPayload(questionnaire) {
    const description = questionnaire.brand_description || '';
    const style = questionnaire.video_style || 'cinematic TikTok short-form video';

    return {
      brand_name: questionnaire.brand_name || 'Unknown Brand',
      industry: style,
      target_audience: questionnaire.target_audience || 'general audience',
      brand_keywords: [style, 'brand storytelling', 'short video'],
      promotion_theme: description || 'brand awareness campaign',
      video_length: '15-30 seconds',
      language: 'zh'
    };
  }

  function setStudioProgress(percent, text) {
    showElement($('studio-progress'));
    const bar = $('studio-bar');
    if (bar) bar.style.width = `${percent}%`;
    setText('studio-percent', `${percent}%`);
    setText('studio-stage', text);
  }

  function hideStudioProgressSoon() {
    setTimeout(() => hideElement($('studio-progress')), 700);
  }

  async function handleGenerateOutline() {
    clearError('studio-error');

    const questionnaire = window.authState.questionnaire;
    if (!questionnaire) {
      showError('studio-error', 'Questionnaire is missing. Please complete onboarding first.');
      showQuestionnairePage();
      return;
    }

    const button = $('btn-generate-outline');
    setButtonLoading(button, true, 'Generating outline...');
    setStudioProgress(20, 'Generating video outline from saved questionnaire...');

    try {
      const aiPayload = mapQuestionnaireToAiPayload(questionnaire);
      const response = await window.Api.generateOutline(aiPayload);
      studioState.outline = response.outline;
      studioState.outlineSource = response.source;
      studioState.promptPackage = null;
      setStudioProgress(100, 'Outline generated.');
      renderOutline(response.outline, response.source);
      const promptButton = $('btn-generate-prompts');
      if (promptButton) promptButton.disabled = false;
      hideStudioProgressSoon();
    } catch (error) {
      showError('studio-error', error.message || 'Failed to generate outline.');
      hideElement($('studio-progress'));
    } finally {
      setButtonLoading(button, false);
    }
  }

  async function handleGeneratePrompts() {
    clearError('studio-error');

    if (!studioState.outline) {
      showError('studio-error', 'Please generate an outline first.');
      return;
    }

    const questionnaire = window.authState.questionnaire;
    const aiPayload = mapQuestionnaireToAiPayload(questionnaire);
    const button = $('btn-generate-prompts');

    setButtonLoading(button, true, 'Generating scenes...');
    setStudioProgress(35, 'Creating Sora scene prompts in the background...');

    try {
      const response = await window.Api.generatePrompts(aiPayload, studioState.outline, 'sora-2');
      studioState.promptPackage = response.prompt_package;
      setStudioProgress(100, 'Sora scene prompts are ready.');
      renderScenePromptActions(response.prompt_package);
      hideStudioProgressSoon();
    } catch (error) {
      showError('studio-error', error.message || 'Failed to generate prompts.');
      hideElement($('studio-progress'));
    } finally {
      setButtonLoading(button, false);
    }
  }

  async function handleGenerateSceneVideo(sceneIndex) {
    clearError('studio-error');

    const scenePrompt = studioState.promptPackage?.scene_prompts?.[sceneIndex];
    if (!scenePrompt) {
      showError('studio-error', 'Scene prompt is missing. Please regenerate prompts.');
      return;
    }

    const button = $(`scene-video-btn-${sceneIndex}`);
    const resultContainer = $(`scene-video-result-${sceneIndex}`);
    setButtonLoading(button, true, 'Generating video...');
    setStudioProgress(55, `Generating scene ${scenePrompt.scene_number} with Sora-2...`);

    try {
      const result = await window.Api.generateSceneVideo(scenePrompt.prompt_en, scenePrompt.duration_seconds);
      studioState.generatedVideos += 1;
      setText('metric-generated', String(studioState.generatedVideos));
      setText('preview-caption', `Scene ${scenePrompt.scene_number} generated successfully.`);

      if (resultContainer) {
        resultContainer.innerHTML = `
          <div class="mt-3 space-y-3">
            <video class="video-frame" src="${escapeHtml(result.video_url)}" controls playsinline></video>
            <a href="${escapeHtml(result.video_url)}" download class="secondary-btn w-full text-xs">
              <i class="fa-solid fa-download"></i>
              Download Scene Video
            </a>
          </div>
        `;
      }

      setStudioProgress(100, `Scene ${scenePrompt.scene_number} video is ready.`);
      hideStudioProgressSoon();
    } catch (error) {
      showError('studio-error', error.message || 'Failed to generate scene video.');
      hideElement($('studio-progress'));
    } finally {
      setButtonLoading(button, false);
    }
  }

  function renderOutline(outline, source) {
    showElement($('outline-panel'));
    setText('outline-source', source || '-');

    const scenes = outline.scenes || [];
    const sceneHtml = scenes.map((scene) => `
      <div class="outline-card">
        <div class="flex items-center justify-between mb-2">
          <h5 class="text-sm font-bold text-white">Scene ${escapeHtml(scene.scene_number)} · ${escapeHtml(scene.title || '')}</h5>
          <span class="text-[10px] text-brand-purple font-bold">${escapeHtml(scene.duration_seconds || '')}s</span>
        </div>
        <p class="text-xs text-slate-400 leading-relaxed mb-2">${escapeHtml(scene.visual_description_zh || '')}</p>
        <p class="text-xs text-slate-300 leading-relaxed">${escapeHtml(scene.voiceover_or_subtitle_zh || '')}</p>
      </div>
    `).join('');

    setHtml('outline-content', `
      <div class="outline-card border-brand-purple/40">
        <div class="text-[10px] text-slate-500 uppercase tracking-widest mb-1">Hook</div>
        <p class="text-sm text-white font-semibold">${escapeHtml(outline.hook_zh || '')}</p>
      </div>
      <div class="outline-card">
        <div class="text-[10px] text-slate-500 uppercase tracking-widest mb-1">Structure</div>
        <p class="text-xs text-slate-400 leading-relaxed">${escapeHtml(outline.structure_summary_zh || '')}</p>
      </div>
      ${sceneHtml}
    `);
  }

  function renderScenePromptActions(promptPackage) {
    const scenePrompts = promptPackage.scene_prompts || [];

    if (!scenePrompts.length) {
      setHtml('scene-video-list', '<p class="text-xs text-slate-500">No scene prompts returned.</p>');
      return;
    }

    const html = scenePrompts.map((scene, index) => `
      <div class="scene-card">
        <div class="flex items-center justify-between gap-3 mb-3">
          <div>
            <div class="text-sm font-bold text-white">Scene ${escapeHtml(scene.scene_number)}</div>
            <div class="text-[10px] text-slate-500">${escapeHtml(scene.duration_seconds)} seconds · Prompt hidden</div>
          </div>
          <button id="scene-video-btn-${index}" onclick="handleGenerateSceneVideo(${index})" class="primary-btn text-xs py-2 px-3">
            <i class="fa-solid fa-video"></i>
            Generate
          </button>
        </div>
        <div id="scene-video-result-${index}"></div>
      </div>
    `).join('');

    setHtml('scene-video-list', html);
    setText('preview-caption', 'Scene prompts are ready. Generate any scene video.');
  }

  function resetStudioState() {
    studioState.outline = null;
    studioState.outlineSource = null;
    studioState.promptPackage = null;
    hideElement($('outline-panel'));
    hideElement($('studio-progress'));
    clearError('studio-error');
    setHtml('outline-content', '');
    setHtml('scene-video-list', '');
    setText('preview-caption', 'Generate an outline first. Scene videos will appear here.');
    const promptButton = $('btn-generate-prompts');
    if (promptButton) promptButton.disabled = true;
  }

  async function loadSocialAccounts() {
    if (!window.authState.isAuthenticated) return;

    try {
      const accounts = await window.Api.listSocialAccounts();
      studioState.socialAccounts = accounts || [];
      renderSocialAccounts();
    } catch (error) {
      console.warn('Failed to load social accounts.', error);
    }
  }

  function renderSocialAccounts() {
    const accounts = studioState.socialAccounts || [];
    setText('metric-socials', String(accounts.length));

    setText('ig-status', accounts.some((item) => item.platform === 'instagram') ? '已绑定' : '待绑定');
    setText('yt-status', accounts.some((item) => item.platform === 'youtube') ? '已绑定' : '待绑定');
    setText('tt-status', accounts.some((item) => item.platform === 'tiktok') ? '已绑定' : '待绑定');

    if (!accounts.length) {
      setHtml('social-accounts-list', '<p class="text-sm text-slate-500">No accounts linked yet.</p>');
      return;
    }

    const html = accounts.map((account) => `
      <div class="social-account-card flex items-center justify-between gap-4">
        <div>
          <div class="text-sm font-bold text-white capitalize">${escapeHtml(account.platform)}</div>
          <div class="text-xs text-slate-500">${escapeHtml(account.account_handle || account.account_url || '')}</div>
        </div>
        <i class="fa-solid fa-circle-check text-brand-teal"></i>
      </div>
    `).join('');

    setHtml('social-accounts-list', html);
  }

  async function handleSocialSubmit(event) {
    event.preventDefault();
    clearError('social-error');

    const form = event.currentTarget;
    const data = getFormData(form);
    const payload = {
      platform: String(data.platform || '').trim(),
      account_url: String(data.account_url || '').trim() || null,
      account_handle: String(data.account_handle || '').trim() || null
    };

    if (!payload.account_url && !payload.account_handle) {
      showError('social-error', 'Please provide either account URL or account handle.');
      return;
    }

    const button = $('social-submit-btn');
    setButtonLoading(button, true, 'Saving account...');

    try {
      await window.Api.addSocialAccount(payload);
      form.reset();
      await loadSocialAccounts();
    } catch (error) {
      showError('social-error', error.message || 'Failed to save social account.');
    } finally {
      setButtonLoading(button, false);
    }
  }

  async function initializeApp() {
    await window.initAuth();

    if (!window.authState.isAuthenticated) {
      showAuthPage();
      return;
    }

    await routeAfterAuth(false);
  }

  function bindEvents() {
    $('login-form')?.addEventListener('submit', handleLogin);
    $('register-form')?.addEventListener('submit', handleRegister);
    $('questionnaire-form')?.addEventListener('submit', handleQuestionnaireSubmit);
    $('social-form')?.addEventListener('submit', handleSocialSubmit);

    document.querySelectorAll('.questionnaire-field').forEach((field) => {
      field.addEventListener('input', updateQuestionnairePreview);
      field.addEventListener('change', updateQuestionnairePreview);
    });

    $('custom-video-style')?.addEventListener('input', updateQuestionnairePreview);

    $('video-style')?.addEventListener('change', () => {
      const isCustom = $('video-style')?.value === '其他';
      $('custom-style-wrapper')?.classList.toggle('hidden', !isCustom);
      updateQuestionnairePreview();
    });
  }

  document.addEventListener('DOMContentLoaded', async () => {
    bindEvents();
    await initializeApp();
  });

  window.showAuthPage = showAuthPage;
  window.showQuestionnairePage = showQuestionnairePage;
  window.showMainPage = showMainPage;
  window.switchAuthTab = switchAuthTab;
  window.switchTab = switchTab;
  window.handleLogout = handleLogout;
  window.handleGenerateOutline = handleGenerateOutline;
  window.handleGeneratePrompts = handleGeneratePrompts;
  window.handleGenerateSceneVideo = handleGenerateSceneVideo;
  window.resetStudioState = resetStudioState;
})();
