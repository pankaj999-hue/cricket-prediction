/* ============================================================
   MATCHCALL — auth context (HttpOnly refresh-cookie flow)
   Port of the vanilla auth.js:
   - Access token lives in memory, mirrored to sessionStorage so it
     survives a refresh within this tab.
   - Refresh token lives ONLY in an HttpOnly cookie set by the server,
     so JS never sees it. Sessions survive browser restarts via cookie.
   Exposed to the tree via useAuth().
   ============================================================ */
import { createContext, useCallback, useContext, useEffect, useState } from 'react';

const AUTH_USER_KEY = 'matchcall_user';
const SESSION_AT_KEY = 'matchcall_at';

function readUser() {
  try { return JSON.parse(localStorage.getItem(AUTH_USER_KEY) || 'null'); }
  catch { return null; }
}

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(readUser);
  const [restored, setRestored] = useState(false);

  const getToken = useCallback(() => sessionStorage.getItem(SESSION_AT_KEY), []);

  const setAccessToken = useCallback((tok) => {
    if (tok) sessionStorage.setItem(SESSION_AT_KEY, tok);
    else sessionStorage.removeItem(SESSION_AT_KEY);
  }, []);

  const setSession = useCallback((data) => {
    if (data.access_token) setAccessToken(data.access_token);
    if (data.user) {
      setUser(data.user);
      localStorage.setItem(AUTH_USER_KEY, JSON.stringify(data.user));
    }
  }, [setAccessToken]);

  const clearSession = useCallback(() => {
    setAccessToken(null);
    setUser(null);
    localStorage.removeItem(AUTH_USER_KEY);
  }, [setAccessToken]);

  // Use credentials so the browser sends/stores the HttpOnly refresh cookie.
  const cookieFetch = useCallback((url, options) => {
    const opts = options || {};
    opts.credentials = opts.credentials || 'same-origin';
    return fetch(url, opts);
  }, []);

  // Ask the server to issue a new access token from the refresh cookie.
  const refreshSession = useCallback(async () => {
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
    } catch { return false; }
  }, [cookieFetch, setSession]);

  // Generic authed fetch: attaches the access token, and on 401 tries one
  // silent refresh (via cookie) before giving up.
  const authedFetch = useCallback(async (url, options) => {
    const opts = options || {};
    opts.headers = Object.assign({}, opts.headers || {});
    opts.credentials = opts.credentials || 'same-origin';
    const token = getToken();
    if (token) opts.headers['Authorization'] = 'Bearer ' + token;

    let res = await fetch(url, opts);
    if (res.status === 401) {
      const refreshed = await refreshSession();
      if (refreshed) {
        opts.headers['Authorization'] = 'Bearer ' + getToken();
        res = await fetch(url, opts);
      } else {
        clearSession();
        window.location.href = '/login';
      }
    }
    return res;
  }, [getToken, refreshSession, clearSession]);

  // Boot-restore: if we have no access token but might have a refresh cookie,
  // try to restore the session once on mount.
  useEffect(() => {
    (async () => {
      if (!getToken()) await refreshSession();
      setRestored(true);
    })();
  }, [getToken, refreshSession]);

  return (
    <AuthContext.Provider value={{
      user, restored,
      getToken, getUser: () => user,
      setSession, clearSession, refreshSession, authedFetch, cookieFetch,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}