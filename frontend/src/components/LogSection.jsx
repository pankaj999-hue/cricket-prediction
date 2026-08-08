import { accuracyStats } from '../constants';

export default function LogSection({ logs, league }) {
  const { pct } = accuracyStats(league);
  return (
    <section className="log-section">
      <div className="log-heading">
        <h2>Recent calls</h2>
        <div className="log-record">Call accuracy · <b id="logRecord">{pct}% call accuracy</b></div>
      </div>
      <div className="log-card">
        <div className="log-row log-head">
          <span>MATCH</span><span>PICK</span><span>CONFIDENCE</span><span>STATUS</span>
        </div>
        <div id="logRows">
          {logs.length === 0 ? null : logs.map((m, i) => (
            <div className="log-row" key={i}>
              <span className="log-match">{m.match}</span>
              <span className="log-match"><span className="winner">{m.pick}</span></span>
              <span className="log-conf">{m.conf}</span>
              <span className={'log-badge ' + (m.noBet ? 'nobet' : 'correct')}>{m.noBet ? 'NO BET' : m.status.toUpperCase()}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}