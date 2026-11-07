import { useEffect, useState } from 'react';
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { BellOff, Clock, Microscope, Stethoscope, Target, TriangleAlert } from 'lucide-react';
import { api } from '../api';
import { FAULT_COLORS, fmtDur } from '../util';

// Simple view of the validation page: four plain results, one chart and the
// honest limits, including the real-flight result. Every number is read from
// the same report as the detailed view.
function Result({ icon: Icon, accent, title, value, note }) {
  return (
    <div className="glass-tile kpi" style={{ '--kpi': accent }}>
      <div className="kpi-head"><span className="kpi-icon"><Icon size={15} /></span><span className="kpi-label">{title}</span></div>
      <div className="kpi-value">{value}</div>
      <div className="kpi-note">{note}</div>
    </div>
  );
}

const PLAIN_FAULT = { Lubrication: 'Oil loss', Cooling: 'Overheating', 'Lean cylinder': 'Fuel problem', Misfire: 'Spark plug', Vibration: 'Worn parts' };

export default function SimpleResults({ r, leadByType }) {
  const [real, setReal] = useState(null);
  useEffect(() => { api.realResults().then(setReal).catch(() => setReal(null)); }, []);
  const s = r.summary;
  const fa = r.metrics.false_alarms;
  const fused = real?.test?.methods?.find((m) => m.method === 'Fused');
  const data = leadByType.map((d) => ({ ...d, plain: PLAIN_FAULT[d.fault] || d.fault }));
  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title">How accurate is it?</h1>
          <div className="page-sub">
            We tested the system on {s.n_fault_missions + s.n_healthy_missions} practice flights it had never seen:
            {' '}{s.n_fault_missions} with a hidden engine problem and {s.n_healthy_missions} healthy ones. The flights are
            computer-simulated, so we know the right answer for every one and can mark the system like a test.
          </div>
        </div>
      </div>

      <div className="kpi-grid simple-results">
        <Result icon={Target} accent="var(--go)" title="Problems caught" value={<>{s.detection.k}<span className="of"> of {s.detection.n}</span></>}
          note="warned before the engine failed" />
        <Result icon={Stethoscope} accent="var(--go)" title="Right problem named" value={<>{s.diagnosis.k}<span className="of"> of {s.diagnosis.n}</span></>}
          note="also said which part was failing" />
        <Result icon={Clock} accent="var(--accent)" title="Typical warning" value={fmtDur(r.metrics.lead_time.median_s)}
          note="before the engine would have failed" />
        <Result icon={BellOff} accent="var(--accent-2)" title="False alarms" value={fa.events}
          note={`in ${fa.healthy_hours.toFixed(0)} hours of healthy flying`} />
      </div>

      <div className="grid g-wide mt">
        <div className="panel">
          <div className="panel-title"><Clock size={15} /> Warning time for each kind of problem</div>
          <div style={{ height: 250 }}>
            <ResponsiveContainer>
              <BarChart data={data} margin={{ top: 22, right: 10, left: -10 }}>
                <XAxis dataKey="plain" />
                <YAxis tickFormatter={(v) => `${v}m`} />
                <Tooltip cursor={{ fill: 'rgba(255,255,255,.04)' }} content={({ active, payload }) => (active && payload?.length
                  ? <div className="tt">{payload[0].payload.plain}: about <b>{fmtDur(payload[0].payload.lead_min * 60)}</b> of warning</div> : null)} />
                <Bar isAnimationActive={false} dataKey="lead_min" radius={[4, 4, 0, 0]} label={{ position: 'top', fill: 'var(--text-2)', fontSize: 11, formatter: (v) => fmtDur(v * 60) }}>
                  {data.map((d) => <Cell key={d.key} fill={FAULT_COLORS[d.key]} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="plain-note">Slow problems like oil loss are spotted many minutes early. A spark-plug failure happens within about two minutes, so there is little time to warn.</div>
        </div>

        <div className="panel honest">
          <div className="panel-title"><TriangleAlert size={15} /> Read these numbers with care</div>
          <ul className="plain-list">
            <li>The practice flights come from <b>the same computer model</b> the system uses to judge the engine, so these scores are a <b>best case</b>. A real engine will be harder.</li>
            {fused && (
              <li>
                We also tried it on <b>{real.test.flights.toLocaleString()} real {real.dataset.aircraft} flights</b> (a different engine). There it
                could <b>not yet</b> tell flights just before a repair from flights just after: it scored <b>{fused.auc.toFixed(2)}</b>, where
                0.50 is a coin flip.
              </li>
            )}
            <li>Making it work on real engines is the next step. It is a helper for engineers, not a certified safety system.</li>
          </ul>
          <div className="plain-note"><Microscope size={13} style={{ verticalAlign: -2 }} /> Want every statistic? Switch to <b>Detailed</b> view at the top of the page.</div>
        </div>
      </div>
    </>
  );
}
