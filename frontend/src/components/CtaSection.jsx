import { useState } from 'react';
import { useApi } from '../api';

export default function CtaSection() {
  const call = useApi();
  const [email, setEmail] = useState('');
  const [toast, setToast] = useState({ text: '', color: '' });

  async function handleSubscribe() {
    const value = email.trim();
    if (!value || !value.includes('@') || !value.includes('.')) {
      setToast({ text: '// enter a valid email address', color: 'var(--pink-2)' });
      return;
    }
    try {
      await call('/api/subscribe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: value, league: 'CPL' }),
      });
      setToast({ text: '// subscribed — toss alerts arrive by email', color: 'var(--green)' });
      setEmail('');
    } catch (e) {
      setToast({ text: `// ${e.message}`, color: 'var(--pink-2)' });
    }
  }

  return (
    <section className="cta-section">
      <div className="cta-card">
        <div className="cta-title">Never miss a call</div>
        <div className="cta-desc">Get predictions pushed to you 30 minutes before every match — form, head-to-head, venue and pitch signal, the full breakdown.</div>
        <div className="cta-form">
          <input
            className="cta-input"
            type="email"
            id="ctaEmail"
            value={email}
            placeholder="you@email.com"
            aria-label="Email address"
            onChange={(e) => setEmail(e.target.value)}
          />
          <button className="cta-submit" id="ctaBtn" onClick={handleSubscribe}>Subscribe</button>
        </div>
        <div className="cta-toast" id="ctaToast" style={{ color: toast.color }}>{toast.text}</div>
      </div>
    </section>
  );
}