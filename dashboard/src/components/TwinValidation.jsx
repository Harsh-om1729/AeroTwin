import { useState } from 'react';
import {
  Area, Bar, BarChart, CartesianGrid, ComposedChart, Legend, Line, ReferenceLine, ResponsiveContainer, Scatter,
  Tooltip, XAxis, YAxis,
} from 'recharts';
import { Atom, Crosshair, Hourglass, ShieldCheck, Target, Timer } from 'lucide-react';
import { FAULT_SHORT, fmtDur, pct } from '../util';

function Stat({ icon: Icon, label, twin, base, baseLabel, note }) {
  return (
    <div className="twin-stat">
      <span><Icon size={12} /> {label}</span>
      <b style={{ color: 'var(--accent-2)' }}>{twin}</b>
      <em>{base != null ? `${baseLabel}: ${base}` : note}</em>
    </div>
  );
}

const Tip = ({ active, payload, fmt }) => {
  if (!active || !payload?.length) return null;
  return <div className="tt">{fmt(payload[0].payload)}</div>;
};

export default function TwinValidation({ twin }) {
  const [ft, setFt] = useState('lubrication');
  const fa = twin.false_alarms;
  const c90 = twin.coverage.find((c) => c.nominal === 90);
  const delays = twin.by_type.map((d) => ({ fault: FAULT_SHORT[d.fault_type], twin: d.twin_delay_s, ml: d.ml_delay_s }));
  const calib = [{ nominal: 0, empirical: 0 }, ...twin.coverage.map((c) => ({ nominal: c.nominal, empirical: c.empirical * 100 })), { nominal: 100, empirical: 100 }];
  const trace = (twin.health_traces[ft] || []).map((p) => ({ ...p, band: [p.p5, p.p95] }));
  const fan = (twin.rul_fans[ft] || []).map((p) => ({ dt: p.dt, p50: p.p50, true: p.true, b90: [p.p5, p.p95], b50: [p.p25, p.p75] }));

  return (
    <div className="panel flagship mt">
      <div className="panel-title">
        <Atom size={15} /> Flagship: Bayesian health twin vs ML ensemble
        <span className="right dim" style={{ fontSize: 11 }}>same 120 test flights · filter tuned only on separate simulated flights</span>
      </div>

      <div className="grid g5 stagger" style={{ marginBottom: 16 }}>
        <Stat icon={Timer} label="Median detection delay" twin={fmtDur(twin.median_delay_s)} base={fmtDur(twin.ml_median_delay_s)} baseLabel="ML ensemble" />
        <Stat icon={Hourglass} label="RUL median error" twin={fmtDur(twin.rul_median_abs_err_s.twin)} base={fmtDur(twin.rul_median_abs_err_s.linear)} baseLabel="HI linear trend*" />
        <Stat icon={Target} label={`RUL within ±${twin.alpha_lambda.alpha * 100}% (α-λ)`} twin={pct(twin.alpha_lambda.twin)} base={pct(twin.alpha_lambda.linear, 1)} baseLabel="linear trend" />
        <Stat icon={Crosshair} label="Hidden-health error" twin={twin.health_mae.toFixed(3)} note="mean |estimate − true health|" />
        <Stat icon={ShieldCheck} label="False alarms" twin={`${fa.events} events`} note={`in ${fa.healthy_hours.toFixed(0)} h · 95% upper ${fa.ci95[1].toFixed(3)} /FH · detect ${twin.detection.k}/${twin.detection.n}, diagnose ${twin.diagnosis.k}/${twin.diagnosis.n}`} />
      </div>

      <div className="grid g2">
        <div>
          <div className="sub-title">Detection delay after fault onset (median, lower is better)</div>
          <div style={{ height: 240 }}>
            <ResponsiveContainer>
              <BarChart data={delays} margin={{ top: 6, right: 6, left: -10 }}>
                <CartesianGrid vertical={false} />
                <XAxis dataKey="fault" />
                <YAxis tickFormatter={(v) => `${v}s`} />
                <Tooltip cursor={{ fill: 'rgba(255,255,255,.03)' }} content={<Tip fmt={(p) => <>{p.fault}<br />twin <b>{fmtDur(p.twin)}</b> · ML <b>{fmtDur(p.ml)}</b></>} />} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Bar isAnimationActive={false} dataKey="twin" name="Bayesian twin" fill="var(--accent-2)" radius={[4, 4, 0, 0]} />
                <Bar isAnimationActive={false} dataKey="ml" name="ML ensemble" fill="#64748b" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="dim" style={{ fontSize: 11.5 }}>
            Not a like-for-like race: the ML path waits for a 60 s window plus 8 × 10 s of persistence, while the twin decides at
            1 Hz, and the twin uses the simulator&apos;s own equations. *The HI linear trend extrapolates to HI = 50, not to the physical
            failure threshold the truth uses, so its RUL error is partly a definition mismatch.
          </div>
        </div>
        <div>
          <div className="sub-title">Uncertainty calibration: do the credible intervals mean what they say?</div>
          <div style={{ height: 240 }}>
            <ResponsiveContainer>
              <ComposedChart data={calib} margin={{ top: 6, right: 10, left: -10 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="nominal" type="number" domain={[0, 100]} ticks={[0, 25, 50, 75, 100]} tickFormatter={(v) => `${v}%`} label={{ value: 'nominal interval', position: 'insideBottom', offset: -2, fill: 'var(--text-3)', fontSize: 11 }} />
                <YAxis domain={[0, 100]} ticks={[0, 25, 50, 75, 100]} tickFormatter={(v) => `${v}%`} />
                <ReferenceLine segment={[{ x: 0, y: 0 }, { x: 100, y: 100 }]} stroke="#fff" strokeDasharray="4 3" />
                <Tooltip content={<Tip fmt={(p) => <>{p.nominal}% interval contains truth <b>{p.empirical.toFixed(1)}%</b> of the time</>} />} />
                <Line isAnimationActive={false} dataKey="empirical" stroke="var(--accent-2)" strokeWidth={2} dot={false} />
                <Scatter isAnimationActive={false} data={calib.slice(1, -1)} dataKey="empirical" fill="var(--accent-2)" />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          <div className="dim" style={{ fontSize: 11.5 }}>
            Over {twin.n_rul_points.toLocaleString()} RUL predictions: the 90% interval contains the true failure time {pct(c90.empirical, 1)} of the time
            (95% CI {pct(c90.ci95[0], 1)}–{pct(c90.ci95[1], 1)}, bootstrapped over flights). Perfect calibration lies on the diagonal; the 50% interval
            is somewhat over-confident.
          </div>
        </div>
      </div>

      <div className="sub-title mt" style={{ justifyContent: 'space-between' }}>
        <span>Example flight: hidden health and RUL fan vs ground truth</span>
        <span className="seg">
          {Object.keys(twin.health_traces).map((k) => (
            <button key={k} className={ft === k ? 'on' : ''} onClick={() => setFt(k)}>{FAULT_SHORT[k]}</button>
          ))}
        </span>
      </div>
      <div className="grid g2">
        <div style={{ height: 230 }}>
          <ResponsiveContainer>
            <ComposedChart data={trace} margin={{ top: 6, right: 6, left: -16 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="dt" type="number" domain={['dataMin', 'dataMax']} tickFormatter={(v) => `${Math.round(v / 60)}m`} />
              <YAxis domain={[0, 1]} />
              <ReferenceLine x={0} stroke="var(--warn)" strokeDasharray="4 3" label={{ value: 'onset', fill: 'var(--warn)', fontSize: 10, position: 'insideTopRight' }} />
              <Tooltip content={<Tip fmt={(p) => <>{p.dt >= 0 ? '+' : ''}{p.dt}s · truth <b>{p.true.toFixed(3)}</b> · twin <b>{p.p50.toFixed(3)}</b></>} />} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Area isAnimationActive={false} dataKey="band" name="twin 90% band" stroke="none" fill="var(--accent-2)" fillOpacity={0.3} />
              <Line isAnimationActive={false} dataKey="p50" name="twin estimate" stroke="var(--accent-2)" strokeWidth={2} dot={false} />
              <Line isAnimationActive={false} dataKey="true" name="true health (hidden)" stroke="var(--warn)" strokeDasharray="5 4" strokeWidth={1.6} dot={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
        <div style={{ height: 230 }}>
          <ResponsiveContainer>
            <ComposedChart data={fan} margin={{ top: 6, right: 6, left: -16 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="dt" type="number" domain={['dataMin', 'dataMax']} tickFormatter={(v) => `${Math.round(v / 60)}m`} />
              <YAxis label={{ value: 'RUL (min)', angle: -90, position: 'insideLeft', offset: 24, fill: 'var(--text-3)', fontSize: 11 }} />
              <Tooltip content={<Tip fmt={(p) => <>{p.dt}s after onset · true RUL <b>{p.true.toFixed(1)}</b> min · twin <b>{p.p50.toFixed(1)}</b> min [{p.b90[0].toFixed(1)}–{p.b90[1].toFixed(1)}]</>} />} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Area isAnimationActive={false} dataKey="b90" name="90% interval" stroke="none" fill="var(--warn)" fillOpacity={0.18} />
              <Area isAnimationActive={false} dataKey="b50" name="50% interval" stroke="none" fill="var(--warn)" fillOpacity={0.32} />
              <Line isAnimationActive={false} dataKey="p50" name="twin median" stroke="var(--warn)" strokeWidth={2} dot={false} />
              <Line isAnimationActive={false} dataKey="true" name="true RUL (hidden)" stroke="#fff" strokeDasharray="5 4" strokeWidth={1.4} dot={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
