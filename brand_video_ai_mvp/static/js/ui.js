(function () {
  const studioState = {
    outline: null,
    outlineSource: null,
    generatedOutlineId: null,
    promptPackage: null,
    generatedPromptPackageId: null,
    generatedVideos: 0,
    socialAccounts: [],
    videoAssets: [],
    publishingJobs: [],
    pendingYouTubeStatus: null
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

  function showSuccess(containerId, message) {
    const container = $(containerId);
    if (!container) return;
    container.textContent = message;
    container.classList.remove('hidden');
  }

  function clearSuccess(containerId) {
    const container = $(containerId);
    if (!container) return;
    container.textContent = '';
    container.classList.add('hidden');
  }

  function escapeHtml(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function renderImagePreview(containerId, imageUrl, fallbackText) {
    const container = $(containerId);
    if (!container) return;
    if (imageUrl) {
      container.innerHTML = `<img src="${escapeHtml(imageUrl)}" alt="" class="w-full h-full object-cover">`;
    } else {
      container.textContent = fallbackText;
    }
  }

  function renderAvatar(containerId, imageUrl, displayName) {
    renderImagePreview(containerId, imageUrl, (displayName || 'U').charAt(0).toUpperCase());
  }

  async function refreshProfileState() {
    const user = await window.Api.getProfile();
    window.authState.user = user;
    localStorage.setItem('current_user', JSON.stringify(user));
    renderProfile(user);
    hydrateUserInterface();
    return user;
  }

  function renderBrandLogoPreview(logoUrl) {
    const wrapper = $('brand-logo-preview-wrapper');
    const image = $('brand-logo-preview');
    if (wrapper) wrapper.classList.toggle('hidden', !logoUrl);
    if (image) image.src = logoUrl || '';
    setText('preview-logo-status', logoUrl ? '已上传' : '未上传');
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
    clearSuccess('questionnaire-success');
    prefillQuestionnaireForm();
    updateQuestionnairePreview();

    if (isEditing) {
      const title = document.querySelector('#page-questionnaire h2');
      if (title) title.textContent = 'Edit your Brand Profile';
    }
  }

  function showMainPage() {
    showPage('page-main');
    hydrateUserInterface();
    renderQuestionnaireSummary();
    loadSocialAccounts();
    loadYouTubePublishingData();
    switchTab('dashboard');
  }

  function switchAuthTab(type) {
    const isLogin = type === 'login';
    $('login-form')?.classList.toggle('hidden', !isLogin);
    $('register-form')?.classList.toggle('hidden', isLogin);
    $('forgot-password-form')?.classList.add('hidden');
    $('reset-password-form')?.classList.add('hidden');
    $('auth-tab-login')?.classList.toggle('auth-tab-active', isLogin);
    $('auth-tab-register')?.classList.toggle('auth-tab-active', !isLogin);
    clearError('auth-error');
    clearSuccess('auth-success');
  }

  function showForgotPasswordForm() {
    $('login-form')?.classList.add('hidden');
    $('register-form')?.classList.add('hidden');
    $('reset-password-form')?.classList.add('hidden');
    $('forgot-password-form')?.classList.remove('hidden');
    $('auth-tab-login')?.classList.remove('auth-tab-active');
    $('auth-tab-register')?.classList.remove('auth-tab-active');
    clearError('auth-error');
    clearSuccess('auth-success');
  }

  function showResetPasswordForm(token = '') {
    $('login-form')?.classList.add('hidden');
    $('register-form')?.classList.add('hidden');
    $('forgot-password-form')?.classList.add('hidden');
    $('reset-password-form')?.classList.remove('hidden');
    $('auth-tab-login')?.classList.remove('auth-tab-active');
    $('auth-tab-register')?.classList.remove('auth-tab-active');
    if ($('reset-token')) $('reset-token').value = token;
    clearError('auth-error');
    clearSuccess('auth-success');
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
      const questionnaire = await window.Api.getBrandProfile();
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
      if (response.message) showSuccess('auth-success', response.message);
      showQuestionnairePage();
    } catch (error) {
      showError('auth-error', error.message || 'Registration failed.');
    } finally {
      setButtonLoading(button, false);
    }
  }

  async function handleForgotPassword(event) {
    event.preventDefault();
    clearError('auth-error');
    clearSuccess('auth-success');

    const data = getFormData(event.currentTarget);
    const email = String(data.email || '').trim().toLowerCase();
    if (!validateEmail(email)) {
      showError('auth-error', 'Please enter a valid email address.');
      return;
    }

    const button = $('forgot-password-submit-btn');
    setButtonLoading(button, true, 'Sending reset link...');
    try {
      const response = await window.Api.forgotPassword(email);
      showSuccess('auth-success', response.message || 'If the account exists, a reset link has been sent.');
    } catch (error) {
      showError('auth-error', error.message || 'Failed to request password reset.');
    } finally {
      setButtonLoading(button, false);
    }
  }

  async function handleResetPassword(event) {
    event.preventDefault();
    clearError('auth-error');
    clearSuccess('auth-success');

    const data = getFormData(event.currentTarget);
    const token = String(data.token || '').trim();
    const newPassword = String(data.new_password || '');
    const confirm = String(data.new_password_confirm || '');

    if (!token) {
      showError('auth-error', 'Reset token is required.');
      return;
    }
    if (!validatePassword(newPassword)) {
      showError('auth-error', 'Password must be at least 8 characters and include uppercase, lowercase, and number.');
      return;
    }
    if (newPassword !== confirm) {
      showError('auth-error', 'Password confirmation does not match.');
      return;
    }

    const button = $('reset-password-submit-btn');
    setButtonLoading(button, true, 'Resetting password...');
    try {
      const response = await window.Api.resetPassword(token, newPassword, confirm);
      switchAuthTab('login');
      showSuccess('auth-success', response.message || 'Password reset. Please log in.');
    } catch (error) {
      showError('auth-error', error.message || 'Failed to reset password.');
    } finally {
      setButtonLoading(button, false);
    }
  }

  function getQuestionnaireFormPayload() {
    const form = $('questionnaire-form');
    const data = getFormData(form);

    return {
      company_name: String(data.company_name || '').trim(),
      industry: String(data.industry || '').trim(),
      brand_description: String(data.brand_description || '').trim(),
      brand_tone: String(data.brand_tone || '').trim(),
      use_logo_in_prompt: Boolean($('use-logo-in-prompt')?.checked)
    };
  }

  async function handleQuestionnaireSubmit(event) {
    event.preventDefault();
    clearError('questionnaire-error');
    clearSuccess('questionnaire-success');

    const payload = getQuestionnaireFormPayload();

    if (!payload.company_name || !payload.industry || !payload.brand_description || !payload.brand_tone) {
      showError('questionnaire-error', 'Please complete all required fields before continuing.');
      return;
    }

    const button = $('questionnaire-submit-btn');
    setButtonLoading(button, true, 'Saving profile...');

    try {
      const questionnaire = await window.Api.saveBrandProfile(payload);
      window.setQuestionnaire(questionnaire);
      showSuccess('questionnaire-success', 'Brand Profile saved.');
      showMainPage();
    } catch (error) {
      showError('questionnaire-error', error.message || 'Failed to save Brand Profile.');
    } finally {
      setButtonLoading(button, false);
    }
  }

  async function handleBrandLogoUpload() {
    clearError('questionnaire-error');
    clearSuccess('questionnaire-success');
    const file = $('brand-logo-file')?.files?.[0];
    if (!file) {
      showError('questionnaire-error', 'Please choose a logo image first.');
      return;
    }

    const button = $('brand-logo-upload-btn');
    setButtonLoading(button, true, 'Uploading logo...');
    try {
      const profile = await window.Api.uploadBrandLogo(file);
      window.setQuestionnaire(profile);
      prefillQuestionnaireForm();
      updateQuestionnairePreview();
      showSuccess('questionnaire-success', 'Logo uploaded.');
    } catch (error) {
      showError('questionnaire-error', error.message || 'Failed to upload logo.');
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
    const brandName = $('brand-name')?.value.trim() || '未填写公司名称';
    const industry = $('brand-industry')?.value.trim() || '未填写';
    const brandDescription = $('brand-description')?.value.trim() || '品牌描述会显示在这里。';
    const videoStyle = $('brand-tone')?.value || '未选择';
    const logoStatus = $('brand-logo-preview')?.getAttribute('src') ? '已上传' : '未上传';

    setText('preview-brand-name', brandName);
    setText('preview-industry', industry);
    setText('preview-brand-description', brandDescription);
    setText('preview-logo-status', logoStatus);
    setText('preview-video-style', videoStyle);

    const requiredValues = [
      $('brand-name')?.value.trim(),
      $('brand-industry')?.value.trim(),
      $('brand-description')?.value.trim(),
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

    if ($('brand-name')) $('brand-name').value = questionnaire.company_name || questionnaire.brand_name || '';
    if ($('brand-industry')) $('brand-industry').value = questionnaire.industry || questionnaire.target_audience || '';
    if ($('brand-description')) $('brand-description').value = questionnaire.brand_description || '';
    if ($('brand-tone')) $('brand-tone').value = questionnaire.brand_tone || questionnaire.video_style || '';
    if ($('use-logo-in-prompt')) $('use-logo-in-prompt').checked = Boolean(questionnaire.use_logo_in_prompt);
    renderBrandLogoPreview(questionnaire.logo_url || '');
  }

  function hydrateUserInterface() {
    const user = window.authState.user || window.getCurrentUser?.();
    if (!user) return;

    const displayName = user.display_name || user.full_name || user.company_name || user.username || 'User';
    setText('sidebar-username', displayName);
    setText('sidebar-company', user.display_company_name || (user.full_name && user.company_name ? user.company_name : 'Profile / Account Settings'));
    renderAvatar('user-avatar-letter', user.avatar_url, displayName);
    $('nav-admin')?.classList.toggle('hidden', user.role !== 'admin');
  }

  function renderQuestionnaireSummary() {
    const questionnaire = window.authState.questionnaire;
    if (!questionnaire) return;

    setText('studio-brand-name', questionnaire.company_name || questionnaire.brand_name || '-');
    setText('studio-video-style', questionnaire.brand_tone || questionnaire.video_style || '-');
    setText('studio-target-audience', questionnaire.industry || questionnaire.target_audience || '-');
    setText('studio-brand-description', questionnaire.brand_description || '-');

    setText('dashboard-summary', `${questionnaire.company_name || questionnaire.brand_name || 'Your company'} operates in ${questionnaire.industry || questionnaire.target_audience || 'your industry'} with a ${questionnaire.brand_tone || questionnaire.video_style || 'custom'} brand tone. ${questionnaire.brand_description || ''}`);
  }

  function switchTab(tabId) {
    ['dashboard', 'studio', 'social', 'calendar', 'profile', 'admin'].forEach((tab) => {
      const tabEl = $(`tab-${tab}`);
      const navEl = $(`nav-${tab}`);
      if (tabEl) tabEl.classList.toggle('hidden', tab !== tabId);
      if (navEl) navEl.classList.toggle('nav-active', tab === tabId);
    });

    const titles = {
      dashboard: '品牌全渠道监控看板',
      studio: 'AI 创作实验室',
      social: '关联社交媒体',
      calendar: '多端自动发布排期',
      profile: 'Profile / Account Settings',
      admin: 'Admin Management'
    };
    setText('workspace-title', titles[tabId] || 'OmniSocial AI');

    if (tabId === 'social') {
      loadSocialAccounts();
    }
    if (tabId === 'studio') {
      loadYouTubePublishingData();
    }
    if (tabId === 'profile') {
      loadProfile();
    }
    if (tabId === 'admin') {
      loadAdminDashboard();
    }
  }

  function mapQuestionnaireToAiPayload(questionnaire) {
    const description = questionnaire.brand_description || '';
    const style = questionnaire.video_style || 'cinematic TikTok short-form video';

    return {
      brand_name: questionnaire.company_name || questionnaire.brand_name || 'Unknown Brand',
      industry: questionnaire.industry || style,
      target_audience: questionnaire.industry || questionnaire.target_audience || 'general audience',
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
      studioState.generatedOutlineId = response.generated_outline_id || null;
      studioState.promptPackage = null;
      studioState.generatedPromptPackageId = null;
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
      const response = await window.Api.generatePrompts(aiPayload, studioState.outline, 'sora-2', {
        questionnaire_id: window.authState.questionnaire?.id || null,
        generated_outline_id: studioState.generatedOutlineId
      });
      studioState.promptPackage = response.prompt_package;
      studioState.generatedPromptPackageId = response.generated_prompt_package_id || null;
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
      const created = await window.Api.generateSceneVideo(scenePrompt.prompt_en, scenePrompt.duration_seconds, {
        scene_number: scenePrompt.scene_number,
        prompt_package_id: studioState.generatedPromptPackageId
      });
      if (resultContainer) {
        resultContainer.innerHTML = `
          <div class="mt-3 rounded-xl border border-brand-purple/30 bg-brand-purple/10 p-3 text-xs text-slate-300">
            Job ${escapeHtml(created.job_id)} queued. Polling status...
          </div>
        `;
      }
      await pollVideoJob(created.job_id, scenePrompt, resultContainer);
    } catch (error) {
      showError('studio-error', error.message || 'Failed to generate scene video.');
      hideElement($('studio-progress'));
    } finally {
      setButtonLoading(button, false);
    }
  }

  async function pollVideoJob(jobId, scenePrompt, resultContainer) {
    const maxAttempts = 60;

    for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
      const job = await window.Api.getVideoJob(jobId);
      const percent = job.status === 'success' ? 100 : Math.min(95, 55 + attempt * 2);
      setStudioProgress(percent, `Scene ${scenePrompt.scene_number} video job: ${job.status}`);

      if (resultContainer) {
        resultContainer.innerHTML = `
          <div class="mt-3 rounded-xl border border-brand-border bg-brand-dark/60 p-3 text-xs text-slate-300">
            Job ${escapeHtml(job.id)} · ${escapeHtml(job.status)}
          </div>
        `;
      }

      if (job.status === 'success') {
        studioState.generatedVideos += 1;
        setText('metric-generated', String(studioState.generatedVideos));
        setText('preview-caption', `Scene ${scenePrompt.scene_number} generated successfully.`);
        renderVideoJobResult(job, resultContainer);
        setStudioProgress(100, `Scene ${scenePrompt.scene_number} video is ready.`);
        hideStudioProgressSoon();
        return;
      }

      if (job.status === 'failed') {
        throw new Error(job.error_message || 'Video generation failed.');
      }

      await new Promise((resolve) => setTimeout(resolve, 2000));
    }

    throw new Error('Video job is still running. Check Video Jobs later.');
  }

  function renderVideoJobResult(job, resultContainer) {
    if (!resultContainer) return;

    const asset = job.video_asset;
    const videoUrl = asset?.video_url || '';
    const mediaHtml = videoUrl
      ? `
        <video class="video-frame" src="${escapeHtml(videoUrl)}" controls playsinline></video>
        <a href="${escapeHtml(videoUrl)}" download class="secondary-btn w-full text-xs">
          <i class="fa-solid fa-download"></i>
          Download Scene Video
        </a>
      `
      : '<div class="rounded-xl border border-brand-teal/30 bg-brand-teal/10 p-3 text-xs text-emerald-200">Mock video job completed. Configure OPENAI_API_KEY to generate a real MP4.</div>';

    resultContainer.innerHTML = `<div class="mt-3 space-y-3">${mediaHtml}</div>`;
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
    studioState.generatedOutlineId = null;
    studioState.promptPackage = null;
    studioState.generatedPromptPackageId = null;
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

    const connectedYouTube = getConnectedYouTubeAccount();
    setText('ig-status', accounts.some((item) => item.platform === 'instagram') ? '已绑定' : '待绑定');
    setText('yt-status', connectedYouTube ? '已连接' : (accounts.some((item) => item.platform === 'youtube') ? '已绑定' : '待绑定'));
    setText('tt-status', accounts.some((item) => item.platform === 'tiktok') ? '已绑定' : '待绑定');
    renderYouTubeConnection();
    renderYouTubePublishConnection();

    if (!accounts.length) {
      setHtml('social-accounts-list', '<p class="text-sm text-slate-500">No accounts linked yet.</p>');
      return;
    }

    const html = accounts.map((account) => `
      <div class="social-account-card flex items-center justify-between gap-4">
        <div>
          <div class="text-sm font-bold text-white capitalize">${escapeHtml(account.platform)}</div>
          <div class="text-xs text-slate-500">${escapeHtml(account.platform_account_name || account.account_handle || account.account_url || '')}</div>
          <div class="text-[10px] text-slate-600 mt-1">Status: ${escapeHtml(account.connection_status || 'manual')}</div>
        </div>
        <i class="fa-solid ${account.connection_status === 'connected' ? 'fa-circle-check text-brand-teal' : 'fa-link text-brand-purple'}"></i>
      </div>
    `).join('');

    setHtml('social-accounts-list', html);
  }

  function getConnectedYouTubeAccount() {
    return (studioState.socialAccounts || []).find((account) => account.platform === 'youtube' && account.connection_status === 'connected') || null;
  }

  function renderYouTubeConnection() {
    const account = getConnectedYouTubeAccount();
    const connectButton = $('youtube-connect-btn');
    const disconnectButton = $('youtube-disconnect-btn');
    if (connectButton) connectButton.classList.toggle('hidden', Boolean(account));
    if (disconnectButton) disconnectButton.classList.toggle('hidden', !account);

    if (account) {
      setHtml('youtube-account-summary', `
        <div class="flex items-start justify-between gap-3">
          <div>
            <div class="text-sm font-bold text-white">${escapeHtml(account.platform_account_name || account.account_handle || 'YouTube Channel')}</div>
            <div class="text-xs text-slate-500 mt-1">${escapeHtml(account.account_url || '')}</div>
            <div class="text-[10px] text-brand-teal mt-2">Connected${account.last_synced_at ? ` · ${escapeHtml(account.last_synced_at)}` : ''}</div>
          </div>
          <i class="fa-solid fa-circle-check text-brand-teal"></i>
        </div>
      `);
    } else {
      setText('youtube-account-summary', 'No connected YouTube account.');
    }
  }

  function renderYouTubePublishConnection() {
    const account = getConnectedYouTubeAccount();
    const statusText = account ? `Connected: ${account.platform_account_name || account.account_handle || 'YouTube'}` : 'Connect YouTube first';
    setText('youtube-publish-connection-status', statusText);
  }

  async function handleYouTubeConnect() {
    clearError('youtube-connect-error');
    clearSuccess('youtube-connect-message');
    const button = $('youtube-connect-btn');
    setButtonLoading(button, true, 'Connecting...');
    try {
      const response = await window.Api.connectYouTube();
      window.location.href = response.auth_url;
    } catch (error) {
      showError('youtube-connect-error', error.message || 'Could not start YouTube OAuth.');
      setButtonLoading(button, false);
    }
  }

  async function handleYouTubeDisconnect() {
    clearError('youtube-connect-error');
    clearSuccess('youtube-connect-message');
    const account = getConnectedYouTubeAccount();
    if (!account) return;

    const button = $('youtube-disconnect-btn');
    setButtonLoading(button, true, 'Disconnecting...');
    try {
      await window.Api.deleteSocialAccount(account.id);
      showSuccess('youtube-connect-message', 'YouTube account disconnected.');
      await loadSocialAccounts();
    } catch (error) {
      showError('youtube-connect-error', error.message || 'Failed to disconnect YouTube.');
    } finally {
      setButtonLoading(button, false);
    }
  }

  async function loadYouTubePublishingData() {
    if (!window.authState.isAuthenticated) return;
    try {
      const [assets, jobs] = await Promise.all([
        window.Api.listVideoAssets(),
        window.Api.listPublishingJobs()
      ]);
      studioState.videoAssets = assets || [];
      studioState.publishingJobs = jobs || [];
      renderVideoAssetOptions();
      renderPublishingJobs();
      renderYouTubePublishConnection();
    } catch (error) {
      console.warn('Failed to load YouTube publishing data.', error);
    }
  }

  function renderVideoAssetOptions() {
    const assets = studioState.videoAssets || [];
    if (!assets.length) {
      setHtml('youtube-video-asset', '<option value="">No generated video assets yet</option>');
      return;
    }

    setHtml('youtube-video-asset', assets.map((asset) => {
      const label = `#${asset.id} · Scene ${asset.scene_number || '-'} · ${asset.status || 'unknown'}${asset.file_path ? '' : ' · no file'}`;
      return `<option value="${Number(asset.id)}">${escapeHtml(label)}</option>`;
    }).join(''));
  }

  function renderPublishingJobs() {
    const jobs = studioState.publishingJobs || [];
    if (!jobs.length) {
      setHtml('publishing-jobs-list', '<p class="text-sm text-slate-500">No publishing jobs yet.</p>');
      return;
    }

    const html = jobs.map((job) => {
      const statusClass = job.status === 'success' ? 'text-brand-teal' : (job.status === 'failed' ? 'text-brand-pink' : 'text-brand-yellow');
      const link = job.provider_post_url
        ? `<a href="${escapeHtml(job.provider_post_url)}" target="_blank" rel="noopener" class="text-brand-purple hover:underline">Watch on YouTube</a>`
        : '';
      return `
        <div class="rounded-xl border border-brand-border bg-brand-dark/50 p-4">
          <div class="flex items-start justify-between gap-3">
            <div>
              <div class="text-sm font-bold text-white">${escapeHtml(job.title)}</div>
              <div class="text-xs ${statusClass} mt-1">${escapeHtml(job.status)} · ${escapeHtml(job.privacy_status)}</div>
              ${job.error_message ? `<div class="text-xs text-brand-pink mt-2">${escapeHtml(job.error_message)}</div>` : ''}
              ${link ? `<div class="text-xs mt-2">${link}</div>` : ''}
            </div>
            <span class="text-[10px] text-slate-600">#${escapeHtml(job.id)}</span>
          </div>
        </div>
      `;
    }).join('');
    setHtml('publishing-jobs-list', html);
  }

  async function handleYouTubePublish(event) {
    event.preventDefault();
    clearError('youtube-publish-error');
    clearSuccess('youtube-publish-success');

    const account = getConnectedYouTubeAccount();
    if (!account) {
      showError('youtube-publish-error', 'Please connect YouTube before publishing.');
      switchTab('social');
      return;
    }

    const form = event.currentTarget;
    const data = getFormData(form);
    const title = String(data.title || '').trim();
    const videoAssetId = Number(data.video_asset_id || 0);
    if (!videoAssetId) {
      showError('youtube-publish-error', 'Please choose a video asset.');
      return;
    }
    if (!title) {
      showError('youtube-publish-error', 'Title is required.');
      return;
    }

    const tags = String(data.tags || '')
      .split(',')
      .map((tag) => tag.trim())
      .filter(Boolean);
    const payload = {
      video_asset_id: videoAssetId,
      social_account_id: account.id,
      title,
      description: String(data.description || '').trim(),
      tags,
      privacy_status: String(data.privacy_status || 'private'),
      contains_synthetic_media: Boolean($('youtube-synthetic')?.checked)
    };

    const button = $('youtube-publish-submit-btn');
    setButtonLoading(button, true, 'Uploading...');
    try {
      const job = await window.Api.uploadYouTubeShort(payload);
      if (job.status === 'success' && job.provider_post_url) {
        showSuccess('youtube-publish-success', `Published successfully: ${job.provider_post_url}`);
      } else if (job.status === 'failed') {
        showError('youtube-publish-error', job.error_message || 'Publishing failed.');
      } else {
        showSuccess('youtube-publish-success', `Publishing job ${job.id} is ${job.status}.`);
      }
      await loadYouTubePublishingData();
    } catch (error) {
      showError('youtube-publish-error', error.message || 'Failed to upload YouTube Short.');
      await loadYouTubePublishingData();
    } finally {
      setButtonLoading(button, false);
    }
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

  function renderProfile(user) {
    if (!user) return;
    if ($('profile-username')) $('profile-username').value = user.username || '';
    if ($('profile-email')) $('profile-email').value = user.email || '';
    if ($('profile-full-name')) $('profile-full-name').value = user.full_name || '';
    if ($('profile-company-name')) $('profile-company-name').value = user.company_name || '';
    renderAvatar('profile-avatar-preview', user.avatar_url, user.display_name || user.username || 'U');

    const verifiedHtml = user.email_verified
      ? '<span class="text-brand-teal font-bold"><i class="fa-solid fa-circle-check mr-2"></i>Verified</span>'
      : '<span class="text-brand-yellow font-bold"><i class="fa-solid fa-triangle-exclamation mr-2"></i>Unverified</span>';
    setHtml('profile-verification-status', verifiedHtml);
    $('profile-resend-verification-btn')?.classList.toggle('hidden', Boolean(user.email_verified));

    setHtml('profile-account-info', `
      <div><span class="text-slate-500">Created:</span> ${escapeHtml(user.created_at || '-')}</div>
      <div><span class="text-slate-500">Last login:</span> ${escapeHtml(user.last_login_at || '-')}</div>
      <div><span class="text-slate-500">Role:</span> <span class="font-bold text-brand-purple">${escapeHtml(user.role || 'user')}</span></div>
    `);
  }

  async function loadProfile() {
    clearError('profile-error');
    clearSuccess('profile-success');
    try {
      const user = await window.Api.getProfile();
      window.authState.user = user;
      localStorage.setItem('current_user', JSON.stringify(user));
      renderProfile(user);
      hydrateUserInterface();
    } catch (error) {
      showError('profile-error', error.message || 'Failed to load profile.');
    }
  }

  async function handleProfileSubmit(event) {
    event.preventDefault();
    clearError('profile-error');
    clearSuccess('profile-success');

    const data = getFormData(event.currentTarget);
    const payload = {
      email: String(data.email || '').trim().toLowerCase(),
      username: String(data.username || '').trim(),
      full_name: String(data.full_name || '').trim() || null,
      company_name: String(data.company_name || '').trim() || null
    };

    if (!validateEmail(payload.email)) {
      showError('profile-error', 'Please enter a valid email address.');
      return;
    }

    const button = $('profile-submit-btn');
    setButtonLoading(button, true, 'Saving profile...');
    try {
      await window.Api.updateProfile(payload);
      const avatarFile = $('profile-avatar-file')?.files?.[0];
      if (avatarFile) {
        await window.Api.uploadAvatar(avatarFile);
        if ($('profile-avatar-file')) $('profile-avatar-file').value = '';
      }
      await refreshProfileState();
      showSuccess('profile-success', 'Profile saved.');
    } catch (error) {
      showError('profile-error', error.message || 'Failed to save profile.');
    } finally {
      setButtonLoading(button, false);
    }
  }

  async function handleAvatarUpload() {
    clearError('profile-error');
    clearSuccess('profile-success');
    const file = $('profile-avatar-file')?.files?.[0];
    if (!file) {
      showError('profile-error', 'Please choose an avatar image first.');
      return;
    }

    const button = $('profile-avatar-upload-btn');
    setButtonLoading(button, true, 'Uploading avatar...');
    try {
      await window.Api.uploadAvatar(file);
      if ($('profile-avatar-file')) $('profile-avatar-file').value = '';
      await refreshProfileState();
      showSuccess('profile-success', 'Avatar uploaded.');
    } catch (error) {
      showError('profile-error', error.message || 'Failed to upload avatar.');
    } finally {
      setButtonLoading(button, false);
    }
  }

  async function handleChangePassword(event) {
    event.preventDefault();
    clearError('password-error');
    clearSuccess('password-success');

    const form = event.currentTarget;
    const data = getFormData(form);
    const currentPassword = String(data.current_password || '');
    const newPassword = String(data.new_password || '');
    const confirm = String(data.new_password_confirm || '');

    if (!validatePassword(newPassword)) {
      showError('password-error', 'Password must be at least 8 characters and include uppercase, lowercase, and number.');
      return;
    }
    if (newPassword !== confirm) {
      showError('password-error', 'Password confirmation does not match.');
      return;
    }

    const button = $('change-password-submit-btn');
    setButtonLoading(button, true, 'Changing password...');
    try {
      const response = await window.Api.changePassword(currentPassword, newPassword, confirm);
      form.reset();
      showSuccess('password-success', response.message || 'Password changed.');
    } catch (error) {
      showError('password-error', error.message || 'Failed to change password.');
    } finally {
      setButtonLoading(button, false);
    }
  }

  async function handleResendVerification() {
    clearError('profile-error');
    clearSuccess('profile-success');
    try {
      const response = await window.Api.resendVerification();
      showSuccess('profile-success', response.message || 'Verification email sent.');
    } catch (error) {
      showError('profile-error', error.message || 'Failed to resend verification email.');
    }
  }

  function renderAdminRows(containerId, rows, formatter) {
    const html = (rows || []).map((row) => `<div class="admin-row">${formatter(row)}</div>`).join('');
    setHtml(containerId, html || '<div class="admin-row">No data yet.</div>');
  }

  function renderAdminMetrics(metrics) {
    const items = [
      ['Users', metrics.total_users],
      ['Verified', metrics.verified_users],
      ['Jobs', metrics.total_generation_jobs],
      ['Failed', metrics.failed_jobs],
      ['API Rows', metrics.total_api_usage_rows],
      ['Outlines', metrics.total_generated_outlines],
      ['Prompts', metrics.total_prompt_packages],
      ['Videos', metrics.total_video_jobs],
      ['Cost', `$${Number(metrics.estimated_total_cost || 0).toFixed(4)}`]
    ];
    setHtml('admin-metrics', items.map(([label, value]) => `
      <div class="metric-card"><span class="metric-label">${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong><small>Live backend data</small></div>
    `).join(''));
  }

  function renderAdminUserRow(userRow) {
    const isCurrentUser = Number(userRow.id) === Number(window.authState.user?.id);
    const activeLabel = userRow.is_active ? 'Disable' : 'Enable';
    const roleLabel = userRow.role === 'admin' ? 'Make User' : 'Make Admin';
    const verifiedButton = userRow.email_verified
      ? ''
      : `<button type="button" class="secondary-btn text-[10px] py-1 px-2" onclick="handleAdminUserAction(${Number(userRow.id)}, 'verify')">
          <i class="fa-solid fa-envelope-circle-check"></i><span>Verify</span>
        </button>`;

    return `
      <div class="flex items-start justify-between gap-3">
        <div>
          <strong>${escapeHtml(userRow.email)}</strong>${isCurrentUser ? ' <span class="text-[10px] text-brand-purple">(you)</span>' : ''}<br>
          ${escapeHtml(userRow.username)} · ${escapeHtml(userRow.role)} · ${userRow.email_verified ? 'verified' : 'unverified'} · ${userRow.is_active ? 'active' : 'inactive'}
        </div>
        <div class="flex flex-wrap justify-end gap-2">
          <button type="button" class="secondary-btn text-[10px] py-1 px-2" onclick="handleAdminUserAction(${Number(userRow.id)}, 'toggle_active')">
            <i class="fa-solid ${userRow.is_active ? 'fa-user-slash' : 'fa-user-check'}"></i><span>${activeLabel}</span>
          </button>
          <button type="button" class="secondary-btn text-[10px] py-1 px-2" onclick="handleAdminUserAction(${Number(userRow.id)}, 'toggle_role')">
            <i class="fa-solid fa-user-shield"></i><span>${roleLabel}</span>
          </button>
          ${verifiedButton}
        </div>
      </div>
    `;
  }

  async function handleAdminUserAction(userId, action) {
    clearError('admin-error');
    clearSuccess('admin-success');

    const users = await window.Api.listAdminUsers();
    const target = users.find((userRow) => Number(userRow.id) === Number(userId));
    if (!target) {
      showError('admin-error', 'User was not found.');
      return;
    }

    const payload = {};
    if (action === 'toggle_active') {
      if (Number(target.id) === Number(window.authState.user?.id) && target.is_active) {
        const confirmed = window.confirm('You are about to disable your own account. Continue?');
        if (!confirmed) return;
      }
      payload.is_active = !target.is_active;
    } else if (action === 'toggle_role') {
      payload.role = target.role === 'admin' ? 'user' : 'admin';
    } else if (action === 'verify') {
      payload.email_verified = true;
    } else {
      showError('admin-error', 'Unknown admin action.');
      return;
    }

    try {
      const updated = await window.Api.updateAdminUser(userId, payload);
      if (Number(updated.id) === Number(window.authState.user?.id)) {
        window.authState.user = updated;
        localStorage.setItem('current_user', JSON.stringify(updated));
      }
      showSuccess('admin-success', 'User updated.');
      await loadAdminDashboard();
    } catch (error) {
      showError('admin-error', error.message || 'Failed to update user.');
    }
  }

  async function loadAdminDashboard() {
    const user = window.authState.user || window.getCurrentUser?.();
    if (!user || user.role !== 'admin') {
      showError('admin-error', 'Admin access is required.');
      return;
    }

    clearError('admin-error');
    try {
      const [metrics, users, questionnaires, jobs, assets, usage, logs, prompts] = await Promise.all([
        window.Api.getAdminMetrics(),
        window.Api.listAdminUsers(),
        window.Api.listAdminQuestionnaires(),
        window.Api.listAdminGenerationJobs(),
        window.Api.listAdminVideoAssets(),
        window.Api.listAdminApiUsage(),
        window.Api.listAdminActionLogs(),
        window.Api.getSystemPrompts()
      ]);

      renderAdminMetrics(metrics);
      renderAdminRows('admin-users', users, renderAdminUserRow);
      renderAdminRows('admin-questionnaires', questionnaires, (item) => `<strong>${escapeHtml(item.brand_name || '-')}</strong><br>User ${escapeHtml(item.user_id)} · ${escapeHtml(item.video_style || '-')}`);
      renderAdminRows('admin-generation-jobs', jobs, (job) => `<strong>#${escapeHtml(job.id)} ${escapeHtml(job.job_type)}</strong><br>${escapeHtml(job.status)} · user ${escapeHtml(job.user_id)} · ${escapeHtml(job.provider)}`);
      renderAdminRows('admin-video-assets', assets, (asset) => `<strong>#${escapeHtml(asset.id)} ${escapeHtml(asset.status)}</strong><br>Job ${escapeHtml(asset.generation_job_id)} · ${escapeHtml(asset.model || '-')}`);
      renderAdminRows('admin-api-usage', usage, (item) => `<strong>${escapeHtml(item.provider)} ${escapeHtml(item.operation)}</strong><br>${escapeHtml(item.model)} · $${Number(item.estimated_cost || 0).toFixed(4)}`);
      renderAdminRows('admin-action-logs', logs, (item) => `<strong>${escapeHtml(item.action)}</strong><br>${escapeHtml(item.target_type || '-')} ${escapeHtml(item.target_id || '')} · admin ${escapeHtml(item.admin_user_id)}`);
      setHtml('admin-system-prompts', `
        <div class="admin-row"><strong>Outline</strong><br>${escapeHtml((prompts.outline_system_prompt || '').slice(0, 600))}</div>
        <div class="admin-row"><strong>Video Prompt</strong><br>${escapeHtml((prompts.video_prompt_system_prompt || '').slice(0, 600))}</div>
      `);
    } catch (error) {
      showError('admin-error', error.message || 'Failed to load admin dashboard.');
    }
  }

  async function initializeApp() {
    const params = new URLSearchParams(window.location.search);
    const resetToken = params.get('reset_token');
    const youtubeConnected = params.get('youtube_connected');
    if (resetToken) {
      window.clearAuth();
      showPage('page-auth');
      showResetPasswordForm(resetToken);
      return;
    }
    if (youtubeConnected) {
      studioState.pendingYouTubeStatus = youtubeConnected;
      params.delete('youtube_connected');
      const newQuery = params.toString();
      const newUrl = `${window.location.pathname}${newQuery ? `?${newQuery}` : ''}${window.location.hash || ''}`;
      window.history.replaceState({}, document.title, newUrl);
    }

    await window.initAuth();

    if (!window.authState.isAuthenticated) {
      showAuthPage();
      return;
    }

    await routeAfterAuth(false);
    if (studioState.pendingYouTubeStatus === 'success') {
      switchTab('social');
      showSuccess('youtube-connect-message', 'YouTube connected successfully.');
      studioState.pendingYouTubeStatus = null;
    } else if (studioState.pendingYouTubeStatus === 'failed') {
      switchTab('social');
      showError('youtube-connect-error', 'YouTube connection failed. Please try again.');
      studioState.pendingYouTubeStatus = null;
    }
  }

  function bindEvents() {
    $('login-form')?.addEventListener('submit', handleLogin);
    $('register-form')?.addEventListener('submit', handleRegister);
    $('forgot-password-form')?.addEventListener('submit', handleForgotPassword);
    $('reset-password-form')?.addEventListener('submit', handleResetPassword);
    $('questionnaire-form')?.addEventListener('submit', handleQuestionnaireSubmit);
    $('social-form')?.addEventListener('submit', handleSocialSubmit);
    $('youtube-publish-form')?.addEventListener('submit', handleYouTubePublish);
    $('profile-form')?.addEventListener('submit', handleProfileSubmit);
    $('change-password-form')?.addEventListener('submit', handleChangePassword);

    document.querySelectorAll('.questionnaire-field').forEach((field) => {
      field.addEventListener('input', updateQuestionnairePreview);
      field.addEventListener('change', updateQuestionnairePreview);
    });

    $('brand-logo-file')?.addEventListener('change', () => {
      const file = $('brand-logo-file')?.files?.[0];
      if (file) renderBrandLogoPreview(URL.createObjectURL(file));
      updateQuestionnairePreview();
    });

    $('profile-avatar-file')?.addEventListener('change', () => {
      const file = $('profile-avatar-file')?.files?.[0];
      if (file) renderAvatar('profile-avatar-preview', URL.createObjectURL(file), window.authState.user?.display_name || 'U');
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
  window.showForgotPasswordForm = showForgotPasswordForm;
  window.showResetPasswordForm = showResetPasswordForm;
  window.switchTab = switchTab;
  window.handleLogout = handleLogout;
  window.handleGenerateOutline = handleGenerateOutline;
  window.handleGeneratePrompts = handleGeneratePrompts;
  window.handleGenerateSceneVideo = handleGenerateSceneVideo;
  window.handleYouTubeConnect = handleYouTubeConnect;
  window.handleYouTubeDisconnect = handleYouTubeDisconnect;
  window.handleResendVerification = handleResendVerification;
  window.handleBrandLogoUpload = handleBrandLogoUpload;
  window.handleAvatarUpload = handleAvatarUpload;
  window.handleAdminUserAction = handleAdminUserAction;
  window.loadAdminDashboard = loadAdminDashboard;
  window.resetStudioState = resetStudioState;
})();
