import { useEffect, useRef, useState } from 'react';
import Nav from '../components/Nav';
import ChevronStrip from '../components/ChevronStrip';
import Footer from '../components/Footer';
import { useApi } from '../api';

export default function Admin() {
  const call = useApi();
  const [text, setText] = useState('');
  const [matchId, setMatchId] = useState('');
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState({ text: '', ok: false });
  const [result, setResult] = useState(null);
  const [recent, setRecent] = useState([]);
  const fileRef = useRef(null);

  const loadRecent = async () => {
    try {
      const data = await call('/api/admin/matches?limit=10');
      setRecent(data.matches || []);
    } catch {}
  };

  useEffect(() => {
    loadRecent();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleFile(e) {
    const file = e.target.files && e.target.files[0];
    if (!file) return;
    try {
      const txt = await file.text();
      JSON.parse(txt); // validate before pasting into the box
      setText(txt);
    } catch {
      setMsg({ text: 'Selected file is not valid JSON.', ok: false });
    }
    e.target.value = '';
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setMsg({ text: '', ok: false });
    setResult(null);
    if (!text.trim()) {
      setMsg({ text: 'Paste a Cricsheet match JSON (or upload a .json file) first.', ok: false });
      return;
    }
    let parsed;
    try {
      parsed = JSON.parse(text);
    } catch {
      setMsg({ text: 'The pasted text is not valid JSON.', ok: false });
      return;
    }
    setBusy(true);
    try {
      const body = { json: parsed };
      if (matchId.trim()) body.match_id = matchId.trim();
      const data = await call('/api/admin/ingest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      setResult(data);
      if (data.inserted) {
        setMsg({ text: `Match loaded — ${data.deliveries} deliveries, ${data.players} players.`, ok: true });
        setText('');
        setMatchId('');
      } else {
        setMsg({ text: `Not loaded: ${data.reason || 'already in the DB'}.`, ok: false });
      }
      loadRecent();
    } catch (err) {
      setMsg({ text: err.message || 'Load failed.', ok: false });
    } finally {
      setBusy(false);
    }
  }

  async function handleRefresh() {
    setBusy(true);
    try {
      await call('/api/admin/refresh', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
      setMsg({ text: 'Aggregation tables rebuilt.', ok: true });
    } catch (err) {
      setMsg({ text: err.message || 'Refresh failed.', ok: false });
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <ChevronStrip />
      <Nav status="online" />
      <section className="auth-hero">
        <div className="auth-card" style={{ width: 760, maxWidth: '92vw' }}>
          <div className="auth-eyebrow">// ADMIN ONLY</div>
          <h1 className="auth-title">Load match data</h1>
          <p className="auth-sub">Paste or upload a full Cricsheet match JSON (CPL). It is inserted into the DB and the prediction tables are rebuilt automatically.</p>

          <form className="auth-form" onSubmit={handleSubmit}>
            <label className="auth-field">
              <span>Match id (optional — leave blank to auto-derive)</span>
              <input type="text" value={matchId} onChange={(e) => setMatchId(e.target.value)} placeholder="e.g. 154315" autoComplete="off" />
            </label>
            <label className="auth-field">
              <span>Match JSON</span>
              <input type="file" ref={fileRef} accept=".json,application/json" onChange={handleFile} />
              <textarea
                rows="14"
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder='{ "info": { ... }, "innings": [...] }'
                style={{ width: '100%', fontFamily: 'monospace', fontSize: 12, resize: 'vertical', background: 'rgba(255,255,255,0.04)', color: 'var(--text)', border: '1px solid rgba(255,255,255,0.15)', borderRadius: 8, padding: 10 }}
              />
            </label>
            <div className="auth-buttons" style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
              <button type="submit" className="auth-btn" disabled={busy}>
                {busy ? 'Loading…' : 'Load match'}
              </button>
              <button type="button" className="auth-btn" style={{ background: 'transparent', border: '1px solid var(--text-dim)' }} onClick={handleRefresh} disabled={busy}>
                Rebuild aggregation tables
              </button>
            </div>
          </form>

          <div className={'auth-msg' + (msg.ok ? ' ok' : '')}>{msg.text}</div>

          {result && (
            <div style={{ marginTop: 16, fontSize: 14 }}>
              {result.inserted ? (
                <div><strong>{result.teams && result.teams.join(' vs ')}</strong> — {result.date}, {result.venue}.<br />
                  {result.deliveries} deliveries, {result.players} players. Match id: <code>{result.match_id}</code></div>
              ) : (
                <div>Already present ({result.reason}). No changes made.</div>
              )}
            </div>
          )}

          <div style={{ marginTop: 24, fontSize: 14 }}>
            <div className="auth-eyebrow" style={{ marginBottom: 8 }}>RECENTLY LOADED</div>
            {recent.length === 0 ? (
              <div className="auth-sub">No CPL matches in the DB yet.</div>
            ) : (
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                <tbody>
                  {recent.map((m) => (
                    <tr key={m.match_id} style={{ borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
                      <td style={{ padding: '6px 8px' }}>{m.date}</td>
                      <td style={{ padding: '6px 8px' }}>{m.team_a} vs {m.team_b}</td>
                      <td style={{ padding: '6px 8px' }}>{m.venue}</td>
                      <td style={{ padding: '6px 8px' }}><code>{m.match_id}</code></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </section>
      <ChevronStrip />
      <Footer />
    </>
  );
}
