import { useEffect, useState } from 'react';
import { Activity, BarChart3, Bot, FlaskConical, LayoutGrid, Network } from 'lucide-react';
import { api } from './api';
import Fleet from './pages/Fleet';
import LiveTwin from './pages/LiveTwin';
import FaultLab from './pages/FaultLab';
import Validation from './pages/Validation';
import Architecture from './pages/Architecture';
import Copilot from './pages/Copilot';
import Background from './components/Background';
import BootScreen from './components/BootScreen';
import Logo from './components/Logo';
import { ViewProvider, ViewSwitch } from './ui/viewMode';

const PAGES = [
  { id: 'fleet', label: 'Fleet overview', short: 'Fleet', icon: LayoutGrid },
  { id: 'twin', label: 'Flight replay', short: 'Replay', icon: Activity },
  { id: 'lab', label: 'Try a fault', short: 'Lab', icon: FlaskConical },
  { id: 'copilot', label: 'Ask the AI', short: 'Ask AI', icon: Bot },
  { id: 'validation', label: 'How accurate is it?', short: 'Accuracy', icon: BarChart3 },
  { id: 'architecture', label: 'How it works', short: 'How', icon: Network },
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
  const [resultsError, setResultsError] = useState(null);
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
    api.results().then(setResults).catch((e) => setResultsError(e.message));
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
  } else if (page === 'copilot') {
    content = <Copilot fleet={fleet} selected={sel} />;
  } else if (page === 'validation') {
    content = <Validation results={results} error={resultsError} />;
  } else {
    content = <Architecture meta={meta} />;
  }

  return (
    <ViewProvider>
    <Background />
    <div className="shell">
      <aside className="sidebar glass-rail">
        <div className="brand">
          <div className="brand-logo"><Logo /></div>
          <div className="brand-text">
            <div className="brand-name">AeroTwin</div>
            <div className="brand-sub">Engine Digital Twin</div>
          </div>
        </div>
        <div className="nav-section label">Operations</div>
        <nav className="nav-list" aria-label="Pages">
          <span className="nav-ind" style={{ '--i': PAGES.findIndex((p) => p.id === page) }} />
          {PAGES.map((p) => (
            <button key={p.id} className={`nav-btn ${page === p.id ? 'active' : ''}`} data-label={p.label}
              aria-current={page === p.id ? 'page' : undefined} onClick={() => go(p.id)}>
              <p.icon size={18} strokeWidth={1.75} />
              <span className="nav-label">{p.label}</span>
              <span className="nav-short" aria-hidden="true">{p.short}</span>
            </button>
          ))}
        </nav>
        <div className="sys-status" role="status">
          <div className="sys-conn" title={error ? 'Backend unreachable' : 'Backend connected'}>
            <span className={`dot ${error ? 'down' : 'pulse'}`} />
            <span className="sys-text">{error ? 'Backend unreachable' : 'Backend connected'}</span>
          </div>
          <div className="sys-desc">Predictive health monitoring for MALE-UAV aero-piston engines (Rotax 912 class).</div>
        </div>
      </aside>
      <main className="main">{fleet && booted && !error && <ViewSwitch />}<div key={`${page}/${sel || ''}/${fleet && booted ? 1 : 0}`} className="page-anim">{content}</div></main>
    </div>
    </ViewProvider>
  );
}
