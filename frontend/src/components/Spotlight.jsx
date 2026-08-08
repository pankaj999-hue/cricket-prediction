export default function Spotlight({ lastPred, onLoadLast }) {
  return (
    <section className="spotlight" id="spotlightSection">
      <div className="spotlight-card">
        <div className="spotlight-side a-side">
          <div className="spotlight-tag">TEAM A</div>
          <div className="spotlight-team">{lastPred ? lastPred.team_a : '—'}</div>
          <div className="spotlight-sub">{lastPred ? (lastPred.no_bet ? 'No Bet — too close' : 'Recommended') : 'Pick a side to load'}</div>
        </div>
        <div className="spotlight-center">
          <div className="spotlight-vs">VS</div>
          <div className="spotlight-when">
            <strong>MATCHDAY</strong>
            LIVE PREDICTION
          </div>
          <div className="spotlight-pct-mini">
            <div className="mini-bar g" style={{ width: lastPred ? `${Math.round(lastPred.team_a_score / 2)}px` : '40px' }} />
            <span className="mini-pct">{lastPred ? lastPred.team_a_score + '%' : '—'}</span>
            <span style={{ color: 'var(--text-dim)', fontSize: 11 }}>—</span>
            <span className="mini-pct">{lastPred ? lastPred.team_b_score + '%' : '—'}</span>
            <div className="mini-bar p" style={{ width: lastPred ? `${Math.round(lastPred.team_b_score / 2)}px` : '40px' }} />
          </div>
          <button className="spotlight-cta" id="spotCta" onClick={onLoadLast}>Load last prediction</button>
        </div>
        <div className="spotlight-side b-side">
          <div className="spotlight-tag">TEAM B</div>
          <div className="spotlight-team">{lastPred ? lastPred.team_b : '—'}</div>
          <div className="spotlight-sub">{lastPred ? `${lastPred.confidence} confidence` : 'Pick a side to load'}</div>
        </div>
      </div>
    </section>
  );
}