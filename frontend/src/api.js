/* ============================================================
   MATCHCALL — API helper. fetchJSON with 401 handling:
   redirects to /login when the session is gone.
   ============================================================ */
import { useCallback } from 'react';
import { useAuth } from './auth';

export function useApi() {
  const auth = useAuth();

  return useCallback(async (url, options) => {
    const opts = auth
      ? auth.authedFetch(url, options)
      : (() => {
          const o = options || {};
          o.headers = Object.assign({}, o.headers || {});
          return fetch(url, o);
        })();
    const res = await opts;
    if (res.status === 401) {
      // authedFetch already redirected to /login when the session expired — we
      // deliberately do NOT redirect again here to avoid a double navigation.
      throw new Error('Session expired. Please sign in again.');
    }
    if (!res.ok) {
      const detail = (await res.json().catch(() => ({}))).detail || res.statusText;
      throw new Error(detail);
    }
    return res.json();
  }, [auth]);
}