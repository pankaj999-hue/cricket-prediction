export default function HowItWorks() {
  return (
    <section className="how-section">
      <div className="section-eyebrow">// METHODOLOGY</div>
      <h2 className="section-title">Three signals,<br />one call</h2>
      <div className="steps-grid">
        <div className="step-card">
          <span className="step-num">01</span>
          <div className="step-icon">&#9889;</div>
          <div className="step-title">Current Form</div>
          <div className="step-desc">Player-level recent form weighted by recency — who is actually in touch, not just who has a famous name.</div>
        </div>
        <div className="step-card">
          <span className="step-num">02</span>
          <div className="step-icon">&#8644;</div>
          <div className="step-title">Head-to-Head</div>
          <div className="step-desc">Recent H2H between the two sides plus key player matchups (batter vs bowler records) across the last three seasons.</div>
        </div>
        <div className="step-card">
          <span className="step-num">03</span>
          <div className="step-icon">&#9878;</div>
          <div className="step-title">Venue &amp; Pitch</div>
          <div className="step-desc">Venue compatibility, venue specialists and the live pitch type — tell us if it&apos;s a batting or bowling friendly surface.</div>
        </div>
      </div>
    </section>
  );
}