import { useEffect, useState } from 'react';
import { ArrowRight, CircleCheck, CircleX, Clock, MousePointerClick, Plane, Radar, Target, TriangleAlert } from 'lucide-react';
import { Term } from '../ui/viewMode';
import { useSimple } from '../ui/viewContext';
import CountUp from '../components/CountUp';
import FleetRadar from '../components/FleetRadar';
import HealthRing from '../components/HealthRing';
import StatusBadge from '../components/StatusBadge';
import TrendSparkline from '../components/TrendSparkline';
import { getStatusTheme, statusVars } from '../ui/statusTheme';
import { clock, pct } from '../util';
import { plainFault } from '../ui/plain';

function Kpi({ i, label, icon: Icon, accent, value, valueColor = 'var(--text-1)', note, ratio }) {
  return (
    <div className={`glass-tile kpi ${ratio != null ? 'has-bar' : ''}`} style={{ '--kpi': accent, '--i': i }}>
      <div className="kpi-head">
        <span className="kpi-icon"><Icon size={15} /></span>
        <span className="kpi-label">{label}</span>
      </div>
      <div className="kpi-value" style={{ color: valueColor }}>{value}</div>
      {note && <div className="kpi-note">{note}</div>}
      {ratio != null && <div className="kpi-bar" aria-hidden="true"><i style={{ transform: `scaleX(${ratio})` }} /></div>}
    </div>
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

function AircraftCard({ f, i, onOpen }) {
  const simple = useSimple();
  const th = getStatusTheme(f.decision);
  const open = (e) => {
    if (e.type === 'click' || e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onOpen(f.id); }
  };
  return (
    <div className={`glass-module fleet-card s-${th.key}`} style={{ ...statusVars(th), '--i': i + 5 }}
      role="button" tabIndex={0} onClick={open} onKeyDown={open}
      aria-label={`${f.id}, ${f.callsign}: ${th.label}, health index ${Math.round(f.hi)}, ${f.status}. Open replay`}>
      <div className="fc-head">
        <div>
          <div className="fc-id">{f.id}</div>
          <div className="fc-meta">{f.callsign} · <Clock size={12} /> <span className="mono">{clock(f.flight_s)}</span></div>
        </div>
        <StatusBadge decision={f.decision} />
      </div>
      <div className="fc-health">
        <HealthRing hi={f.hi} />
        <div>
          <div className="label">{simple ? 'Health score' : 'Health index'}</div>
          <span className="cat-chip">{simple ? { nominal: 'healthy', warning: 'needs a check', critical: 'serious problem' }[f.status] || f.status : f.status}</span>
        </div>
      </div>
      <div className="glass-well fc-trend">
        <TrendSparkline id={f.id} data={f.spark} color={th.color} />
      </div>
      <div className="fc-fault">
        {f.diagnosis ? (
          <>
            <Radar size={15} />
            <div>
              <b>{simple ? plainFault(f.diagnosis) : f.diagnosis.label}{f.diagnosis.cylinder ? (simple ? `, cylinder ${f.diagnosis.cylinder}` : ` · cyl ${f.diagnosis.cylinder}`) : ''}</b>
              {f.first_alert_t != null && (simple
                ? <>Warning raised {Math.round(f.first_alert_t / 60)} min into the flight</>
                : <>Alert at <time>T+{clock(f.first_alert_t)}</time></>)}
            </div>
          </>
        ) : f.decision === 'GO' ? (
          <><CircleCheck size={15} /><span>{simple ? 'Everything looks normal' : 'All residuals within healthy bounds'}</span></>
        ) : (
          <><TriangleAlert size={15} /><span>{simple ? 'Grounded, but no single part is to blame yet. Open the replay to see why.' : <>No rule-based fault signature. Open the replay for the advisor&apos;s reasons.</>}</span></>
        )}
      </div>
      <div className="fc-action">{simple ? 'Watch this flight' : 'Open replay'} <ArrowRight size={14} /></div>
    </div>
  );
}

export default function Fleet({ fleet, results, onOpen }) {
  const simple = useSimple();
  const count = (d) => fleet.filter((f) => f.decision === d).length;
  const n = fleet.length;
  const s = results?.summary;
  const utc = useUtcClock();
  const caution = count('CAUTION');
  return (
    <>
      <section className="glass-stage hero">
        <div>
          <span className="status-pill label"><span className="dot pulse" />Twin online</span>
          <h1 className="display">{simple ? 'Fleet overview' : 'Fleet Command'}</h1>
          {simple ? (
            <p className="hero-desc">
              This is a health check for a fleet of {n} drone engines. After each flight, the system decides if the engine is
              safe to fly again. The flights are computer-simulated, so we know the right answer and can check the system.
            </p>
          ) : (
            <p className="hero-desc">
              Engine health of each MALE-UAV after its last flight. Every card is a simulated test flight, never used in
              training, run end-to-end through the physics twin, the ML ensemble and the Bayesian health twin.
              Click an aircraft or a radar contact to replay its flight.
            </p>
          )}
          <div className="ro-chips">
            <span className="ro-chip clock">{utc} UTC</span>
            <span className="ro-chip go"><span className="dot" />{count('GO')} cleared</span>
            {caution > 0 && <span className="ro-chip caution"><span className="dot" />{caution} caution</span>}
            <span className="ro-chip nogo"><span className="dot" />{count('NO-GO')} grounded</span>
            <span className="ro-chip"><span className="k">Engine ·</span> Rotax 912 S/ULS</span>
          </div>
          {simple && (
            <ul className="read-guide" aria-label="How to read this page">
              <li><span className="rg-icon"><Target size={15} /></span><span><b>Health score 0–100.</b> Higher is healthier. Staying below 50 sets off a warning.</span></li>
              <li><span className="rg-icon go"><CircleCheck size={15} /></span><span><b>GO</b> = safe for the next flight. <b className="nogo">NO-GO</b> = repair it first.</span></li>
              <li><span className="rg-icon"><MousePointerClick size={15} /></span><span><b>Click any card</b> to watch that flight and see when the problem was spotted.</span></li>
            </ul>
          )}
        </div>
        <FleetRadar fleet={fleet} onOpen={onOpen} />
      </section>

      <div className="kpi-grid">
        <Kpi i={0} label={simple ? 'Drones' : 'Total aircraft'} icon={Plane} accent="var(--accent)" value={<CountUp value={n} duration={600} />} note={simple ? 'drones in the fleet' : 'Rotax 912-class engines'} />
        <Kpi i={1} label="Go" icon={CircleCheck} accent="var(--go)" valueColor="var(--go)" value={<CountUp value={count('GO')} duration={600} />} note={simple ? 'safe to fly' : 'cleared for next mission'} ratio={count('GO') / n} />
        <Kpi i={2} label="Caution" icon={TriangleAlert} accent="var(--caution)" valueColor={caution ? 'var(--caution)' : 'var(--text-3)'} value={<CountUp value={caution} duration={600} />} note={simple ? 'check soon' : 'inspect soon'} ratio={caution / n} />
        <Kpi i={3} label="No-Go" icon={CircleX} accent="var(--nogo)" valueColor="var(--nogo)" value={<CountUp value={count('NO-GO')} duration={600} />} note={simple ? 'must be repaired first' : 'grounded for maintenance'} ratio={count('NO-GO') / n} />
        <Kpi i={4} label={simple ? 'Problems caught' : 'Faults detected'} icon={Target} accent="var(--accent-2)"
          value={s ? <><CountUp value={s.detection.k} duration={600} /><span className="of">/{s.detection.n}</span></> : '…'}
          note={s ? (simple ? <>in {s.detection.n} test flights with a hidden <Term tip="Test flights are computer-simulated, so the true problem is known and the answer can be checked.">engine problem</Term></> : `simulated test flights · 95% CI ≥ ${pct(s.detection.ci95[0])}`) : 'computing…'}
          ratio={s ? s.detection.k / s.detection.n : undefined} />
      </div>

      <div className="fleet-grid">
        {fleet.map((f, i) => <AircraftCard key={f.id} f={f} i={i} onOpen={onOpen} />)}
      </div>
    </>
  );
}
