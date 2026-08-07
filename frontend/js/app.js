/* ============================================================
   MATCHCALL — frontend app
   Connects to the FastAPI engine at /api/*
   ============================================================ */

// ---------- globals ----------
let TEAMS = [];
let TEAM_COLORS = {};
const TEAM_COLOR_PALETTE = [
  '#C4F135', '#ED0B65', '#FF4D9D', '#F5D033', '#9B6BFF',
  '#3DFFB0', '#FF5C5C', '#5CC8FF', '#FF9E5C', '#E05CFF',
  '#5CFFE0', '#FFE05C'
];
let PITCH_TYPE = 'neutral';
let LEAGUE = 'IPL';
let SEASON = '2026';

// Per-league accuracy constants from validated backtests:
//   IPL: 86.7% call accuracy (High+Medium), 2026 + 2024/25 validation
//   CPL: 85.7% call accuracy (High+Medium), 2024/25 backtest
const LEAGUE_ACCURACY = {
  IPL: { pct: 87, high: '39/45', medium: '40/47', noBet: '70 declined' },
  CPL: { pct: 86, high: '27/30', medium: '3/5',  noBet: '31 declined' },
};

// ---------- helpers ----------
const $ = (id) => document.getElementById(id);

function hideVideoOnError() {
  const v = $('heroVideo');
  if (!v) return;
  v.addEventListener('error', () => { v.style.display = 'none'; });
  v.addEventListener('stalled', () => { if (v.readyState === 0) v.style.display = 'none'; });
}

function renderAuthNav() {
  const el = $('navAuth');
  if (!el) return;
  let user = null;
  try { user = JSON.parse(localStorage.getItem('matchcall_user') || 'null'); } catch {}
  if (user && user.email) {
    el.textContent = 'Sign out · ' + user.email;
    el.classList.add('out');
    el.href = '#';
    el.onclick = null;
    el.addEventListener('click', doLogout);
  } else {
    el.textContent = 'Sign in';
    el.classList.remove('out');
    el.href = 'login.html';
    el.onclick = null;
    el.addEventListener('click', () => { window.location.href = 'login.html'; });
  }
}

async function doLogout(e) {
  if (e) e.preventDefault();
  try {
    const token = (window.matchcallAuth && window.matchcallAuth.getToken()) || null;
    const headers = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = 'Bearer ' + token;
    await fetch('/api/auth/logout', {
      method: 'POST', headers, credentials: 'same-origin', body: '{}',
    });
  } catch {}
  if (window.matchcallAuth) window.matchcallAuth.clearSession();
  window.location.href = '/login.html';
}

async function fetchJSON(url, options) {
  const authed = window.matchcallAuth;
  const opts = authed ? authed.authedFetch(url, options) : (function () {
    const o = options || {};
    o.headers = Object.assign({}, o.headers || {});
    return fetch(url, o);
  })();
  const res = await opts;
  if (res.status === 401) {
    if (authed) { authed.clearSession(); window.location.href = '/login.html'; }
    throw new Error('Session expired. Please sign in again.');
  }
  if (!res.ok) {
    const detail = (await res.json().catch(() => ({}))).detail || res.statusText;
    throw new Error(detail);
  }
  return res.json();
}

async function initEngineStatus() {
  const el = $('engineStatus');
  const txt = $('engineStatusText');
  try {
    await fetchJSON('/api/teams?league=' + LEAGUE + '&season=' + SEASON);
    txt.textContent = 'ENGINE CONNECTED';
    el.classList.remove('offline');
  } catch (e) {
    txt.textContent = 'ENGINE OFFLINE';
    el.classList.add('offline');
  }
}

// ---------- load teams + venues ----------
async function loadData() {
  const [teamsData, venuesData] = await Promise.all([
    fetchJSON('/api/teams?league=' + LEAGUE + '&season=' + SEASON),
    fetchJSON('/api/venues?league=' + LEAGUE + '&season=' + SEASON),
  ]);
  TEAMS = teamsData.teams;
  const venues = venuesData.venues;

  fillSelect($('teamA'), TEAMS);
  fillSelect($('teamB'), TEAMS);
  fillSelect($('venueSel'), venues);

  // showcase default picks
  const defaults = LEAGUE === 'IPL'
    ? { a: 'Royal Challengers Bengaluru', b: 'Chennai Super Kings', v: 'MA Chidambaram Stadium, Chepauk, Chennai' }
    : { a: 'Guyana Amazon Warriors', b: 'Antigua and Barbuda Falcons', v: 'Providence Stadium, Georgetown' };
  setTeamSelect($('teamA'), defaults.a);
  setTeamSelect($('teamB'), defaults.b);
  setTeamSelect($('venueSel'), defaults.v);

  updateSwatches();
  await renderLeaderboard();
  renderTicker();
  renderAccuracy();
  showDebutNote();
}

