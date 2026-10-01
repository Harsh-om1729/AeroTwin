// Top-down schematic of a Rotax 912-class flat-four. Cylinder heads are
// coloured by live CHT, exhaust ports by EGT; the propeller spins with RPM,
// the engine shakes with the vibration residual, and the cylinder the
// diagnosis engine flags blinks red.

const STOPS = [
  [40, [30, 64, 175]],
  [85, [34, 197, 94]],
  [115, [245, 158, 11]],
  [135, [239, 68, 68]],
];
const EGT_STOPS = [
  [200, [30, 64, 175]],
  [550, [245, 158, 11]],
  [880, [239, 68, 68]],
];

function ramp(stops, v) {
  if (v == null) return 'rgb(60,70,90)';
  if (v <= stops[0][0]) return `rgb(${stops[0][1].join(',')})`;
  for (let i = 1; i < stops.length; i++) {
    const [t1, c1] = stops[i];
    const [t0, c0] = stops[i - 1];
    if (v <= t1) {
      const f = (v - t0) / (t1 - t0);
      return `rgb(${c0.map((c, k) => Math.round(c + (c1[k] - c) * f)).join(',')})`;
    }
  }
  return `rgb(${stops[stops.length - 1][1].join(',')})`;
}

// Rotax 912 numbering: 1 front-right, 2 front-left, 3 rear-right, 4 rear-left
const CYL = {
  1: { x: 250, y: 104, side: 'R' },
  2: { x: 60, y: 104, side: 'L' },
  3: { x: 250, y: 188, side: 'R' },
  4: { x: 60, y: 188, side: 'L' },
};

function Cylinder({ n, cht, egt, flagged }) {
  const { x, y, side } = CYL[n];
  const fill = ramp(STOPS, cht);
  const fins = Array.from({ length: 7 }, (_, i) => x + 14 + i * 11);
  const exX = side === 'R' ? x + 96 : x - 6;
  return (
    <g>
      <rect x={x} y={y} width="90" height="62" rx="9" fill={fill} opacity=".88" stroke={flagged ? '#ef4444' : 'rgba(255,255,255,.25)'} strokeWidth={flagged ? 3 : 1} className={flagged ? 'cyl-alert' : ''} />
      {fins.map((fx) => (
        <line key={fx} x1={fx} y1={y + 5} x2={fx} y2={y + 57} stroke="rgba(0,0,0,.25)" strokeWidth="2" />
      ))}
      <circle cx={exX} cy={y + 31} r="7" fill={ramp(EGT_STOPS, egt)} style={{ filter: `drop-shadow(0 0 6px ${ramp(EGT_STOPS, egt)})` }} />
      <rect x={x + 8} y={y + 8} width="74" height="46" rx="6" fill="rgba(4,10,22,.62)" />
      <text x={x + 45} y={y + 22} textAnchor="middle" fontSize="10" fill="#cbd5e1" fontWeight="700">CYL {n}</text>
      <text x={x + 45} y={y + 36} textAnchor="middle" fontSize="10.5" fill="#fff" fontFamily="var(--mono)">CHT {cht != null ? cht.toFixed(0) : '—'}°</text>
      <text x={x + 45} y={y + 49} textAnchor="middle" fontSize="10.5" fill="#fde68a" fontFamily="var(--mono)">EGT {egt != null ? egt.toFixed(0) : '—'}°</text>
    </g>
  );
}

