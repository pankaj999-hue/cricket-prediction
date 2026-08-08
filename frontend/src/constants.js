/* ============================================================
   MATCHCALL — shared constants + derived helpers
   ============================================================ */

export const TEAM_COLOR_PALETTE = [
  '#C4F135', '#ED0B65', '#FF4D9D', '#F5D033', '#9B6BFF',
  '#3DFFB0', '#FF5C5C', '#5CC8FF', '#FF9E5C', '#E05CFF',
  '#5CFFE0', '#FFE05C',
];

// Per-league accuracy constants from validated backtests:
//   IPL: 86.7% call accuracy (High+Medium), 2026 + 2024/25 validation
//   CPL: 85.7% call accuracy (High+Medium), 2024/25 backtest
export const LEAGUE_ACCURACY = {
  IPL: { pct: 87, high: '39/45', medium: '40/47', noBet: '70 declined' },
  CPL: { pct: 86, high: '27/30', medium: '3/5',  noBet: '31 declined' },
};

export const DEBUT_VENUE = 'Arnos Vale Stadium, Kingstown';

// Showcase default picks per league.
export const DEFAULT_SELECTIONS = {
  IPL: {
    a: 'Royal Challengers Bengaluru',
    b: 'Chennai Super Kings',
    v: 'MA Chidambaram Stadium, Chepauk, Chennai',
  },
  CPL: {
    a: 'Guyana Amazon Warriors',
    b: 'Antigua and Barbuda Falcons',
    v: 'Providence Stadium, Georgetown',
  },
};

export const teamColor = (i) => TEAM_COLOR_PALETTE[i % TEAM_COLOR_PALETTE.length];

// Call accuracy on High+Medium across the validated backtest for a league.
export function accuracyStats(league) {
  const band = LEAGUE_ACCURACY[league] || LEAGUE_ACCURACY.IPL;
  const high = band.high.split('/').map(Number);
  const medium = band.medium.split('/').map(Number);
  const calls = [
    { label: 'High', correct: high[0], wrong: high[1] - high[0] },
    { label: 'Med', correct: medium[0], wrong: medium[1] - medium[0] },
  ];
  const totalCorrect = calls.reduce((s, c) => s + c.correct, 0);
  const total = calls.reduce((s, c) => s + c.correct + c.wrong, 0);
  const pct = total ? Math.round((totalCorrect / total) * 100) : 0;
  return { calls, pct, noBet: band.noBet };
}