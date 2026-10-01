import { useEffect, useState } from 'react';
import { Activity, BarChart3, FlaskConical, LayoutGrid, Network, Plane } from 'lucide-react';
import { api } from './api';
import Fleet from './pages/Fleet';
import LiveTwin from './pages/LiveTwin';
import FaultLab from './pages/FaultLab';
import Validation from './pages/Validation';
import Architecture from './pages/Architecture';
import Background from './components/Background';
import BootScreen from './components/BootScreen';

const PAGES = [
  { id: 'fleet', label: 'Fleet Command', icon: LayoutGrid },
  { id: 'twin', label: 'Twin Replay', icon: Activity },
  { id: 'lab', label: 'Fault Injection Lab', icon: FlaskConical },
  { id: 'validation', label: 'Model Validation', icon: BarChart3 },
  { id: 'architecture', label: 'How it works', icon: Network },
];

// page + selected aircraft live in the URL hash so refresh/back keep your place
function readHash() {
  const [page, sel] = window.location.hash.replace('#/', '').split('/');
  return { page: PAGES.some((p) => p.id === page) ? page : 'fleet', sel: sel || null };
}

export default function App() {
  const [{ page, sel }, setNav] = useState(readHash);
  const [fleet, setFleet] = useState(null);
  const [results, setResults] = useState(null);
  const [meta, setMeta] = useState(null);
  const [error, setError] = useState(null);
  // Show the start-up sequence once per browser session (demo polish); later
  // reloads go straight to the page.
  const [booted, setBooted] = useState(() => {
    try { return sessionStorage.getItem('aerotwin-booted') === '1'; } catch { return true; }
  });

  useEffect(() => {
    if (booted) return undefined;
    const id = setTimeout(() => {
      setBooted(true);
      try { sessionStorage.setItem('aerotwin-booted', '1'); } catch { /* storage unavailable */ }
    }, 2400);
    return () => clearTimeout(id);
  }, [booted]);

  useEffect(() => {
    api.fleet().then(setFleet).catch((e) => setError(e.message));
    api.results().then(setResults).catch(() => {});
    api.meta().then(setMeta).catch(() => {});
    const onHash = () => setNav(readHash());
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  const go = (p, s = null) => {
    window.location.hash = `#/${p}${s ? `/${s}` : ''}`;
    window.scrollTo(0, 0);
  };

  let content;
  if (error) {
    content = (
      <div className="loading">
        <div>
          <div style={{ color: 'var(--crit)', fontWeight: 700, fontSize: 18 }}>Cannot reach the AeroTwin backend</div>
          <div className="muted" style={{ marginTop: 8 }}>Start it with <span className="mono">./run.sh</span> (or <span className="mono">python3 -m uvicorn backend.main:app --port 8000</span>).</div>
          <div className="dim mono" style={{ marginTop: 8, fontSize: 12 }}>{error}</div>
          <button className="btn mt" onClick={() => window.location.reload()}>Retry</button>
        </div>
      </div>
    );
  } else if (!fleet || !booted) {
    content = <BootScreen />;
  } else if (page === 'fleet') {
    content = <Fleet fleet={fleet} results={results} onOpen={(id) => go('twin', id)} />;
  } else if (page === 'twin') {
    content = <LiveTwin fleet={fleet} selected={sel} onSelect={(id) => go('twin', id)} />;
  } else if (page === 'lab') {
    content = <FaultLab />;
  } else if (page === 'validation') {
    content = <Validation results={results} />;
  } else {
    content = <Architecture meta={meta} />;
  }

  return (
    <>
    <Background />
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-logo"><Plane size={20} /></div>
          <div>
            <div className="brand-name">AeroTwin</div>
            <div className="brand-sub">Engine Digital Twin</div>
          </div>
        </div>
        {PAGES.map((p) => (
          <button key={p.id} className={`nav-btn ${page === p.id ? 'active' : ''}`} onClick={() => go(p.id)}>
            <p.icon size={18} /> {p.label}
          </button>
        ))}
        <div className="sidebar-foot">
          <div><span className="live-dot" />Backend connected</div>
          <div style={{ marginTop: 6 }}>Predictive health monitoring for MALE-UAV aero-piston engines (Rotax 912 class).</div>
        </div>
      </aside>
      <main className="main"><div key={`${page}/${sel || ''}/${fleet && booted ? 1 : 0}`} className="page-anim">{content}</div></main>
    </div>
    </>
  );
}