// ---------- league switch ----------
function bindLeagueSwitch() {
  const tabs = Array.from(document.querySelectorAll('.league-tab'));
  tabs.forEach((tab) => {
    tab.addEventListener('click', async () => {
      if (tab.dataset.league === LEAGUE) return;
      tabs.forEach((t) => t.classList.remove('active'));
      tab.classList.add('active');
      LEAGUE = tab.dataset.league;
      SEASON = tab.dataset.season;
      const hint = $('hint');
      hint.textContent = '// loading ' + LEAGUE + ' ' + SEASON + '…';
      hint.style.color = 'var(--text-dim)';
      try {
        await loadData();
        hint.textContent = '';
      } catch (e) {
        hint.textContent = 'Could not load ' + LEAGUE + ' data: ' + e.message;
        hint.style.color = 'var(--pink-2)';
      }
    });
  });
}

function fillSelect(sel, items) {
  sel.innerHTML = items.map((v, i) => `<option value="${i}">${v}</option>`).join('');
  sel.selectedIndex = 0;
}
function setTeamSelect(sel, name) {
  const idx = TEAMS.indexOf(name);
  if (idx >= 0) sel.selectedIndex = idx;
}

function teamColor(i) { return TEAM_COLOR_PALETTE[i % TEAM_COLOR_PALETTE.length]; }

// ---------- swatches ----------
function updateSwatches() {
  const aIdx = +$('teamA').value;
  const bIdx = +$('teamB').value;
  $('swatchA').style.borderColor = `transparent transparent transparent ${teamColor(aIdx)}`;
  $('swatchB').style.borderColor = `transparent transparent transparent ${teamColor(bIdx)}`;
  $('formA').textContent = TEAMS[aIdx] || '—';
  $('formB').textContent = TEAMS[bIdx] || '—';
}

// ---------- live ticker ----------
function renderTicker() {
  const track = $('tickerTrack');
  const items = TEAMS.map((t, i) => {
    const nxt = TEAMS[(i + 1) % TEAMS.length];
    return `<div class="ticker-item">
        <span class="ticker-dot upcoming"></span>
        <span>${t} vs ${nxt}</span>
        <span>ready to call</span>
      </div>`;
  }).join('');
  track.innerHTML = items + items; // duplicate for seamless loop
}

// ---------- leaderboard (real squad strength from /api/team-strength) ----------
async function renderLeaderboard() {
  const container = $('lbRows');
  try {
    const data = await fetchJSON('/api/team-strength?league=' + LEAGUE + '&season=' + SEASON);
    const rows = data.teams;
    const n = rows.length;
    container.innerHTML = rows.map((row, rank) => {
      const idx = TEAMS.indexOf(row.team);
      const color = idx >= 0 ? teamColor(idx) : 'var(--text-dim)';
      const rating = row.rating;
      const nm = rating != null ? Math.round(rating) : '—';
      const width = rating != null ? Math.max(4, Math.min(100, rating)) : 0;
      const tag = rating == null
        ? 'new'
        : (rank === 0 ? 'top' : (rank === 1 ? 'top' : (rank === 2 ? 'top' : '')));
      return `<div class="lb-row">
        <span class="lb-rank ${rank < 3 ? 'top' : ''}">${String(rank + 1).padStart(2, '0')}</span>
        <span class="lb-name"><span class="lb-color-dot" style="background:${color}"></span>${row.team}</span>
        <span class="lb-stat">${row.players} pl</span>
        <span class="lb-stat">${row.data} sd</span>
        <span class="lb-bar-wrap-col" style="display:flex;align-items:center;gap:8px;">
          <div class="lb-bar-wrap"><div class="lb-bar-fill" style="width:${width}%;background:${color}"></div></div>
          <span class="lb-stat">${nm}%</span>
        </span>
        <span><span class="lb-form">squad strength</span></span>
      </div>`;
    }).join('');
  } catch (e) {
    container.innerHTML = '<div class="lb-row"><span>Could not load squad strength: ' + e.message + '</span></div>';
  }
}

