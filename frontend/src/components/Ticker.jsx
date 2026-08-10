import { useEffect, useState } from 'react';
import { useApi } from '../api';

export default function Ticker({ teams }) {
  const call = useApi();
  const [match, setMatch] = useState(null);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const data = await call('/api/ticker');
        if (alive) setMatch(data.match);
      } catch (err) {
        /* keep last known value on failure */
      }
    };
    load();
    const id = setInterval(load, 60000);
    return () => { alive = false; clearInterval(id); };
  }, [call]);

  const entries = [];
  if (match && match.team_a && match.team_b) {
    entries.push({
      dot: 'upcoming',
      first: `Next match ${match.start_ist || '—'}`,
      second: `${match.team_a} vs ${match.team_b}${match.venue ? ` @ ${match.venue}` : ''}`,
    });
    if (match.state && String(match.state).toLowerCase() === 'live') {
      entries.push({ dot: 'live', first: 'Match is LIVE', second: 'watch for toss + team lines' });
    }
    if (match.toss_winner) {
      entries.push({
        dot: 'toss',
        first: `${match.toss_winner} won the toss`,
        second: `chose ${match.toss_decision || 'batting first'}`,
      });
    }
    if (match.playing_xi && Object.keys(match.playing_xi).length) {
      for (const t of [match.team_a, match.team_b]) {
        const x = match.playing_xi[t];
        if (x && x.length) {
          entries.push({ dot: 'xi', first: `${t} XI`, second: x.join(', ') });
        }
      }
      if (!match.toss_winner) {
        entries.push({
          dot: 'accent',
          first: 'Teams announced → prediction is live',
          second: 'check the pick below',
        });
      }
    }
    if (match.prediction) {
      const p = match.prediction;
      if (p.no_bet) {
        entries.push({ dot: 'accent', first: 'Pick: No Bet', second: 'matchup too close to call' });
      } else {
        const conf = p.confidence || 'Medium';
        entries.push({ dot: 'pick', first: `Pick: ${p.predicted_winner}`, second: `${conf} confidence` });
      }
    }
  }
  if (!entries.length) {
    entries.push({
      dot: 'upcoming',
      first: 'When teams announce their XI → predictions get more accurate',
      second: teams && teams.length ? `${teams.length} teams loaded` : 'waiting for teams',
    });
  }

  const items = Array.from({ length: 12 }, (_, i) => {
    const e = entries[i % entries.length];
    return (
      <div className="ticker-item" key={i}>
        <span className={`ticker-dot ${e.dot}`} />
        <span className="ticker-first">{e.first}</span>
        <span className="ticker-second">{e.second}</span>
      </div>
    );
  });

  return (
    <div className="ticker-wrap">
      <div className="ticker-track">{items}</div>
    </div>
  );
}