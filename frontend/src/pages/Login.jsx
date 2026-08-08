import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../auth';
import ChevronStrip from '../components/ChevronStrip';
import Footer from '../components/Footer';

export default function Login() {
  const navigate = useNavigate();
  const { user, restored, cookieFetch, setSession } = useAuth();
  const [mode, setMode] = useState('login');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [msg, setMsg] = useState({ text: '', ok: false });
  const [busy, setBusy] = useState(false);

  // Already signed in (via refresh cookie)? Go straight to the app.
  useEffect(() => {
    if (restored && user) navigate('/', { replace: true });
  }, [restored, user, navigate]);

  async function handleSubmit(e) {
    e.preventDefault();
    const eml = email.trim();
    setMsg({ text: '', ok: false });
    if (!eml || !eml.includes('@') || !eml.includes('.')) {
      setMsg({ text: 'Enter a valid email address.', ok: false });
      return;
    }
    if (password.length < 6) {
      setMsg({ text: 'Password must be at least 6 characters.', ok: false });
      return;
    }
    setBusy(true);
    try {
      const endpoint = mode === 'login' ? '/api/auth/login' : '/api/auth/register';
      const body = mode === 'login'
        ? { email: eml, password }
        : { email: eml, password, name: name.trim() };
      const res = await cookieFetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || res.statusText);
      setSession(data);
      navigate('/', { replace: true });
    } catch (err) {
      setMsg({ text: err.message || 'Something went wrong. Try again.', ok: false });
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <ChevronStrip />
      <nav>
        <div className="logo"><span className="logo-chev" />ANTARYAMI</div>
      </nav>
      <section className="auth-hero">
        <div className="auth-card">
          <div className="auth-eyebrow">// SECURE ACCESS</div>
          <h1 className="auth-title" id="authTitle">{mode === 'login' ? 'Welcome back' : 'Create your account'}</h1>
          <p className="auth-sub" id="authSub">
            {mode === 'login' ? 'Sign in to open the prediction engine.' : 'Register to start calling matches.'}
          </p>

          <div className="auth-tabs">
            <button type="button" className={'auth-tab' + (mode === 'login' ? ' active' : '')} data-mode="login" onClick={() => setMode('login')}>Sign in</button>
            <button type="button" className={'auth-tab' + (mode === 'register' ? ' active' : '')} data-mode="register" onClick={() => setMode('register')}>Create account</button>
          </div>

          <form className="auth-form" id="authForm" onSubmit={handleSubmit} noValidate>
            <label className="auth-field">
              <span>Name{mode === 'register' && <em className="auth-req"> (optional)</em>}</span>
              <input type="text" id="authName" value={name} onChange={(e) => setName(e.target.value)} placeholder="Your name" autoComplete="name" />
            </label>
            <label className="auth-field">
              <span>Email</span>
              <input type="email" id="authEmail" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@email.com" autoComplete="email" required />
            </label>
            <label className="auth-field">
              <span>Password</span>
              <input type="password" id="authPassword" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} required />
            </label>
            <div className={'auth-msg' + (msg.ok ? ' ok' : '')} id="authMsg">{msg.text}</div>
            <button type="submit" className="auth-btn" id="authBtn" disabled={busy}>
              {busy ? 'Please wait…' : (mode === 'login' ? 'Sign in' : 'Create account')}
            </button>
          </form>

          <div className="auth-hint">Rate-limited to protect your account.<br />Predictions are limited to 20 per minute.</div>
        </div>
      </section>
      <ChevronStrip />
      <Footer />
    </>
  );
}