export default function Ticker({ teams }) {
  const announcement = 'When teams announce their XI → predictions get more accurate';
  const items = Array.from({ length: 12 }, (_, i) => (
    <div className="ticker-item" key={i}>
      <span className="ticker-dot upcoming" />
      <span>{announcement}</span>
      <span>{teams && teams.length ? `${teams.length} teams loaded` : 'waiting for teams'}</span>
    </div>
  ));
  return (
    <div className="ticker-wrap">
      <div className="ticker-track">{items}</div>
    </div>
  );
}