export default function EngineDiagram({ row, flaggedCyl, flaggedSystem }) {
  const rpm = row?.rpm ?? 0;
  const vibZ = Math.max(0, row?.z?.vib_rms_g ?? 0);
  const shakePx = Math.min(3, vibZ / 4);
  const oilLow = flaggedSystem === 'lubrication';
  const coolingBad = flaggedSystem === 'cooling_degradation';
  const propDur = rpm > 100 ? Math.max(0.09, 500 / rpm) : 0;

  return (
    <svg viewBox="0 0 400 330" className="engine-svg">
      <defs>
        <linearGradient id="case" x1="0" x2="1">
          <stop offset="0" stopColor="#334155" />
          <stop offset=".5" stopColor="#64748b" />
          <stop offset="1" stopColor="#334155" />
        </linearGradient>
        <radialGradient id="hub">
          <stop offset="0" stopColor="#e2e8f0" />
          <stop offset="1" stopColor="#64748b" />
        </radialGradient>
      </defs>

      {/* propeller, seen edge-on from above: blades sweep through the plane */}
      {propDur > 0 && <rect x="78" y="49" width="244" height="6" rx="3" fill="rgba(148,163,184,.12)" />}
      <g className={propDur ? 'prop' : ''} style={{ animationDuration: `${propDur}s` }}>
        <ellipse cx="200" cy="52" rx="120" ry="5" fill="rgba(203,213,225,.75)" />
      </g>
      <circle cx="200" cy="52" r="13" fill="url(#hub)" />
      <rect x="194" y="64" width="12" height="28" fill="#475569" />

      <g className={shakePx > 0.3 ? 'shake' : ''} style={{ '--sx': `${shakePx}px` }}>
        {/* crankcase */}
        <rect x="160" y="92" width="80" height="176" rx="14" fill="url(#case)" stroke={flaggedSystem === 'abnormal_vibration' ? '#ef4444' : 'rgba(255,255,255,.2)'} strokeWidth={flaggedSystem === 'abnormal_vibration' ? 3 : 1} className={flaggedSystem === 'abnormal_vibration' ? 'cyl-alert' : ''} />
        <text x="200" y="168" textAnchor="middle" fontSize="10" fill="#e2e8f0" fontWeight="700">CRANK</text>
        <text x="200" y="182" textAnchor="middle" fontSize="10" fill="#e2e8f0" fontFamily="var(--mono)">{rpm.toFixed(0)} rpm</text>
        <text x="200" y="200" textAnchor="middle" fontSize="9.5" fill="#cbd5e1" fontFamily="var(--mono)">{row?.vib_rms_g != null ? `${row.vib_rms_g.toFixed(2)} g` : ''}</text>

        {/* connecting rods */}
        {[1, 2, 3, 4].map((n) => {
          const { x, y, side } = CYL[n];
          return <rect key={n} x={side === 'R' ? 240 : x + 90} y={y + 24} width={side === 'R' ? 10 : 10} height="14" fill="#475569" />;
        })}
        {[1, 2, 3, 4].map((n) => (
          <Cylinder key={n} n={n} cht={row?.[`cht_${n}`]} egt={row?.[`egt_${n}`]} flagged={flaggedCyl === n || coolingBad} />
        ))}

        {/* oil sump */}
        <rect x="150" y="276" width="100" height="36" rx="9" fill={oilLow ? 'rgba(239,68,68,.25)' : 'rgba(245,158,11,.18)'} stroke={oilLow ? '#ef4444' : 'rgba(245,158,11,.6)'} strokeWidth={oilLow ? 3 : 1} className={oilLow ? 'cyl-alert' : ''} />
        <text x="200" y="291" textAnchor="middle" fontSize="9.5" fill="#fde68a" fontWeight="700">OIL</text>
        <text x="200" y="305" textAnchor="middle" fontSize="10" fill="#fff" fontFamily="var(--mono)">
          {row?.oil_press_bar != null ? `${row.oil_press_bar.toFixed(2)} bar · ${row.oil_temp_c.toFixed(0)}°C` : '—'}
        </text>
      </g>

      {/* legend */}
      <g fontSize="9" fill="var(--text-3)">
        <text x="8" y="296">CHT</text>
        {[40, 70, 100, 120, 135].map((v, i) => (
          <rect key={v} x={30 + i * 14} y="288" width="14" height="9" fill={ramp(STOPS, v)} />
        ))}
        <text x="30" y="310">40°</text>
        <text x="84" y="310">135°</text>
        <text x="300" y="296">EGT port</text>
        <circle cx="352" cy="293" r="4" fill={ramp(EGT_STOPS, 300)} />
        <circle cx="364" cy="293" r="4" fill={ramp(EGT_STOPS, 600)} />
        <circle cx="376" cy="293" r="4" fill={ramp(EGT_STOPS, 880)} />
        <text x="300" y="310">FRONT ↑ (prop)</text>
      </g>
    </svg>
  );
}
