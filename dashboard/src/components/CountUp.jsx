import { useEffect, useRef, useState } from 'react';

const reduced = () => typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

// Animates a number from its previous value to `value` (ease-out cubic).
export default function CountUp({ value, decimals = 0, duration = 900, prefix = '', suffix = '' }) {
  const [shown, setShown] = useState(reduced() ? value : 0);
  const from = useRef(reduced() ? value : 0);

  useEffect(() => {
    if (value == null || !Number.isFinite(value)) return undefined;
    if (reduced()) {
      from.current = value;
      return undefined;
    }
    const start = performance.now();
    const a = from.current;
    let raf;
    const tick = (now) => {
      const k = Math.min(1, (now - start) / duration);
      const v = a + (value - a) * (1 - (1 - k) ** 3);
      setShown(v);
      if (k < 1) raf = requestAnimationFrame(tick);
      else from.current = value;
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value, duration]);

  if (value == null || !Number.isFinite(value)) return <>{prefix}—{suffix}</>;
  return <>{prefix}{(reduced() ? value : shown).toFixed(decimals)}{suffix}</>;
}
