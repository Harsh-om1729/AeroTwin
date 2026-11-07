import { useEffect, useState } from 'react';

// 72px Health Index ring. Colour comes from the card's --status; the arc
// animates from empty on mount and to any new value.
export default function HealthRing({ hi }) {
  const r = 30, c = 2 * Math.PI * r;
  const [shown, setShown] = useState(0);
  useEffect(() => {
    const id = requestAnimationFrame(() => setShown(hi));
    return () => cancelAnimationFrame(id);
  }, [hi]);
  return (
    <svg viewBox="0 0 72 72" className="hi-ring" role="img" aria-label={`Health index ${Math.round(hi)} of 100`}>
      <circle cx="36" cy="36" r={r} fill="none" strokeWidth="6" className="trk" />
      <circle cx="36" cy="36" r={r} fill="none" strokeWidth="6" stroke="var(--status)" strokeLinecap="round"
        strokeDasharray={c} strokeDashoffset={c * (1 - Math.max(0, Math.min(100, shown)) / 100)} className="val" />
      <text x="36" y="43.5" textAnchor="middle">{Math.round(hi)}</text>
    </svg>
  );
}
