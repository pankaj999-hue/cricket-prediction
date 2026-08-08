import { accuracyStats } from '../constants';

export default function AccuracySection({ league }) {
  const { calls, pct } = accuracyStats(league);
  const deg = Math.round((pct / 100) * 360);
  const maxTotal = Math.max(...calls.map((c) => c.correct + c.wrong), 1);

  return (
    <section className="accuracy-section">
      <div className="section-eyebrow">// TRACK RECORD</div>
      <h2 className="section-title">Model accuracy</h2>
      <div className="acc-grid">
        <div className="acc-big">
          <div className="acc-ring-wrap">
            <div
              className="acc-ring"
              id="accRing"
              style={{ background: `conic-gradient(var(--green) 0deg, var(--green) ${deg}deg, var(--surface-3) ${deg}deg)` }}
            >
              <div className="acc-ring-inner" id="accPct">{pct}%</div>
            </div>
          </div>
          <div className="acc-label">CALL ACCURACY (HIGH + MEDIUM)</div>
          <div className="acc-sublabel">Predictions where the recommended team went on to win. Low-confidence games are declined as &quot;No Bet&quot;.</div>
        </div>
        <div className="acc-chart">
          <div className="acc-chart-title">BY CONFIDENCE BAND</div>
          <div className="bar-chart" id="barChart">
            {calls.map((c, i) => {
              const t = c.correct + c.wrong;
              const correctW = Math.round((c.correct / maxTotal) * 100);
              const wrongW = Math.round((c.wrong / maxTotal) * 100);
              return (
                <div className="bar-row" key={i}>
                  <span className="bar-label">{c.label}</span>
                  <div className="bar-track">
                    <div className="bar-fill correct-bar" style={{ width: correctW + '%' }} />
                    <div className="bar-fill wrong-bar" style={{ width: wrongW + '%', marginLeft: 2 }} />
                  </div>
                  <span className="bar-val">{c.correct}/{t}</span>
                </div>
              );
            })}
          </div>
          <div className="acc-legend">
            <span><span className="acc-legend-dot" style={{ background: 'var(--green)' }} />Correct</span>
            <span><span className="acc-legend-dot" style={{ background: 'var(--pink-2)' }} />Missed</span>
          </div>
        </div>
      </div>
    </section>
  );
}