import { useEffect, useState } from 'react';
import { accuracyStats } from '../constants';
import { useApi } from '../api';

const toRow = (r) => {
  if (r.no_bet) {
    return { key: `s-${r.match_id}`, match: r.match, pick: 'No Bet', conf: '—', badge: 'nobet', label: 'NO BET' };
  }
  if (r.is_correct === true) {
    return { key: `s-${r.match_id}`, match: r.match, pick: r.pick, conf: r.confidence, badge: 'correct', label: 'WIN' };
  }
  if (r.is_correct === false) {
    return { key: `s-${r.match_id}`, match: r.match, pick: r.pick, conf: r.confidence, badge: 'wrong', label: 'LOSS' };
  }
  return { key: `s-${r.match_id}`, match: r.match, pick: r.pick, conf: r.confidence, badge: 'nobet', label: 'IN PLAY' };
};

export default function LogSection({ league }) {
  const call = useApi();
  const [records, setRecords] = useState([]);
  const [live, setLive] = useState(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const data = await call('/api/toss-records?limit=8');
        if (!alive) return;
        setRecords((data.records || []).map(toRow));
        if (data.accuracy && data.accuracy.calls > 0) setLive(data.accuracy);
      } catch (e) {
        if (alive) setRecords([]);
      }
    })();
    return () => { alive = false; };
  }, [call, league]);

  const staticStats = accuracyStats(league);
  const displayPct = live ? live.pct : staticStats.pct;
  const rows = records;

  return (
    <section className="log-section">
      <div className="log-heading">
        <h2>Recent calls</h2>
        <div className="log-record">Call accuracy · <b id="logRecord">{displayPct}% call accuracy</b></div>
      </div>
      <div className="log-card">
        <div className="log-row log-head">
          <span>MATCH</span><span>PICK</span><span>CONFIDENCE</span><span>STATUS</span>
        </div>
        <div id="logRows">
          {rows.length === 0 ? null : rows.map((m) => (
            <div className="log-row" key={m.key}>
              <span className="log-match">{m.match}</span>
              <span className="log-match"><span className="winner">{m.pick}</span></span>
              <span className="log-conf">{m.conf}</span>
              <span className={'log-badge ' + m.badge}>{m.label}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
