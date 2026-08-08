export default function Ticker({ teams }) {
  if (!teams || teams.length === 0) return null;
  const doubled = [];
  teams.forEach((t, i) => {
    const nxt = teams[(i + 1) % teams.length];
    doubled.push(
      <div className="ticker-item" key={'a' + i}>
        <span className="ticker-dot upcoming" />
        <span>{t} vs {nxt}</span>
        <span>ready to call</span>
      </div>
    );
  });
  teams.forEach((t, i) => {
    const nxt = teams[(i + 1) % teams.length];
    doubled.push(
      <div className="ticker-item" key={'b' + i} aria-hidden="true">
        <span className="ticker-dot upcoming" />
        <span>{t} vs {nxt}</span>
        <span>ready to call</span>
      </div>
    );
  });
  return (
    <div className="ticker-wrap">
      <div className="ticker-track">{doubled}</div>
    </div>
  );
}