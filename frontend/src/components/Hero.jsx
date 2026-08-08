import { useRef } from 'react';

export default function Hero() {
  const videoRef = useRef(null);
  function hideVideo() {
    if (videoRef.current) videoRef.current.style.display = 'none';
  }
  return (
    <section className="hero">
      <video
        className="hero-video"
        ref={videoRef}
        autoPlay muted loop playsInline preload="auto"
        onError={hideVideo}
        onStalled={(e) => { if (e.currentTarget.readyState === 0) hideVideo(); }}
      >
        <source src="/assets/hero-action.mp4" type="video/mp4" />
      </video>
      <div className="hero-overlay" />
      <div className="trinetra" aria-hidden="true" />
      <div className="eyebrow">// THE ALL-SEEING EYE</div>
      <h1>Who wins<br />under the <span className="accent">lights?</span></h1>
      <p className="sub">Antaryami keeps three eyes on form, head-to-head and venue history — then calls the match before a ball is bowled.</p>
    </section>
  );
}