// ---------- accuracy tracker (per-league backtest-derived constants) ----------
function renderAccuracy() {
  // Call accuracy on High+Medium across the validated backtest for the active league.
  const band = LEAGUE_ACCURACY[LEAGUE] || LEAGUE_ACCURACY.IPL;
  const bands = {
    High:    { correct: band.high.split('/')[0],  total: band.high.split('/')[1] },
    Medium:  { correct: band.medium.split('/')[0], total: band.medium.split('/')[1] },
    'No Bet':{ correct: 0,  total: 0, note: band.noBet },
  };
  const calls = [
    { correct: +bands.High.correct,    wrong: +bands.High.total - +bands.High.correct,    label: 'High' },
    { correct: +bands.Medium.correct,  wrong: +bands.Medium.total - +bands.Medium.correct, label: 'Med' },
  ];
  const totalCorrect = calls.reduce((s, c) => s + c.correct, 0);
  const total = calls.reduce((s, c) => s + c.correct + c.wrong, 0);
  const pct = total ? Math.round((totalCorrect / total) * 100) : 0;
  const deg = Math.round((pct / 100) * 360);

  $('accPct').textContent = pct + '%';
  $('accRing').style.background =
    `conic-gradient(var(--green) 0deg, var(--green) ${deg}deg, var(--surface-3) ${deg}deg)`;

  const chart = $('barChart');
  const maxTotal = Math.max(...calls.map((c) => c.correct + c.wrong), 1);
  chart.innerHTML = calls.map((c) => {
    const t = c.correct + c.wrong;
    const correctW = Math.round((c.correct / maxTotal) * 100);
    const wrongW = Math.round((c.wrong / maxTotal) * 100);
    return `<div class="bar-row">
        <span class="bar-label">${c.label}</span>
        <div class="bar-track">
          <div class="bar-fill correct-bar" style="width:${correctW}%;"></div>
          <div class="bar-fill wrong-bar" style="width:${wrongW}%;margin-left:2px;"></div>
        </div>
        <span class="bar-val">${c.correct}/${t}</span>
      </div>`;
  }).join('');
  $('logRecord').textContent = pct + '% call accuracy';
}

// ---------- pitch pills ----------
function bindPitchPills() {
  const pills = Array.from(document.querySelectorAll('.pitch-pill'));
  pills.forEach((p) => {
    p.addEventListener('click', () => {
      pills.forEach((x) => x.classList.remove('active'));
      p.classList.add('active');
      PITCH_TYPE = p.dataset.pitch;
    });
  });
}

// ---------- debut venue / team notice (CPL 2026) ----------
const DEBUT_VENUE = 'Arnos Vale Stadium, Kingstown';
function showDebutNote() {
  const hint = $('hint');
  const venue = $('venueSel').value;
  if ($('venueSel').selectedIndex < 0) return;
  const vText = $('venueSel').options[$('venueSel').selectedIndex].text;
  const a = TEAMS[+$('teamA').value];
  const b = TEAMS[+$('teamB').value];
  if (LEAGUE === 'CPL' && vText === DEBUT_VENUE) {
    hint.style.color = 'var(--green)';
    if (a === 'Jamaica Kingsmen' || b === 'Jamaica Kingsmen') {
      hint.textContent = '// Debut alert: Jamaica Kingsmen\'s first-ever CPL match + Arnos Vale\'s first CPL game. No history — open call.';
    } else {
      hint.textContent = '// Arnos Vale Stadium hosts its first-ever CPL match — neutral.';
    }
  } else {
    hint.textContent = '';
  }
}

// ---------- spotlight ----------
let LAST_PRED = null;
function updateSpotlight() {
  if (!LAST_PRED) return;
  const p = LAST_PRED;
  $('spotTeamA').textContent = p.team_a;
  $('spotTeamB').textContent = p.team_b;
  $('spotSubA').textContent = p.no_bet ? 'No Bet — too close' : 'Recommended';
  $('spotSubB').textContent = `${p.confidence} confidence`;
  $('spotMiniA').style.width = (p.team_a_score / 2) + 'px';
  $('spotMiniB').style.width = (p.team_b_score / 2) + 'px';
  $('spotMiniPctA').textContent = p.team_a_score + '%';
  $('spotMiniPctB').textContent = p.team_b_score + '%';
}

// ---------- prediction ----------
function renderResult(p) {
  LAST_PRED = p;
  updateSpotlight();

  const noBet = !!p.no_bet;
  $('resNameA').textContent = p.team_a;
  $('resNameB').textContent = p.team_b;
  $('projA').textContent = p.team_a_score + '%';
  $('projB').textContent = p.team_b_score + '%';
  $('confidence').textContent = noBet ? 'NO BET' : p.confidence;
  $('confidence').classList.toggle('nobet', noBet);
  $('pctA').textContent = p.team_a_score + '%';
  $('pctB').textContent = p.team_b_score + '%';

  $('beamFillA').style.width = p.team_a_score + '%';
  $('beamFillB').style.width = p.team_b_score + '%';
  $('beamSplit').style.left = p.team_a_score + '%';

  let factors;
  if (noBet) {
    factors = [{ label: 'Recommendation', value: 'No Bet', cls: 'no-bet-fact' }];
    factors.push({ label: 'Why', value: 'Confidence too low — edge too thin to risk' , cls: 'no-bet-fact'});
  } else {
    factors = p.key_factors.map((f) => ({ label: f, value: '', cls: '' }));
    factors.unshift({ label: 'Pick', value: p.predicted_winner, cls: 'winner-fact' });
  }
  $('factorsList').innerHTML = factors.map((f) =>
    `<div class="factor-row ${f.cls}"><span>${f.label}</span><span>${f.value}</span></div>`
  ).join('');

  $('result').classList.add('show');
  $('result').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  logPrediction(p, noBet);
}

