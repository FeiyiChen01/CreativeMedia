(function () {
  const API_BASE_URL = window.API_BASE_URL || window.location.origin || 'http://localhost:8000';

  function normalizeEndpoint(endpoint) {
    return endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  }

  function getAuthHeaders(requireAuth) {
    const headers = {
      'Content-Type': 'application/json'
    };

    if (requireAuth) {
      const token = window.getToken ? window.getToken() : localStorage.getItem('access_token');
      if (token) {
        headers.Authorization = `Bearer ${token}`;
      }
    }

    return headers;
  }

  async function parseResponseBody(response) {
    const contentType = response.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      return response.json();
    }
    const text = await response.text();
    return text ? { detail: text } : null;
  }

  function getErrorMessage(errorBody, fallbackMessage) {
    if (!errorBody) return fallbackMessage;
    if (typeof errorBody === 'string') return errorBody;
    if (typeof errorBody.detail === 'string') return errorBody.detail;
    if (Array.isArray(errorBody.detail)) return errorBody.detail.map((item) => item.msg || item.type).join(', ');
    if (typeof errorBody.message === 'string') return errorBody.message;
    return fallbackMessage;
  }

  async function apiFetch(endpoint, options = {}, requireAuth = true) {
    const url = `${API_BASE_URL}${normalizeEndpoint(endpoint)}`;
    const response = await fetch(url, {
      ...options,
      headers: {
        ...getAuthHeaders(requireAuth),
        ...(options.headers || {})
      }
    });

    const body = await parseResponseBody(response);

    if (!response.ok) {
      if (response.status === 401) {
        if (window.clearAuth) window.clearAuth();
        if (window.showAuthPage) window.showAuthPage();
      }

      const error = new Error(getErrorMessage(body, `Request failed with status ${response.status}`));
      error.status = response.status;
      error.body = body;
      throw error;
    }

    return body;
  }

  async function tryEndpoints(endpoints, options, requireAuth = true) {
    let lastError = null;

    for (const endpoint of endpoints) {
      try {
        return await apiFetch(endpoint, options, requireAuth);
      } catch (error) {
        lastError = error;
        if (error.status !== 404 && error.status !== 405) {
          throw error;
        }
      }
    }

    throw lastError || new Error('No endpoint matched the request.');
  }

  async function register(email, username, password, passwordConfirm) {
    return apiFetch('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify({
        email,
        username,
        password,
        password_confirm: passwordConfirm
      })
    }, false);
  }

  async function login(email, password) {
    return apiFetch('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password })
    }, false);
  }

  async function logout() {
    return apiFetch('/api/auth/logout', {
      method: 'POST',
      body: JSON.stringify({})
    }, true);
  }

  async function getCurrentUser() {
    return apiFetch('/api/auth/me', { method: 'GET' }, true);
  }

  async function resendVerification() {
    return apiFetch('/api/auth/resend-verification', {
      method: 'POST',
      body: JSON.stringify({})
    }, true);
  }

  async function forgotPassword(email) {
    return apiFetch('/api/auth/forgot-password', {
      method: 'POST',
      body: JSON.stringify({ email })
    }, false);
  }

  async function resetPassword(token, newPassword, newPasswordConfirm) {
    return apiFetch('/api/auth/reset-password', {
      method: 'POST',
      body: JSON.stringify({
        token,
        new_password: newPassword,
        new_password_confirm: newPasswordConfirm
      })
    }, false);
  }

  async function getProfile() {
    return apiFetch('/api/profile', { method: 'GET' }, true);
  }

  async function updateProfile(profileData) {
    return apiFetch('/api/profile', {
      method: 'PATCH',
      body: JSON.stringify(profileData)
    }, true);
  }

  async function changePassword(currentPassword, newPassword, newPasswordConfirm) {
    return apiFetch('/api/profile/change-password', {
      method: 'POST',
      body: JSON.stringify({
        current_password: currentPassword,
        new_password: newPassword,
        new_password_confirm: newPasswordConfirm
      })
    }, true);
  }

  async function saveQuestionnaire(questionnaireData) {
    return tryEndpoints([
      '/api/questionnaire',
      '/api/questionnaires'
    ], {
      method: 'POST',
      body: JSON.stringify(questionnaireData)
    }, true);
  }

  async function getQuestionnaire() {
    return tryEndpoints([
      '/api/questionnaire',
      '/api/questionnaires/me',
      '/api/questionnaires'
    ], { method: 'GET' }, true);
  }

  async function listSocialAccounts() {
    return apiFetch('/api/social-accounts', { method: 'GET' }, true);
  }

  async function addSocialAccount(accountData) {
    return apiFetch('/api/social-accounts', {
      method: 'POST',
      body: JSON.stringify(accountData)
    }, true);
  }

  async function generateOutline(questionnairePayload) {
    return apiFetch('/api/generate-outline', {
      method: 'POST',
      body: JSON.stringify({ questionnaire: questionnairePayload })
    }, true);
  }

  async function generatePrompts(questionnairePayload, outline, targetTool = 'sora-2') {
    return apiFetch('/api/generate-prompts', {
      method: 'POST',
      body: JSON.stringify({
        questionnaire: questionnairePayload,
        outline,
        target_tool: targetTool
      })
    }, true);
  }

  async function generateSceneVideo(promptEn, durationSeconds = 4) {
    return apiFetch('/api/video-jobs', {
      method: 'POST',
      body: JSON.stringify({
        prompt_en: promptEn,
        duration_seconds: durationSeconds
      })
    }, true);
  }

  async function getVideoJob(jobId) {
    return apiFetch(`/api/video-jobs/${jobId}`, { method: 'GET' }, true);
  }

  async function getAdminMetrics() {
    return apiFetch('/api/admin/metrics', { method: 'GET' }, true);
  }

  async function listAdminUsers() {
    return apiFetch('/api/admin/users', { method: 'GET' }, true);
  }

  async function listAdminQuestionnaires() {
    return apiFetch('/api/admin/questionnaires', { method: 'GET' }, true);
  }

  async function listAdminGenerationJobs() {
    return apiFetch('/api/admin/generation-jobs', { method: 'GET' }, true);
  }

  async function listAdminVideoAssets() {
    return apiFetch('/api/admin/video-assets', { method: 'GET' }, true);
  }

  async function listAdminApiUsage() {
    return apiFetch('/api/admin/api-usage', { method: 'GET' }, true);
  }

  async function listAdminActionLogs() {
    return apiFetch('/api/admin/action-logs', { method: 'GET' }, true);
  }

  async function getSystemPrompts() {
    return apiFetch('/api/system-prompts', { method: 'GET' }, true);
  }

  window.Api = {
    apiFetch,
    register,
    login,
    logout,
    getCurrentUser,
    resendVerification,
    forgotPassword,
    resetPassword,
    getProfile,
    updateProfile,
    changePassword,
    saveQuestionnaire,
    getQuestionnaire,
    listSocialAccounts,
    addSocialAccount,
    generateOutline,
    generatePrompts,
    generateSceneVideo,
    getVideoJob,
    getAdminMetrics,
    listAdminUsers,
    listAdminQuestionnaires,
    listAdminGenerationJobs,
    listAdminVideoAssets,
    listAdminApiUsage,
    listAdminActionLogs,
    getSystemPrompts
  };
})();
