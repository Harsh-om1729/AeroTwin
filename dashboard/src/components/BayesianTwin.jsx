// Flagship panel: the particle-filter health twin's live beliefs --
// which fault hypothesis explains the sensors, how healthy the hidden
// component is (with a credible band), and the RUL as a probability fan.
import { useMemo } from 'react';
import { Area, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Atom, Gauge as GaugeIcon, Hourglass, Sigma } from 'lucide-react';
import { HYP_LABEL, clock, fmtDur, trueHealth } from '../util';

const COMPONENT = {
  lubrication: 'oil-system health',
  cooling_degradation: 'cooling efficiency',
  injector_abnormality: 'mixture health',
  misfire: 'ignition health',
  abnormal_vibration: 'bearing health',
};
const DETECT_P = 0.95;

function Tip({ active, payload, label, unit }) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div className="tt">
      <div className="dim">T+{clock(label)}</div>
      {p.p50 != null && <div style={{ color: 'var(--accent-2)' }}>estimate <b>{p.p50.toFixed(unit ? 1 : 3)}</b>{unit} {p.band && <span className="dim">[{p.band[0].toFixed(unit ? 1 : 3)} – {p.band[1].toFixed(unit ? 1 : 3)}]</span>}</div>}
      {p.true != null && <div style={{ color: 'var(--warn)' }}>truth <b>{p.true.toFixed(unit ? 1 : 3)}</b>{unit}</div>}
    </div>
  );
}