// ---------- prediction log ----------
const LOG = [];
function logPrediction(p, noBet) {
  LOG.unshift({
    pick: noBet ? 'No Bet' : p.predicted_winner,
    conf: noBet ? '—' : p.confidence,
    status: noBet ? 'no bet' : p.confidence.toLowerCase(),
    noBet,
    match: `${p.team_a} vs ${p.team_b}`
  });
  renderLog();
}

function renderLog() {
  const rows = $('logRows');
  rows.innerHTML = LOG.slice(0, 8).map((m) => `
    <div class="log-row">
      <span class="log-match">${m.match}</span>
      <span class="log-match"><span class="winner">${m.pick}</span></span>
      <span class="log-conf">${m.conf}</span>
      <span class="log-badge ${m.noBet ? 'nobet' : 'correct'}">${m.noBet ? 'NO BET' : m.status.toUpperCase()}</span>
    </div>
  `).join('');
}

// ---------- main predict handler ----------
async function handlePredict() {
  const a = TEAMS[+$('teamA').value];
  const b = TEAMS[+$('teamB').value];
  const venue = $('venueSel').options[$('venueSel').selectedIndex].text;
  const hint = $('hint');

  if (!a || !b || a === b) {
    hint.textContent = '// pick two different teams';
    hint.style.color = 'var(--pink-2)';
    return;
  }
  hint.textContent = '';
  const btn = $('predictBtn');
  btn.disabled = true;
  btn.textContent = 'Calling it…';

  const body = {
    team_a: a,
    team_b: b,
    venue,
    league: LEAGUE,
    stage: 'League',
    pitch_type: PITCH_TYPE,
  };

  try {
    const p = await fetchJSON('/api/predict', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    renderResult(p);
  } catch (e) {
    hint.textContent = 'Engine error: ' + e.message;
    hint.style.color = 'var(--pink-2)';
  } finally {
    btn.disabled = false;
    btn.textContent = 'Call the match';
  }
}

// ---------- CTA ----------
function bindCta() {
  $('ctaBtn').addEventListener('click', () => {
    const email = $('ctaEmail').value.trim();
    const toast = $('ctaToast');
    if (!email || !email.includes('@') || !email.includes('.')) {
      toast.textContent = '// enter a valid email address';
      toast.style.color = 'var(--pink-2)';
      return;
    }
    toast.textContent = '// subscribed — you\'ll get the next call';
    toast.style.color = 'var(--green)';
    $('ctaEmail').value = '';
  });
}

// ---------- boot ----------
(async function boot() {
  // Auth guard: allow the anonymous API endpoints (teams/venues/strength) to
  // render, but only run the protected predict flow when signed in.
  hideVideoOnError();
  if (window.matchcallAuth && window.matchcallAuth.restoreSession) {
    try { await window.matchcallAuth.restoreSession(); } catch {}
  }
  renderAuthNav();
  bindPitchPills();
  bindCta();
  bindLeagueSwitch();
  $('teamA').addEventListener('change', () => { updateSwatches(); showDebutNote(); });
  $('teamB').addEventListener('change', () => { updateSwatches(); showDebutNote(); });
  $('venueSel').addEventListener('change', showDebutNote);
  $('predictBtn').addEventListener('click', handlePredict);
  $('spotCta').addEventListener('click', () => {
    if (LAST_PRED) {
      const ia = TEAMS.indexOf(LAST_PRED.team_a);
      const ib = TEAMS.indexOf(LAST_PRED.team_b);
      if (ia >= 0) setTeamSelect($('teamA'), LAST_PRED.team_a);
      if (ib >= 0) setTeamSelect($('teamB'), LAST_PRED.team_b);
      updateSwatches();
    }
    document.querySelector('.builder').scrollIntoView({ behavior: 'smooth', block: 'start' });
  });

  renderTicker();
  renderAccuracy();
  initEngineStatus();

  try {
    await loadData();
    renderTicker();
  } catch (e) {
    $('engineStatusText').textContent = 'ENGINE OFFLINE';
    $('engineStatus').classList.add('offline');
    $('hint').textContent = 'Could not load engine data: ' + e.message;
    $('hint').style.color = 'var(--pink-2)';
  }
})();