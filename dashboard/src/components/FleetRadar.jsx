// Radar scope: one blip per aircraft, coloured by its Go/No-Go decision,
// with a rotating sweep. Positions are fixed per aircraft index.
const COLORS = { GO: 'var(--ok)', CAUTION: 'var(--warn)', 'NO-GO': 'var(--crit)' };

export default function FleetRadar({ fleet, onOpen }) {
  const R = 92;
  return (
    <svg viewBox="-110 -110 220 220" className="radar" role="img" aria-label="Fleet radar">
      <defs>
        <radialGradient id="radar-bg">
          <stop offset="0" stopColor="rgba(255,255,255,.14)" />
          <stop offset="1" stopColor="rgba(255,255,255,.02)" />
        </radialGradient>
        <linearGradient id="sweep-g" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="rgba(255,45,135,0)" />
          <stop offset="1" stopColor="rgba(255,120,60,.7)" />
        </linearGradient>
      </defs>
      <circle r={R} fill="url(#radar-bg)" stroke="rgba(255,255,255,.3)" />
      {[0.33, 0.66].map((k) => <circle key={k} r={R * k} className="radar-ring" />)}
      <line x1={-R} x2={R} y1="0" y2="0" stroke="rgba(255,255,255,.14)" />
      <line y1={-R} y2={R} x1="0" x2="0" stroke="rgba(255,255,255,.14)" />
      <g className="radar-sweep">
        <path d={`M0 0 L${R} 0 A${R} ${R} 0 0 0 ${R * Math.cos(-0.7)} ${R * Math.sin(-0.7)} Z`} fill="url(#sweep-g)" />
      </g>
      {fleet.map((f, i) => {
        const a = (i / fleet.length) * Math.PI * 2 + 0.4;
        const r = R * (0.38 + 0.5 * ((i * 37) % 10) / 10);
        const c = COLORS[f.decision] || 'var(--accent)';
        return (
          <g key={f.id} transform={`translate(${r * Math.cos(a)} ${r * Math.sin(a)})`} className="blip" onClick={() => onOpen(f.id)} style={{ animationDelay: `${i * 0.35}s` }}>
            <circle r="9" fill={c} opacity=".18" className="blip-ring" />
            <circle r="3.4" fill={c} />
            <text y="-7" textAnchor="middle" fontSize="7" fill="var(--text)">{f.id}</text>
          </g>
        );
      })}
    </svg>
  );
}
