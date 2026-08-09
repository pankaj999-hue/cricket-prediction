import { teamColor } from '../constants';

export default function Builder({
  teams, venues, league, season,
  teamA, teamB, venue,
  pitch, hint, predicting,
  onTeamA, onTeamB, onVenue, onPitch, onLeague, onPredict,
  builderRef,
}) {
  const aIdx = teams.indexOf(teamA);
  const bIdx = teams.indexOf(teamB);
  const vIdx = venues.indexOf(venue);
  const hintColor = hint && hint.kind === 'err' ? 'var(--pink-2)' : 'var(--text-dim)';

  return (
    <section className="builder" ref={builderRef}>
      <div className="section-eyebrow">// PREDICTOR</div>
      <h2 className="section-title">Call it yourself</h2>
      <div className="league-switch">
        <button type="button" className={'league-tab' + (league === 'CPL' ? ' active' : '')} data-league="CPL" data-season="2026" onClick={() => onLeague('CPL')}>
          CPL 2026
        </button>
        <button type="button" className={'league-tab' + (league === 'IPL' ? ' active' : '')} data-league="IPL" data-season="2026" onClick={() => onLeague('IPL')}>
          IPL 2026
        </button>
      </div>

      <div className="field-grid">
        <div className="team-card a">
          <div className="team-label">TEAM A</div>
          <select
            value={aIdx >= 0 ? aIdx : ''}
            onChange={(e) => onTeamA(teams[Number(e.target.value)])}
            aria-label="Team A"
          >
            {teams.map((t, i) => <option key={i} value={i}>{t}</option>)}
          </select>
          <div className="team-swatch">
            <span className="swatch" style={{ borderColor: `transparent transparent transparent ${aIdx >= 0 ? teamColor(aIdx) : 'var(--green)'}` }} />
            <span>{teamA || '—'}</span>
          </div>
        </div>
        <div className="vs-mark">VS</div>
        <div className="team-card b">
          <div className="team-label">TEAM B</div>
          <select
            value={bIdx >= 0 ? bIdx : ''}
            onChange={(e) => onTeamB(teams[Number(e.target.value)])}
            aria-label="Team B"
          >
            {teams.map((t, i) => <option key={i} value={i}>{t}</option>)}
          </select>
          <div className="team-swatch">
            <span className="swatch" style={{ borderColor: `transparent transparent transparent ${bIdx >= 0 ? teamColor(bIdx) : 'var(--pink-2)'}` }} />
            <span>{teamB || '—'}</span>
          </div>
        </div>
      </div>

      <div className="field-grid field-row2">
        <div className="team-card a">
          <div className="team-label">VENUE</div>
          <select
            className="venue-select"
            value={vIdx >= 0 ? vIdx : ''}
            onChange={(e) => onVenue(venues[Number(e.target.value)])}
            aria-label="Venue"
          >
            {venues.map((v, i) => <option key={i} value={i}>{v}</option>)}
          </select>
          <div className="team-swatch"><span>Neutral / auto-detected</span></div>
        </div>
        <div className="team-card b">
          <div className="team-label">PITCH TYPE (SOIL) — LIVE</div>
          <div className="pitch-pills">
            {['neutral', 'batting', 'bowling'].map((p) => (
              <button
                key={p}
                type="button"
                className={'pitch-pill' + (pitch === p ? ' active' : '')}
                data-pitch={p}
                onClick={() => onPitch(p)}
              >
                {p[0].toUpperCase() + p.slice(1)}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="predict-row">
        <button className="predict-btn" id="predictBtn" disabled={predicting} onClick={onPredict}>
          {predicting ? 'Calling it…' : 'Call the match'}
        </button>
      </div>
      <div className="hint" style={{ color: hintColor }}>{hint.text || ''}</div>
    </section>
  );
}