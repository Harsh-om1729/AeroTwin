// Fixed, non-interactive backdrop: a slowly drifting engineering grid,
// soft aurora glows and a few aircraft tracing contrails across the sky.
// Pure CSS/SVG animation (GPU-friendly); disabled under prefers-reduced-motion.
const ROUTES = [
  { d: 'M-80 640 C 300 520, 700 600, 1100 380 S 1700 180, 2000 120', dur: 46, delay: 0 },
  { d: 'M-80 220 C 400 300, 800 140, 1250 260 S 1750 420, 2000 360', dur: 58, delay: 14 },
  { d: 'M-80 900 C 500 820, 900 900, 1300 700 S 1800 520, 2000 560', dur: 64, delay: 30 },
];

const PLANE = 'M0 -1.6 L11 0 L0 1.6 L-2 5.5 L-4 5.5 L-2.4 1.2 L-8 1 L-10 3 L-11.5 3 L-10.4 0 L-11.5 -3 L-10 -3 L-8 -1 L-2.4 -1.2 L-4 -5.5 L-2 -5.5 Z';

export default function Background() {
  return (
    <div className="bg-fx" aria-hidden="true">
      <div className="bg-aurora a1" />
      <div className="bg-aurora a2" />
      <div className="bg-aurora a3" />
      <div className="bg-grid" />
      <svg className="bg-routes" viewBox="0 0 1920 1080" preserveAspectRatio="xMidYMid slice">
        {ROUTES.map((r, i) => (
          <g key={i}>
            <path d={r.d} className="route" />
            <path d={r.d} className="contrail" style={{ animationDuration: `${r.dur}s`, animationDelay: `${r.delay}s` }} />
            <path d={PLANE} className="plane">
              <animateMotion dur={`${r.dur}s`} begin={`${r.delay}s`} repeatCount="indefinite" rotate="auto" path={r.d} />
            </path>
          </g>
        ))}
      </svg>
      <div className="bg-vignette" />
    </div>
  );
}
