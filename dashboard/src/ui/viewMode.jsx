import { useContext, useEffect, useState } from 'react';
import { BookOpen, Microscope } from 'lucide-react';
import { ViewCtx } from './viewContext';

// Simple view (default) explains everything in everyday words and hides the
// expert charts. Detailed view shows the full engineering dashboard. The choice
// is remembered per browser.
const KEY = 'aerotwin-view';

export function ViewProvider({ children }) {
  const [simple, setSimple] = useState(() => {
    try { return localStorage.getItem(KEY) !== 'detailed'; } catch { return true; }
  });
  useEffect(() => {
    try { localStorage.setItem(KEY, simple ? 'simple' : 'detailed'); } catch { /* storage unavailable */ }
  }, [simple]);
  return <ViewCtx.Provider value={{ simple, setSimple }}>{children}</ViewCtx.Provider>;
}

export function ViewSwitch() {
  const { simple, setSimple } = useContext(ViewCtx);
  return (
    <div className="view-switch" role="group" aria-label="How much detail to show">
      <span className="view-switch-label">View</span>
      <div className="seg">
        <button className={simple ? 'on' : ''} aria-pressed={simple} onClick={() => setSimple(true)}><BookOpen size={14} /> Simple</button>
        <button className={!simple ? 'on' : ''} aria-pressed={!simple} onClick={() => setSimple(false)}><Microscope size={14} /> Detailed</button>
      </div>
    </div>
  );
}

// A word with its plain meaning on hover/focus.
export function Term({ children, tip }) {
  return <span className="term" tabIndex={0} title={tip} aria-label={`${typeof children === 'string' ? children : ''}: ${tip}`}>{children}</span>;
}
