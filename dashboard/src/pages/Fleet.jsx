import { Area, AreaChart, ReferenceLine, ResponsiveContainer, YAxis } from 'recharts';
import { CircleCheck, CircleX, Plane, Radar, Target, TriangleAlert } from 'lucide-react';
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

export default function Fleet({ fleet, results, onOpen }) {
  const count = (d) => fleet.filter((f) => f.decision === d).length;
  const s = results?.summary;
  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title">Fleet Command</h1>
          <div className="page-sub">
            Health of each MALE-UAV aero-piston engine after its last flight. Each card is a simulated test flight, never used in
            training, processed end-to-end by the digital twin. Click an aircraft to replay its flight.
          </div>
        </div>
        <span className="badge b-info"><span className="live-dot" />Twin online</span>
      </div>

      <div className="grid g5">
        <Kpi label="Aircraft" value={fleet.length} note="Rotax 912-class engines" icon={Plane} color="var(--text)" />
        <Kpi label="Go" value={count('GO')} note="cleared for next mission" icon={CircleCheck} color="var(--ok)" glow="rgba(34,197,94,.14)" />
        <Kpi label="Caution" value={count('CAUTION')} note="inspect soon" icon={TriangleAlert} color="var(--warn)" glow="rgba(245,158,11,.14)" />
        <Kpi label="No-Go" value={count('NO-GO')} note="grounded for maintenance" icon={CircleX} color="var(--crit)" glow="rgba(239,68,68,.16)" />
        <Kpi label="Faults detected" value={s ? `${s.detection.k}/${s.detection.n}` : '…'} note={s ? `simulated test flights · 95% CI ≥ ${pct(s.detection.ci95[0])}` : 'computing…'} icon={Target} color="var(--accent)" />
      </div>

      <div className="grid g4 mt">
        {fleet.map((f) => (
          <div key={f.id} className={`panel fleet-card ${f.status === 'critical' ? 'crit' : f.status === 'warning' ? 'warn' : ''}`} onClick={() => onOpen(f.id)}>
            <div className="fc-top">
              <div>
                <div className="fc-id">{f.id}</div>
                <div className="fc-call">{f.callsign} · flight {clock(f.flight_s)}</div>
              </div>
              <span className={`badge ${decisionBadge(f.decision)}`}>{f.decision}</span>
            </div>
            <div className="fc-hi">
              <b style={{ color: hiColor(f.hi) }}>{f.hi.toFixed(0)}</b>
              <span>Health Index</span>
              <span className={`badge ${statusBadge(f.status)}`} style={{ marginLeft: 'auto' }}>{f.status}</span>
            </div>
            <div style={{ height: 54, margin: '4px -4px 0' }}>
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
          </div>
        ))}
      </div>
    </>
  );
}
