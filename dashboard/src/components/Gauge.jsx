// 240-degree arc gauge with coloured limit bands, a value arc and a white
// tick marking what the healthy digital twin expects at this moment.
const START = 150; // degrees, measured clockwise from +x (SVG y points down)
const SWEEP = 240;
const CX = 70, CY = 66, R = 52;

const polar = (deg, r = R) => {
  const a = (deg * Math.PI) / 180;
  return [CX + r * Math.cos(a), CY + r * Math.sin(a)];
};

const arc = (from, to, r = R) => {
  const [x1, y1] = polar(from, r);
  const [x2, y2] = polar(to, r);
  return `M ${x1} ${y1} A ${r} ${r} 0 ${to - from > 180 ? 1 : 0} 1 ${x2} ${y2}`;
};

export default function Gauge({ label, value, unit, min, max, bands = [], expected, decimals = 0, icon: Icon }) {
  const frac = (v) => Math.min(1, Math.max(0, (v - min) / (max - min)));
  const ang = (v) => START + SWEEP * frac(v);
  const v = value ?? min;
  const band = bands.find((b) => v <= b.to) || bands[bands.length - 1];
  const color = band ? band.color : 'var(--accent)';

  const bandArcs = bands.map((b, i) => {
    const from = i === 0 ? min : bands[i - 1].to;
    const d = arc(ang(from), ang(Math.min(b.to, max)), R + 9);
    return <path key={i} d={d} stroke={b.color} strokeWidth="3" fill="none" opacity=".55" />;
  });

  const [ex1, ey1] = polar(ang(expected ?? min), R - 9);
  const [ex2, ey2] = polar(ang(expected ?? min), R + 6);

  return (
    <div className="panel" style={{ padding: '12px 10px 10px', textAlign: 'center' }}>
      <svg viewBox="0 0 140 112" style={{ width: '100%', maxWidth: 180 }}>
        {bandArcs}
        <path d={arc(START, START + SWEEP)} stroke="var(--bg-2)" strokeWidth="9" fill="none" strokeLinecap="round" />
        <path
          d={arc(START, Math.max(START + 0.5, ang(v)))}
          stroke={color}
          strokeWidth="9"
          fill="none"
          strokeLinecap="round"
          style={{ filter: `drop-shadow(0 0 4px ${color})`, transition: 'all .25s' }}
        />
        {expected != null && (
          <line x1={ex1} y1={ey1} x2={ex2} y2={ey2} stroke="#fff" strokeWidth="2.5" strokeLinecap="round">
            <title>Healthy twin expects {expected.toFixed(decimals)} {unit}</title>
          </line>
        )}
        <text x={CX} y={CY + 4} textAnchor="middle" fill="var(--text)" fontSize="21" fontWeight="800" fontFamily="var(--mono)">
          {value == null ? '—' : value.toFixed(decimals)}
        </text>
        <text x={CX} y={CY + 20} textAnchor="middle" fill="var(--text-3)" fontSize="10">
          {unit}
        </text>
        <text x={CX} y={108} textAnchor="middle" fill="var(--text-3)" fontSize="9">
          {expected != null ? `twin ${expected.toFixed(decimals)}` : ''}
        </text>
      </svg>
      <div style={{ fontSize: 12, color: 'var(--text-2)', fontWeight: 600, display: 'flex', gap: 6, justifyContent: 'center', alignItems: 'center' }}>
        {Icon && <Icon size={13} />} {label}
      </div>
    </div>
  );
}
