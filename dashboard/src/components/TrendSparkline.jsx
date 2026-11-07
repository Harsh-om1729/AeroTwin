import { Area, AreaChart, ReferenceLine, ResponsiveContainer, YAxis } from 'recharts';
import { CHART } from '../ui/chartTheme';

// Per-aircraft Health Index trend: status-coloured monotone line, fading area,
// the HI-50 alert threshold dashed, and the last point marked.
export default function TrendSparkline({ id, data, color }) {
  const rows = data.map((v, i) => ({ i, v }));
  const last = rows.length - 1;
  const dot = ({ cx, cy, index }) => (index === last
    ? (
      <g key="last">
        <circle cx={cx} cy={cy} r={6} fill={color} opacity={0.25} />
        <circle cx={cx} cy={cy} r={3} fill={color} />
      </g>
    )
    : <g key={index} />);
  return (
    <ResponsiveContainer>
      <AreaChart data={rows} margin={{ top: 6, right: 8, left: 0, bottom: 2 }}>
        <defs>
          <linearGradient id={`trend-${id}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor={color} stopOpacity={0.22} />
            <stop offset="1" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <YAxis hide domain={[0, 100]} />
        <ReferenceLine y={50} stroke={CHART.threshold} strokeDasharray={CHART.thresholdDash} />
        <Area type="monotone" dataKey="v" stroke={color} strokeWidth={CHART.strokeWidth} fill={`url(#trend-${id})`}
          dot={dot} activeDot={false} isAnimationActive animationDuration={CHART.drawInMs} />
      </AreaChart>
    </ResponsiveContainer>
  );
}
