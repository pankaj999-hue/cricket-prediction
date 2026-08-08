import { teamColor } from '../constants';

export default function Leaderboard({ teams, rows, error }) {
  return (
    <section className="leaderboard-section">
      <div className="section-eyebrow">// TEAMS</div>
      <h2 className="section-title">Squads by strength</h2>
      <div className="lb-card">
        <div className="lb-row lb-head">
          <span>#</span><span>TEAM</span><span>SQUAD</span><span>STATS</span><span>RATING</span><span>BAND</span>
        </div>
        <div id="lbRows">
          {error ? (
            <div className="lb-row"><span>Could not load squad strength: {error}</span></div>
          ) : (
            rows.map((row, rank) => {
              const idx = teams.indexOf(row.team);
              const color = idx >= 0 ? teamColor(idx) : 'var(--text-dim)';
              const rating = row.rating;
              const nm = rating != null ? Math.round(rating) : '—';
              const width = rating != null ? Math.max(4, Math.min(100, rating)) : 0;
              return (
                <div className="lb-row" key={rank}>
                  <span className={'lb-rank' + (rank < 3 ? ' top' : '')}>{String(rank + 1).padStart(2, '0')}</span>
                  <span className="lb-name"><span className="lb-color-dot" style={{ background: color }} />{row.team}</span>
                  <span className="lb-stat">{row.players} pl</span>
                  <span className="lb-stat">{row.data} sd</span>
                  <span className="lb-bar-wrap-col" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <div className="lb-bar-wrap"><div className="lb-bar-fill" style={{ width: width + '%', background: color }} /></div>
                    <span className="lb-stat">{nm}%</span>
                  </span>
                  <span><span className="lb-form">squad strength</span></span>
                </div>
              );
            })
          )}
        </div>
      </div>
    </section>
  );
}