export default function BayesianTwin({ timeline, idx, truth, showTruth, maxT }) {
  const cur = timeline[idx];
  const tw = cur.twin;
  const detected = tw.p_degraded > DETECT_P;
  const firstDetect = useMemo(() => timeline.find((r) => r.twin.p_degraded > DETECT_P), [timeline]);
  const hasTruth = showTruth && truth?.fault_type && truth.rate != null;

  const data = useMemo(() => timeline.slice(0, idx + 1).map((r) => {
    const d = r.twin.p_degraded > 0.5;
    const rul = r.twin.p_degraded > DETECT_P && r.twin.rul ? r.twin.rul : null;
    const trueRul = hasTruth && r.t >= truth.fault_start_t && r.t < truth.failure_t ? (truth.failure_t - r.t) / 60 : null;
    return {
      t: r.t,
      p50: d ? r.twin.health.p50 : 1,
      band: d ? [r.twin.health.p5, r.twin.health.p95] : [1, 1],
      true: hasTruth ? trueHealth(truth, r.t) : null,
      r50: rul ? rul.p50 / 60 : null,
      r90: rul ? [rul.p5 / 60, rul.p95 / 60] : null,
      r50b: rul ? [rul.p25 / 60, rul.p75 / 60] : null,
      rtrue: trueRul,
    };
  }), [timeline, idx, hasTruth, truth]);
  const rulData = data.map((d) => ({ t: d.t, p50: d.r50, band: d.r90, band50: d.r50b, true: d.rtrue }));
  const rulMax = Math.min(60, Math.max(5, ...rulData.flatMap((d) => [d.band?.[1] ?? 0, d.true ?? 0])));

  const post = Object.entries(tw.posterior).sort((a, b) => b[1] - a[1]);
  const shown = post.slice(0, 6);
  const xAxis = <XAxis dataKey="t" type="number" domain={[0, maxT]} tickFormatter={clock} ticks={[0, 600, 1200, 1800, 2400, 3000, 3600].filter((x) => x <= maxT)} />;
  const truthX = hasTruth ? <ReferenceLine x={truth.fault_start_t} stroke="var(--warn)" strokeDasharray="4 3" /> : null;
  const detectX = firstDetect && firstDetect.t <= cur.t ? <ReferenceLine x={firstDetect.t} stroke="var(--accent-2)" strokeDasharray="2 3" strokeOpacity={0.7} label={{ value: 'twin detects', fill: 'var(--accent-2)', fontSize: 10, position: 'insideTopLeft' }} /> : null;
  const comp = COMPONENT[tw.map.fault];

  return (
    <div className="panel flagship mt">
      <div className="panel-title">
        <Atom size={15} /> Bayesian health twin
        <span className="badge b-info" style={{ marginLeft: 8 }}>flagship</span>
        <span className="right dim" style={{ fontSize: 11 }}>1,320 particles · 11 fault hypotheses · physics model in the loop</span>
      </div>

      <div className="grid g4" style={{ marginBottom: 14 }}>
        <div className="twin-stat">
          <span>P(component degraded)</span>
          <b style={{ color: detected ? 'var(--crit)' : tw.p_degraded > 0.5 ? 'var(--warn)' : 'var(--ok)' }}>{(tw.p_degraded * 100).toFixed(tw.p_degraded > 0.99 ? 1 : 0)}%</b>
        </div>
        <div className="twin-stat">
          <span>Hidden {detected ? comp : 'health'}</span>
          <b>{detected ? `${tw.health.p50.toFixed(2)}` : '≈ 1.00'}</b>
          {detected && <em>90% CI {tw.health.p5.toFixed(2)}–{tw.health.p95.toFixed(2)} · {(tw.rate_per_min ?? 0) * 100 > 0 ? `−${((tw.rate_per_min ?? 0) * 100).toFixed(1)}%/min` : ''}</em>}
        </div>
        <div className="twin-stat">
          <span><Hourglass size={12} /> RUL (median, 90% CI)</span>
          <b>{detected && tw.rul ? fmtDur(tw.rul.p50) : '—'}</b>
          {detected && tw.rul && <em>{fmtDur(tw.rul.p5)} – {fmtDur(tw.rul.p95)}</em>}
        </div>
        <div className="twin-stat">
          <span><GaugeIcon size={12} /> P(failure in next 1 h mission)</span>
          <b style={{ color: tw.p_fail_horizon >= 0.1 ? 'var(--crit)' : 'var(--ok)' }}>{(tw.p_fail_horizon * 100).toFixed(tw.p_fail_horizon > 0 && tw.p_fail_horizon < 0.1 ? 1 : 0)}%</b>
        </div>
      </div>

      <div className="grid" style={{ gridTemplateColumns: 'minmax(0,0.8fr) minmax(0,1.1fr) minmax(0,1.1fr)' }}>
        <div>
          <div className="sub-title"><Sigma size={13} /> Hypothesis posterior P(h | sensors)</div>
          {shown.map(([k, p]) => (
            <div key={k} className="diag-bar" style={{ gridTemplateColumns: '96px 1fr 48px' }}>
              <span>{HYP_LABEL[k]}</span>
              <div className="track"><div className="fill" style={{ width: `${p * 100}%`, background: k === 'healthy' ? 'var(--ok)' : p > 0.5 ? 'var(--crit)' : 'var(--accent-2)' }} /></div>
              <b className="mono" style={{ fontSize: 11 }}>{(p * 100).toFixed(p < 0.01 && p > 0 ? 2 : 1)}%</b>
            </div>
          ))}
          <div className="dim" style={{ fontSize: 11, marginTop: 10, lineHeight: 1.5 }}>
            Top 6 of 12 hypotheses. Each is a separate particle filter; Bayes&apos; rule weighs how well each explains every sensor reading, every second.
          </div>
        </div>
        <div>
          <div className="sub-title">Hidden health estimate {detected ? `(${comp})` : ''} · 90% credible band</div>
          <div style={{ height: 200 }}>
            <ResponsiveContainer>
              <ComposedChart data={data} margin={{ top: 6, right: 6, left: -22, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" />
                {xAxis}
                <YAxis domain={[0, 1]} ticks={[0, 0.25, 0.5, 0.75, 1]} />
                {truthX}{detectX}
                <Tooltip content={<Tip unit="" />} />
                <Area dataKey="band" stroke="none" fill="var(--accent-2)" fillOpacity={0.3} isAnimationActive={false} />
                <Line dataKey="p50" stroke="var(--accent-2)" strokeWidth={2} dot={false} isAnimationActive={false} />
                {hasTruth && <Line dataKey="true" stroke="var(--warn)" strokeDasharray="5 4" strokeWidth={1.6} dot={false} isAnimationActive={false} />}
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div>
          <div className="sub-title">RUL probability fan (min) · 50% / 90% intervals</div>
          <div style={{ height: 200 }}>
            <ResponsiveContainer>
              <ComposedChart data={rulData} margin={{ top: 6, right: 6, left: -22, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" />
                {xAxis}
                <YAxis domain={[0, Math.ceil(rulMax)]} allowDataOverflow />
                {truthX}{detectX}
                <Tooltip content={<Tip unit=" min" />} />
                <Area dataKey="band" stroke="none" fill="var(--warn)" fillOpacity={0.18} isAnimationActive={false} connectNulls={false} />
                <Area dataKey="band50" stroke="none" fill="var(--warn)" fillOpacity={0.3} isAnimationActive={false} connectNulls={false} />
                <Line dataKey="p50" stroke="var(--warn)" strokeWidth={2} dot={false} isAnimationActive={false} connectNulls={false} />
                {hasTruth && <Line dataKey="true" stroke="#fff" strokeDasharray="5 4" strokeWidth={1.4} dot={false} isAnimationActive={false} />}
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
      <div className="dim" style={{ fontSize: 11.5, marginTop: 8 }}>
        {hasTruth
          ? 'Dashed lines = hidden ground truth from the simulator (true health / true time to failure). The twin never sees these.'
          : 'Tick “Ground truth” in the playback bar to overlay the simulator’s hidden true health and true time to failure.'}
      </div>
    </div>
  );
}
