/* ============================================================
   MATCHCALL — auth (HttpOnly refresh-cookie flow)
   - Access token is kept in memory (short-lived, not persisted).
   - Refresh token lives ONLY in an HttpOnly cookie set by the server,
     so JS never sees it. Sessions survive browser restarts via the cookie.
   Exposes a small API on window.matchcallAuth (no global collisions).
   ============================================================ */

(() => {
  const AUTH_USER_KEY = 'matchcall_user';

  let accessToken = null;

  const $ = (id) => document.getElementById(id);

  // The access token is held in memory; it is also mirrored to sessionStorage
  // so it survives a page refresh within this tab without a round-trip.
  const SESSION_AT_KEY = 'matchcall_at';
  function restoreAccess() {
    accessToken = accessToken || sessionStorage.getItem(SESSION_AT_KEY);
    return accessToken;
  }
  function setAccessToken(tok) {
    accessToken = tok || null;
    if (tok) sessionStorage.setItem(SESSION_AT_KEY, tok);
    else sessionStorage.removeItem(SESSION_AT_KEY);
  }

  function getToken() { return restoreAccess(); }
  function getUser() {
    try { return JSON.parse(localStorage.getItem(AUTH_USER_KEY) || 'null'); }
    catch { return null; }
  }

  function setSession(data) {
    if (data.access_token) setAccessToken(data.access_token);
    if (data.user) localStorage.setItem(AUTH_USER_KEY, JSON.stringify(data.user));
  }
  function clearSession() {
    setAccessToken(null);
    localStorage.removeItem(AUTH_USER_KEY);
  }

  // Use credentials so the browser sends/stores the HttpOnly refresh cookie.
  function cookieFetch(url, options) {
    const opts = options || {};
    opts.credentials = opts.credentials || 'same-origin';
    return fetch(url, opts);
  }

  // Ask the server to issue a new access token from the refresh cookie.
  // Returns true when the token was refreshed, false otherwise.
  // Ask the server to issue a new access token from the refresh cookie.
  // Returns true when the token was refreshed, false otherwise.
  async function refreshSession() {
    try {
      const res = await cookieFetch('/api/auth/refresh', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: '{}',
      });
      if (!res.ok) return false;
      const data = await res.json();
      setSession(data);
      return true;
    } catch {
      return false;
    }
  }

  // Generic authed fetch: attaches the access token, and on 401 tries one
  // silent refresh (via cookie) before giving up.
  async function authedFetch(url, options) {
    const opts = options || {};
    opts.headers = Object.assign({}, opts.headers || {});
    opts.credentials = opts.credentials || 'same-origin';
    const token = restoreAccess();
    if (token) opts.headers['Authorization'] = 'Bearer ' + token;

    let res = await fetch(url, opts);
    if (res.status === 401) {
      const refreshed = await refreshSession();
      if (refreshed) {
        opts.headers['Authorization'] = 'Bearer ' + restoreAccess();
        res = await fetch(url, opts);
      } else {
        clearSession();
        window.location.href = '/login.html';
      }
    }
    return res;
  }

  // Boot-restore: if we have no access token but might have a refresh cookie,
  // try to restore the session. Returns true if a session is now active.
  async function restoreSession() {
    if (restoreAccess()) return true;
    const ok = await refreshSession();
    return ok;
  }

  let mode = 'login';

  function setMode(m) {
    mode = m;
    $('authTitle').textContent = m === 'login' ? 'Welcome back' : 'Create your account';
    $('authSub').textContent = m === 'login'
      ? 'Sign in to open the prediction engine.'
      : 'Register to start calling matches.';
    $('nameReq').style.display = m === 'login' ? 'none' : 'inline';
    $('authName').required = m === 'register';
    $('authBtn').textContent = m === 'login' ? 'Sign in' : 'Create account';
    $('authPassword').autocomplete = m === 'login' ? 'current-password' : 'new-password';
    document.querySelectorAll('.auth-tab').forEach((t) =>
      t.classList.toggle('active', t.dataset.mode === m)
    );
  }

  function showMsg(text, ok) {
    const el = $('authMsg');
    el.textContent = text || '';
    el.classList.toggle('ok', !!ok);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    const email = $('authEmail').value.trim();
    const password = $('authPassword').value;
    const name = $('authName').value.trim();
    showMsg('');

    if (!email || !email.includes('@') || !email.includes('.')) {
      showMsg('Enter a valid email address.');
      return;
    }
    if (password.length < 6) {
      showMsg('Password must be at least 6 characters.');
      return;
    }

    const btn = $('authBtn');
    btn.disabled = true;
    btn.textContent = 'Please wait…';

    try {
      const endpoint = mode === 'login' ? '/api/auth/login' : '/api/auth/register';
      const body = mode === 'login'
        ? { email, password }
        : { email, password, name };

      const res = await cookieFetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || res.statusText);
      }

      setSession(data);
      window.location.href = '/';
    } catch (err) {
      showMsg(err.message || 'Something went wrong. Try again.');
    } finally {
      btn.disabled = false;
      btn.textContent = mode === 'login' ? 'Sign in' : 'Create account';
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    // Signed in and landed on the login page? Go straight to the app.
    if (getUser() && window.location.pathname.indexOf('login.html') !== -1) {
      window.location.href = '/';
      return;
    }
    // No auth form on this page — auth.js is being used as a helper only.
    if (!document.getElementById('authForm')) return;

    document.querySelectorAll('.auth-tab').forEach((t) =>
      t.addEventListener('click', () => setMode(t.dataset.mode))
    );
    $('authForm').addEventListener('submit', handleSubmit);
    setMode('login');
    restoreSession(); // if a refresh cookie exists, we're still signed in
  });

  window.matchcallAuth = {
    getToken, getUser,
    setSession, clearSession, refreshSession, authedFetch, restoreSession,
  };
})();