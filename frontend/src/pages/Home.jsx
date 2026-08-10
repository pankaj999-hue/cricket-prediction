import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Nav from '../components/Nav';
import Ticker from '../components/Ticker';
import Hero from '../components/Hero';
import Spotlight from '../components/Spotlight';
import HowItWorks from '../components/HowItWorks';
import Builder from '../components/Builder';
import ResultPanel from '../components/ResultPanel';
import Leaderboard from '../components/Leaderboard';
import AccuracySection from '../components/AccuracySection';
import LogSection from '../components/LogSection';
import CtaSection from '../components/CtaSection';
import ChevronStrip from '../components/ChevronStrip';
import Footer from '../components/Footer';
import { useApi } from '../api';
import { DEFAULT_SELECTIONS, DEBUT_VENUE } from '../constants';

export default function Home() {
  const call = useApi();
  const navigate = useNavigate();

  const [engine, setEngine] = useState('connecting');
  const [league, setLeague] = useState('CPL');
  const [season, setSeason] = useState('2026');
  const [teams, setTeams] = useState([]);
  const [venues, setVenues] = useState([]);
  const [teamA, setTeamA] = useState('');
  const [teamB, setTeamB] = useState('');
  const [venue, setVenue] = useState('');
  const [pitch, setPitch] = useState('neutral');
  const [autoXi, setAutoXi] = useState(true);
  const [hint, setHint] = useState({ text: '', kind: '' });
  const [predicting, setPredicting] = useState(false);
  const [result, setResult] = useState(null);
  const [resultKey, setResultKey] = useState(0);
  const [leaderboard, setLeaderboard] = useState([]);
  const [lbError, setLbError] = useState('');
  const builderRef = useRef(null);
  const resultRef = useRef(null);

  const loadLeaderboard = useCallback(async (l, s) => {
    try {
      const data = await call(`/api/team-strength?league=${l}&season=${s}`);
      setLeaderboard(data.teams);
    } catch (e) {
      setLbError(e.message);
    }
  }, [call]);

  const loadData = useCallback(async (l, s) => {
    const [teamsData, venuesData] = await Promise.all([
      call(`/api/teams?league=${l}&season=${s}`),
      call(`/api/venues?league=${l}&season=${s}`),
    ]);
    setTeams(teamsData.teams);
    setVenues(venuesData.venues);
    const defaults = DEFAULT_SELECTIONS[l] || DEFAULT_SELECTIONS.IPL;
    setTeamA(defaults.a);
    setTeamB(defaults.b);
    setVenue(defaults.v);
    await loadLeaderboard(l, s);
  }, [call, loadLeaderboard]);

  // Boot: check engine + load initial data (loadData already calls /api/teams —
  // no separate health-check fetch that would double the request).
  useEffect(() => {
    (async () => {
      try {
        await loadData('CPL', '2026');
        setEngine('online');
      } catch (e) {
        setEngine('offline');
        setHint({ text: 'Could not load engine data: ' + e.message, kind: 'err' });
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Debut venue / team notice (CPL 2026) — don't clobber error hints.
  useEffect(() => {
    if (!teams.length || !venue) return;
    if (league === 'CPL' && venue === DEBUT_VENUE) {
      const isKingsmen = teamA === 'Jamaica Kingsmen' || teamB === 'Jamaica Kingsmen';
      const text = isKingsmen
        ? '// Debut alert: Jamaica Kingsmen\'s first-ever CPL match + Arnos Vale\'s first CPL game. No history — open call.'
        : '// Arnos Vale Stadium hosts its first-ever CPL match — neutral.';
      setHint((h) => (h.kind === 'err' ? h : { text, kind: 'info' }));
    } else {
      setHint((h) => (h.kind === 'info' ? { text: '', kind: '' } : h));
    }
  }, [venue, league, teamA, teamB, teams]);

  function handleLeague(l) {
    if (l === league) return;
    setLeague(l);
    setSeason('2026');
    setHint({ text: '// loading ' + l + ' 2026…', kind: 'info' });
    (async () => {
      try {
        await loadData(l, '2026');
        setHint({ text: '', kind: '' });
      } catch (e) {
        setHint({ text: 'Could not load ' + l + ' data: ' + e.message, kind: 'err' });
      }
    })();
  }

  async function handlePredict() {
    if (!teamA || !teamB || teamA === teamB) {
      setHint({ text: '// pick two different teams', kind: 'err' });
      return;
    }
    setHint({ text: '', kind: '' });
    setPredicting(true);
    try {
      const p = await call('/api/predict', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          team_a: teamA,
          team_b: teamB,
          venue,
          league,
          stage: 'League',
          pitch_type: pitch,
          auto_xi: autoXi,
        }),
      });
      setResult(p);
      setResultKey((k) => k + 1);
      if (resultRef.current) resultRef.current.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    } catch (e) {
      setHint({ text: 'Engine error: ' + e.message, kind: 'err' });
    } finally {
      setPredicting(false);
    }
  }

  function handleLoadLast() {
    if (result) {
      if (teams.includes(result.team_a)) setTeamA(result.team_a);
      if (teams.includes(result.team_b)) setTeamB(result.team_b);
    }
    if (builderRef.current) builderRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function handleNavigateLogin() {
    navigate('/login');
  }

  return (
    <>
      <ChevronStrip />
      <Nav status={engine} />
      <Ticker teams={teams} />
      <Hero />
      <Spotlight lastPred={result} onLoadLast={handleLoadLast} />
      <HowItWorks />
      <Builder
        teams={teams}
        venues={venues}
        league={league}
        season={season}
        teamA={teamA}
        teamB={teamB}
        venue={venue}
        pitch={pitch}
        autoXi={autoXi}
        hint={hint}
        predicting={predicting}
        onTeamA={setTeamA}
        onTeamB={setTeamB}
        onVenue={setVenue}
        onPitch={setPitch}
        onAutoXi={setAutoXi}
        onLeague={handleLeague}
        onPredict={handlePredict}
        builderRef={builderRef}
      />
      <ResultPanel result={result} show={!!result} animationKey={resultKey} resultRef={resultRef} />
      <Leaderboard teams={teams} rows={leaderboard} error={lbError} />
      <AccuracySection league={league} />
      <LogSection league={league} />
      <CtaSection />
      <ChevronStrip />
      <Footer />
    </>
  );
}