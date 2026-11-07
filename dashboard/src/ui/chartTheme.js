// Shared chart styling (plan §8). Global Recharts overrides (horizontal grid
// only, no axis lines, mono tick labels) live in index.css; these are the values
// components pass as props.
export const CHART = {
  grid: 'rgba(214, 224, 234, .08)',
  threshold: 'rgba(214, 224, 234, .35)',
  thresholdDash: '4 4',
  strokeWidth: 1.75,
  tick: { fill: '#c0b8cc', fontSize: 11, fontFamily: 'var(--font-mono)' },
  drawInMs: 700,
};

// Sequential heatmap scale for magnitude: #22102e -> #f6a623 (t in 0..1).
const LO = [34, 16, 46];
const HI = [246, 166, 35];
export const heatScale = (t) => {
  const k = Math.max(0, Math.min(1, t));
  return `rgb(${LO.map((c, i) => Math.round(c + (HI[i] - c) * k)).join(',')})`;
};
export const onHeat = (t) => (t > 0.55 ? '#1c0d26' : 'var(--text-1)');
