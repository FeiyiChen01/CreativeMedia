(function () {
  const TOKEN_KEY = 'access_token';
  const USER_KEY = 'current_user';
  const QUESTIONNAIRE_KEY = 'questionnaire';

  window.authState = {
    isAuthenticated: false,
    user: null,
    token: null,
    questionnaire: null
  };

  function readJsonFromStorage(key) {
    try {
      const rawValue = localStorage.getItem(key);
      return rawValue ? JSON.parse(rawValue) : null;
    } catch (error) {
      console.warn(`Failed to parse localStorage key: ${key}`, error);
      localStorage.removeItem(key);
      return null;
    }
  }

  function writeJsonToStorage(key, value) {
    localStorage.setItem(key, JSON.stringify(value));
  }

  function decodeJwtPayload(token) {
    try {
      const payloadPart = token.split('.')[1];
      if (!payloadPart) return null;
      const base64 = payloadPart.replace(/-/g, '+').replace(/_/g, '/');
      const json = decodeURIComponent(
        atob(base64)
          .split('')
          .map((char) => `%${(`00${char.charCodeAt(0).toString(16)}`).slice(-2)}`)
          .join('')
      );
      return JSON.parse(json);
    } catch (error) {
      console.warn('Failed to decode JWT payload.', error);
      return null;
    }
  }

  function isTokenExpired(token) {
    const payload = decodeJwtPayload(token);
    if (!payload || !payload.exp) return false;
    const nowInSeconds = Math.floor(Date.now() / 1000);
    return payload.exp <= nowInSeconds;
  }

  function setToken(token, user) {
    window.authState.token = token;
    window.authState.user = user;
    window.authState.isAuthenticated = Boolean(token && user);
    localStorage.setItem(TOKEN_KEY, token);
    writeJsonToStorage(USER_KEY, user);
  }

  function getToken() {
    return window.authState.token || localStorage.getItem(TOKEN_KEY);
  }

  function setQuestionnaire(questionnaire) {
    window.authState.questionnaire = questionnaire || null;
    if (questionnaire) {
      writeJsonToStorage(QUESTIONNAIRE_KEY, questionnaire);
    } else {
      localStorage.removeItem(QUESTIONNAIRE_KEY);
    }
  }

  function getQuestionnaireFromStorage() {
    return readJsonFromStorage(QUESTIONNAIRE_KEY);
  }

  function clearAuth() {
    window.authState.isAuthenticated = false;
    window.authState.user = null;
    window.authState.token = null;
    window.authState.questionnaire = null;
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    localStorage.removeItem(QUESTIONNAIRE_KEY);
  }

  function getCurrentUser() {
    return window.authState.user || readJsonFromStorage(USER_KEY);
  }

  async function initAuth() {
    const storedToken = localStorage.getItem(TOKEN_KEY);
    const storedUser = readJsonFromStorage(USER_KEY);
    const storedQuestionnaire = getQuestionnaireFromStorage();

    if (!storedToken || !storedUser) {
      clearAuth();
      return window.authState;
    }

    if (isTokenExpired(storedToken)) {
      clearAuth();
      return window.authState;
    }

    window.authState.token = storedToken;
    window.authState.user = storedUser;
    window.authState.questionnaire = storedQuestionnaire;
    window.authState.isAuthenticated = true;

    if (window.Api && typeof window.Api.getCurrentUser === 'function') {
      try {
        const freshUser = await window.Api.getCurrentUser();
        window.authState.user = freshUser;
        writeJsonToStorage(USER_KEY, freshUser);
      } catch (error) {
        console.warn('Token validation failed during init.', error);
        clearAuth();
      }
    }

    return window.authState;
  }

  window.initAuth = initAuth;
  window.setToken = setToken;
  window.getToken = getToken;
  window.clearAuth = clearAuth;
  window.getCurrentUser = getCurrentUser;
  window.isTokenExpired = isTokenExpired;
  window.setQuestionnaire = setQuestionnaire;
  window.getQuestionnaireFromStorage = getQuestionnaireFromStorage;
})();
