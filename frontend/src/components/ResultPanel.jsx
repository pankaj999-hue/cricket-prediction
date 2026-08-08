export default function ResultPanel({ result, show, animationKey, resultRef }) {
  const noBet = !!(result && result.no_bet);
  const aScore = result ? result.team_a_score : 50;
  const bScore = result ? result.team_b_score : 50;

  let factors;
  if (!result) {
    factors = null;
  } else if (noBet) {
    factors = [
      { label: 'Recommendation', value: 'No Bet', cls: 'no-bet-fact' },
      { label: 'Why', value: 'Confidence too low — edge too thin to risk', cls: 'no-bet-fact' },
    ];
  } else {
    factors = (result.key_factors || []).map((f) => ({ label: f, value: '', cls: '' }));
    factors.unshift({ label: 'Pick', value: result.predicted_winner, cls: 'winner-fact' });
  }

  return (
    <section className={'result' + (show ? ' show' : '')} key={animationKey} ref={resultRef} id="result">
      <div className="beam-card">
        <div className="beam-title">WIN PROBABILITY</div>
        <div className="beam-names">
          <span className="a-name" id="resNameA">{result ? result.team_a : 'TEAM A'}</span>
          <span className="b-name" id="resNameB">{result ? result.team_b : 'TEAM B'}</span>
        </div>
        <div className="beam-track">
          <div className="beam-fill-a" id="beamFillA" style={{ width: aScore + '%' }} />
          <div className="beam-fill-b" id="beamFillB" style={{ width: bScore + '%' }} />
          <div className="beam-split" id="beamSplit" style={{ left: aScore + '%' }} />
          <div className="beam-pct pct-a" id="pctA">{aScore}%</div>
          <div className="beam-pct pct-b" id="pctB">{bScore}%</div>
        </div>
        <div className="stat-grid">
          <div className="stat-box">
            <div className="stat-label">WIN % (A)</div>
            <div className="stat-value" id="projA">{result ? aScore + '%' : '—'}</div>
          </div>
          <div className="stat-box">
            <div className="stat-label">WIN % (B)</div>
            <div className="stat-value" id="projB">{result ? bScore + '%' : '—'}</div>
          </div>
          <div className="stat-box">
            <div className="stat-label">CONFIDENCE</div>
            <div className={'stat-value' + (noBet ? ' nobet' : '')} id="confidence">
              {result ? (noBet ? 'NO BET' : result.confidence) : '—'}
            </div>
          </div>
        </div>
        {factors && (
          <div className="factors">
            <div className="factors-title">KEY FACTORS</div>
            <div id="factorsList">
              {factors.map((f, i) => (
                <div className={'factor-row ' + f.cls} key={i}>
                  <span>{f.label}</span>
                  <span>{f.value}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}