// Robustness section: (1) fair comparison of the three detectors at equal
// false-alarm rates, (2) how each degrades as the twin stops matching the
// engine (reality-gap study), with and without per-engine calibration.
import { useEffect, useState } from 'react';
import {
  CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import { FlaskConical, Scale, ShieldAlert } from 'lucide-react';
import { api } from '../api';
import { METHOD_COLORS, METHOD_LABEL, fmtDur, pct } from '../util';

const ORDER = ['ml', 'twin', 'cusum'];

function Tip({ active, payload, label, fmt }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="tt">
      <div className="dim" style={{ marginBottom: 4 }}>reality gap {Number(label).toFixed(2)}</div>
      {payload.map((p) => (
        <div key={p.dataKey}><span style={{ color: p.color }}>●</span> {p.name}: <b>{p.value == null ? '—' : fmt(p.value)}</b></div>
      ))}
    </div>
  );
}

const PANEL = '#0f1a30';

// One shared legend for the small multiples: swatch + name in text ink
function MethodLegend({ methods = ORDER }) {
  return (
    <div className="method-legend">
      {methods.map((m) => (
        <span key={m}><i style={{ background: METHOD_COLORS[m] }} />{METHOD_LABEL[m]}</span>
      ))}
    </div>
  );
}

function GapChart({ rows, metric, fmt, domain, title, note, methods = ORDER, refY }) {
  const data = rows.map((r) => ({
    gap: r.gap,
    ...Object.fromEntries(methods.map((m) => [m, metric(r[m])])),
  }));
  return (
    <div>
      <div className="sub-title">{title}</div>
      <div style={{ height: 210 }}>
        <ResponsiveContainer>
          <LineChart data={data} margin={{ top: 8, right: 16, left: -14, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="gap" type="number" domain={[0, 1]} ticks={[0, 0.1, 0.2, 0.35, 0.5, 0.75, 1]} tickFormatter={(v) => v.toFixed(2).replace(/0$/, '')} />
            <YAxis domain={domain} tickFormatter={fmt} />
            {refY != null && <ReferenceLine y={refY} stroke="var(--text-3)" strokeDasharray="4 3" label={{ value: 'nominal 90%', fill: 'var(--text-3)', fontSize: 10, position: 'insideBottomLeft' }} />}
            <Tooltip content={<Tip fmt={fmt} />} />
            {methods.map((m) => (
              <Line key={m} dataKey={m} name={METHOD_LABEL[m]} stroke={METHOD_COLORS[m]} strokeWidth={2}
                dot={{ r: 4, fill: METHOD_COLORS[m], strokeWidth: 2, stroke: PANEL }} activeDot={{ r: 5.5, fill: METHOD_COLORS[m], stroke: PANEL }}
                isAnimationActive={false} />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
      {note && <div className="dim" style={{ fontSize: 11.5, marginTop: 4, lineHeight: 1.5 }}>{note}</div>}
    </div>
  );
}

function AmocChart({ amoc }) {
  // one line per method: x = false-alarm events per healthy flight-hour (log), y = median delay
  const floor = 0.005;
  const series = ORDER.map((m) => ({
    m,
    pts: amoc.curves[m]
      .filter((p) => p.median_delay_s != null && p.detection >= 0.95)
      .map((p) => ({ far: Math.max(floor, p.far), farTrue: p.far, events: p.events, delay: p.median_delay_s, det: p.detection }))
      .sort((a, b) => a.far - b.far || a.delay - b.delay),
  }));
  return (
    <div style={{ height: 260 }}>
      <ResponsiveContainer>
        <LineChart margin={{ top: 4, right: 16, left: -6, bottom: 14 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="far" type="number" scale="log" domain={[floor, 'auto']} allowDataOverflow
            ticks={[0.005, 0.01, 0.1, 1, 10]} tickFormatter={(v) => (v <= floor ? '0' : v)}
            label={{ value: 'false-alarm events per healthy flight-hour (log)', position: 'insideBottom', offset: -4, fill: 'var(--text-3)', fontSize: 11 }} />
          <YAxis dataKey="delay" type="number" tickFormatter={(v) => `${v}s`} />
          <ReferenceLine x={amoc.target_far} stroke="var(--text-3)" strokeDasharray="4 3" label={{ value: `${amoc.target_far} /FH`, fill: 'var(--text-3)', fontSize: 10, position: 'insideTopRight' }} />
          <Tooltip content={({ active, payload }) => {
            if (!active || !payload?.length) return null;
            const p = payload[0].payload;
            return <div className="tt">{METHOD_LABEL[payload[0].payload.m || '']}{' '}<b>{p.events}</b> false-alarm events ({p.farTrue.toFixed(3)} /FH) · median delay <b>{fmtDur(p.delay)}</b> · detected {pct(p.det)}</div>;
          }} />
          <Legend verticalAlign="top" height={26} wrapperStyle={{ fontSize: 11 }} />
          {series.map(({ m, pts }) => (
            <Line key={m} data={pts.map((p) => ({ ...p, m }))} dataKey="delay" name={METHOD_LABEL[m]} stroke={METHOD_COLORS[m]}
              strokeWidth={2} dot={{ r: 3, fill: METHOD_COLORS[m], strokeWidth: 1.5, stroke: PANEL }} isAnimationActive={false} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export default function RobustnessStudy({ amoc, native }) {
  const [study, setStudy] = useState(null);
  const [missing, setMissing] = useState(false);
  const [cond, setCond] = useState('raw');
  useEffect(() => {
    api.gapStudy().then(setStudy).catch(() => setMissing(true));
  }, []);

  const rows = study?.conditions[cond];
  return (
    <div className="panel mt">
      <div className="panel-title"><ShieldAlert size={15} /> Robustness: a fair race, and what happens when the twin is wrong</div>

      {amoc && (
        <div className="grid" style={{ gridTemplateColumns: 'minmax(0,1.5fr) minmax(0,1fr)', gap: 22, marginBottom: 22 }}>
          <div>
            <div className="sub-title"><Scale size={13} /> Matched comparison on the test split: detection delay vs false-alarm rate</div>
            <AmocChart amoc={amoc} />
          </div>
          <div>
            <div className="sub-title">At ≤ {amoc.target_far} false-alarm events per flight-hour (≥ 95% detected)</div>
            <table className="t">
              <thead><tr><th>Method</th><th style={{ textAlign: 'right' }}>Median delay</th><th style={{ textAlign: 'right' }}>Detected</th></tr></thead>
              <tbody>
                {ORDER.map((m) => {
                  const p = amoc.at_target[m];
                  return (
                    <tr key={m}>
                      <td><span style={{ color: METHOD_COLORS[m] }}>●</span> {METHOD_LABEL[m]}</td>
                      <td className="num">{p ? fmtDur(p.median_delay_s) : 'not reachable'}</td>
                      <td className="num">{p ? pct(p.detection) : '—'}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {native && (
              <div className="dim" style={{ fontSize: 11.5, marginTop: 8, lineHeight: 1.5 }}>
                The ML ensemble&apos;s fused score fluctuates too much for a 3-window rule. With its own deployed rule (HI &lt; 50 for 8
                windows) it reaches {native.far.toFixed(3)} events/FH with {pct(native.detection)} detected and a {fmtDur(native.delay)} median delay.
              </div>
            )}
            <div className="note mt">
              Each method&apos;s threshold is swept with the same 3-window persistence. With an exact twin, healthy residuals are white
              noise, and textbook CUSUM is the optimal detector for exactly that case. The ML ensemble&apos;s value is not speed here;
              the reality-gap study below shows where each one breaks.
            </div>
          </div>
        </div>
      )}

      <div className="sub-title" style={{ justifyContent: 'space-between' }}>
        <span><FlaskConical size={13} /> Reality-gap study: the simulated engine departs from the twin (offsets, gains, time constants, sensor bias, drift, coloured noise)</span>
        <span className="seg">
          <button className={cond === 'raw' ? 'on' : ''} onClick={() => setCond('raw')}>Uncalibrated twin</button>
          <button className={cond === 'calibrated' ? 'on' : ''} onClick={() => setCond('calibrated')}>Per-engine calibration</button>
        </span>
      </div>
      {missing && <div className="dim">Run <span className="mono">python3 -m aerotwin.evaluation.gap_study</span> to build this study.</div>}
      {rows && (
        <>
          <div className="gap-headline">
            Stays usable (≤ 5% of healthy flight time in false alarm and ≥ 90% of faults caught) up to a reality gap of:
            {ORDER.map((m) => {
              const ok = rows.filter((r) => r[m].healthy_alarm_fraction <= 0.05 && r[m].detection.rate >= 0.9);
              // largest gap level reached without ever failing at a smaller one
              let last = null;
              for (const r of rows) { if (ok.includes(r)) last = r.gap; else break; }
              return <b key={m}><i style={{ background: METHOD_COLORS[m] }} />{METHOD_LABEL[m]} {last == null ? '—' : last.toFixed(2)}</b>;
            })}
          </div>
          <MethodLegend />
          <div className="grid g2 mt">
            <GapChart rows={rows} title="Healthy flight time spent in false alarm (lower is better)"
              metric={(x) => x.healthy_alarm_fraction * 100} fmt={(v) => `${Math.round(v)}%`} domain={[0, 100]} />
            <GapChart rows={rows} title="Faults caught by a new alarm before failure (higher is better)"
              metric={(x) => x.detection.rate * 100} fmt={(v) => `${Math.round(v)}%`} domain={[0, 100]}
              note="A method already alarming when the fault starts earns no credit; that is why detection falls when false alarms saturate." />
          </div>
          <div className="grid g2 mt">
            <GapChart rows={rows} title="Correct diagnosis (fault type + cylinder) at first detection"
              metric={(x) => (x.diagnosis == null ? null : x.diagnosis * 100)} fmt={(v) => `${Math.round(v)}%`} domain={[0, 100]}
              methods={['ml', 'twin']} note="ML = physics-signature rules at the first ML alert; twin = most probable hypothesis. CUSUM does not diagnose." />
            <GapChart rows={rows} title="Bayesian twin: 90% RUL interval coverage" refY={90}
              metric={(x) => (x.coverage90 == null ? null : x.coverage90 * 100)} fmt={(v) => `${Math.round(v)}%`} domain={[0, 100]}
              methods={['twin']} note="Below the dashed line = over-confident. The filter's uncertainty does not yet include model mismatch." />
          </div>
          <div className="dim" style={{ fontSize: 11.5, marginTop: 10, lineHeight: 1.6 }}>
            Paired design: the same {study.n_healthy} healthy and {study.n_fault} fault flights at every gap level (identical noise, onsets and
            engine identities); only the mismatch magnitude changes. Thresholds are the deployed ones, fixed before the study.
            Per-engine calibration subtracts the mean residual of one healthy reference flight of the same engine.
          </div>
        </>
      )}
    </div>
  );
}
