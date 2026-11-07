import { useState } from 'react';
import { getStatusTheme } from '../ui/statusTheme';

// Fleet radar: one contact per aircraft, coloured by its Go/No-Go decision.
// Positions keep the same per-index formula as before; only the drawing changed.
const R = 140;
const VB = 168; // viewBox half-size; room for bearing labels
const TICKS = Array.from({ length: 24 }, (_, k) => k * 15);
const BEARINGS = [['000', 0, -R - 9], ['090', R + 13, 3], ['180', 0, R + 16], ['270', -R - 13, 3]];

export default function FleetRadar({ fleet, onOpen }) {
  const [tip, setTip] = useState(null);
  const contacts = fleet.map((f, i) => {
    const a = (i / fleet.length) * Math.PI * 2 + 0.4;
    const r = R * (0.38 + 0.5 * ((i * 37) % 10) / 10);
    return { f, x: r * Math.cos(a), y: r * Math.sin(a), th: getStatusTheme(f.decision) };
  });
  const open = (e, id) => {
    if (e.type === 'click' || e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onOpen(id); }
  };
  const pct = (v) => `${((v + VB) / (2 * VB)) * 100}%`;

  return (
    <figure className="radar">
      <div className="radar-scope glass-well">
        <div className="radar-sweep" />
        <svg viewBox={`${-VB} ${-VB} ${2 * VB} ${2 * VB}`} role="group" aria-label={`Fleet radar, ${fleet.length} contacts`}>
          {[0.25, 0.5, 0.75].map((k) => <circle key={k} r={R * k} className="ring" />)}
          <circle r={R} className="ring outer" />
          <line x1={-R} x2={R} y1="0" y2="0" className="cross" />
          <line y1={-R} y2={R} x1="0" x2="0" className="cross" />
          {TICKS.map((d) => {
            const t = (d - 90) * Math.PI / 180;
            const len = d % 45 === 0 ? 7 : 4;
            return <line key={d} className="tick" x1={R * Math.cos(t)} y1={R * Math.sin(t)} x2={(R - len) * Math.cos(t)} y2={(R - len) * Math.sin(t)} />;
          })}
          {BEARINGS.map(([t, x, y]) => <text key={t} x={x} y={y} textAnchor="middle" className="bearing">{t}</text>)}
          {contacts.map(({ f, x, y, th }) => (
            <g key={f.id} transform={`translate(${x} ${y})`} className="blip" tabIndex={0} role="button"
              aria-label={`${f.id}, ${th.label}, health index ${Math.round(f.hi)}. Open replay`}
              onClick={(e) => open(e, f.id)} onKeyDown={(e) => open(e, f.id)}
              onMouseEnter={() => setTip(f.id)} onMouseLeave={() => setTip(null)}
              onFocus={() => setTip(f.id)} onBlur={() => setTip(null)}>
              <circle r="13" fill="transparent" />
              <g className="blip-body">
                {th.key === 'NOGO' && <circle r="3" fill="none" stroke={th.color} strokeWidth="1" className="blip-pulse" />}
                <circle r="7" fill={th.color} opacity=".2" />
                <circle r="3" fill={th.color} />
                <circle r="10" className="blip-focus" />
              </g>
              <text y="-11" textAnchor="middle" className="blip-label">{f.id}</text>
            </g>
          ))}
        </svg>
        {tip && (() => {
          const c = contacts.find((k) => k.f.id === tip);
          return (
            <div className="radar-tip" style={{ left: pct(c.x), top: pct(c.y) }}>
              {c.f.id} · <span style={{ color: c.th.color }}>{c.th.label}</span> · HI {Math.round(c.f.hi)}
            </div>
          );
        })()}
      </div>
      <figcaption className="label">Fleet radar · {fleet.length} contacts</figcaption>
    </figure>
  );
}
