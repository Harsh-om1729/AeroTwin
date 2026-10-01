import { useEffect, useState } from 'react';
import { Area, AreaChart, ReferenceLine, ResponsiveContainer, YAxis } from 'recharts';
import { ChevronRight, CircleCheck, CircleX, Plane, Radar, Target, TriangleAlert } from 'lucide-react';
import CountUp from '../components/CountUp';
import FleetRadar from '../components/FleetRadar';
import { clock, decisionBadge, hiColor, pct, statusBadge } from '../util';

function Kpi({ label, value, note, icon: Icon, color, glow }) {
  return (
    <div className="panel kpi" style={{ '--glow': glow }}>
      <div className="kpi-label"><Icon size={14} color={color} /> {label}</div>
      <div className="kpi-value" style={{ color }}>{value}</div>
      {note && <div className="kpi-note">{note}</div>}
    </div>
  );
}

// Circular Health-Index gauge; the arc animates in from empty on mount.
function HiRing({ hi }) {
  const r = 31, c = 2 * Math.PI * r;
  const [shown, setShown] = useState(0);
  useEffect(() => {
    const id = requestAnimationFrame(() => setShown(hi));
    return () => cancelAnimationFrame(id);
  }, [hi]);
  const color = hiColor(hi);
  return (
    <svg viewBox="0 0 74 74" className="hi-ring" style={{ color }}>
      <circle cx="37" cy="37" r={r} fill="none" strokeWidth="6" className="track" />
      <circle cx="37" cy="37" r={r} fill="none" strokeWidth="6" stroke={color} strokeLinecap="round"
        strokeDasharray={c} strokeDashoffset={c * (1 - shown / 100)} className="val" />
      <text x="37" y="42" textAnchor="middle" fontSize="18" fontWeight="800" fill={color} fontFamily="Inter">
        {Math.round(hi)}
      </text>
    </svg>
  );
}

function useUtcClock() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  return now.toISOString().slice(11, 19);
}

export default function Fleet({ fleet, results, onOpen }) {
  const count = (d) => fleet.filter((f) => f.decision === d).length;
  const s = results?.summary;
  const utc = useUtcClock();
  return (
    <>
      <div className="panel hero">
        <div>
          <span className="badge b-info"><span className="live-dot" />Twin online</span>
          <h1 style={{ marginTop: 12 }}>Fleet Command</h1>
          <div className="page-sub">
            Engine health of each MALE-UAV after its last flight. Every card is a simulated test flight, never used in
            training, run end-to-end through the physics twin, the ML ensemble and the Bayesian health twin.
            Click an aircraft or a radar blip to replay its flight.
          </div>
          <div className="hero-meta">
            <span className="badge b-mute"><span className="hero-clock">{utc} UTC</span></span>
            <span className="badge b-ok">{count('GO')} cleared</span>
            <span className="badge b-crit">{count('NO-GO')} grounded</span>
            <span className="badge b-mute">Rotax 912 S/ULS class</span>
          </div>
        </div>
        <FleetRadar fleet={fleet} onOpen={onOpen} />
      </div>

      <div className="grid g5 mt stagger">
        <Kpi label="Aircraft" value={<CountUp value={fleet.length} />} note="Rotax 912-class engines" icon={Plane} color="var(--text)" />
        <Kpi label="Go" value={<CountUp value={count('GO')} />} note="cleared for next mission" icon={CircleCheck} color="var(--ok)" glow="rgba(34,197,94,.14)" />
        <Kpi label="Caution" value={<CountUp value={count('CAUTION')} />} note="inspect soon" icon={TriangleAlert} color="var(--warn)" glow="rgba(245,158,11,.14)" />
        <Kpi label="No-Go" value={<CountUp value={count('NO-GO')} />} note="grounded for maintenance" icon={CircleX} color="var(--crit)" glow="rgba(239,68,68,.16)" />
        <Kpi label="Faults detected" value={s ? <><CountUp value={s.detection.k} />/{s.detection.n}</> : '…'} note={s ? `simulated test flights · 95% CI ≥ ${pct(s.detection.ci95[0])}` : 'computing…'} icon={Target} color="var(--accent)" />
      </div>

      <div className="grid g4 mt stagger">
        {fleet.map((f) => (
          <div key={f.id} className={`panel fleet-card ${f.status === 'critical' ? 'crit' : f.status === 'warning' ? 'warn' : ''}`} onClick={() => onOpen(f.id)}>
            <div className="fc-top">
              <div>
                <div className="fc-id">{f.id}</div>
                <div className="fc-call">{f.callsign} · flight {clock(f.flight_s)}</div>
              </div>
              <span className={`badge ${decisionBadge(f.decision)}`}>{f.decision}</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 14, margin: '12px 0 2px' }}>
              <HiRing hi={f.hi} />
              <div style={{ minWidth: 0 }}>
                <div className="dim" style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '.6px', fontWeight: 600 }}>Health Index</div>
                <span className={`badge ${statusBadge(f.status)}`} style={{ marginTop: 6 }}>{f.status}</span>
              </div>
            </div>
            <div style={{ height: 50, margin: '4px -4px 0' }}>
              <ResponsiveContainer>
                <AreaChart data={f.spark.map((v, i) => ({ i, v }))} margin={{ top: 2, right: 0, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id={`sp-${f.id}`} x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0" stopColor={hiColor(f.hi)} stopOpacity=".4" />
                      <stop offset="1" stopColor={hiColor(f.hi)} stopOpacity="0" />
                    </linearGradient>
                  </defs>
                  <YAxis hide domain={[0, 100]} />
                  <ReferenceLine y={50} stroke="rgba(239,68,68,.35)" strokeDasharray="3 3" />
                  <Area dataKey="v" stroke={hiColor(f.hi)} fill={`url(#sp-${f.id})`} strokeWidth={2} dot={false} isAnimationActive={false} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
            <div className="fc-diag">
              {f.diagnosis ? (
                <>
                  <Radar size={12} style={{ verticalAlign: -1, marginRight: 4 }} color="var(--crit)" />
                  <b>{f.diagnosis.label}{f.diagnosis.cylinder ? ` · cyl ${f.diagnosis.cylinder}` : ''}</b>
                  <br />Alert at T+{clock(f.first_alert_t)}
                </>
              ) : (
                <>All residuals within healthy bounds.<br /><span className="dim">No fault signature detected.</span></>
              )}
            </div>
            <div className="fc-open">Open replay <ChevronRight size={12} style={{ verticalAlign: -2 }} /></div>
          </div>
        ))}
      </div>
    </>
  );
}
