import { useEffect, useMemo, useState } from 'react';
import {
  Area, Bar, BarChart, CartesianGrid, Cell, ComposedChart, Line, LineChart, ReferenceArea, ReferenceLine,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import {
  Activity, Atom, Brain, CircleAlert, CircleCheck, CircleX, Clock, Cpu, Droplet, Eye, FastForward, FileText,
  Fuel, Gauge as GaugeIcon, Layers, Mountain, Pause, Play, RotateCcw, ShieldCheck, Siren, Thermometer,
  TriangleAlert, Waves, Wrench,
} from 'lucide-react';
import Gauge from './Gauge';
import EngineDiagram from './EngineDiagram';
import BayesianTwin from './BayesianTwin';
import XaiPanel from './XaiPanel';
import { FAULT_SHORT, HYP_LABEL, MODEL_COLORS, clock, fmtDur, hiColor } from '../util';

const SPEEDS = [
  { label: '1×', wps: 2 },
  { label: '4×', wps: 8 },
  { label: '10×', wps: 20 },
  { label: '30×', wps: 60 },
];

const SIGNALS = {
  cht: { label: 'CHT (per cylinder)', unit: '°C', cyl: 'cht', exp: 'cht' },
  egt: { label: 'EGT (per cylinder)', unit: '°C', cyl: 'egt', exp: 'egt' },
  oil_press_bar: { label: 'Oil pressure', unit: 'bar', key: 'oil_press_bar', exp: 'oil_press_bar' },
  oil_temp_c: { label: 'Oil temperature', unit: '°C', key: 'oil_temp_c', exp: 'oil_temp_c' },
  vib_rms_g: { label: 'Vibration', unit: 'g RMS', key: 'vib_rms_g', exp: 'vib_rms_g' },
};
const CYL_COLORS = ['#38bdf8', '#f472b6', '#a3e635', '#fbbf24'];

const Z_CHANNELS = [
  ['oil_press_bar', 'Oil P'], ['oil_temp_c', 'Oil T'], ['fuel_flow_lph', 'Fuel'], ['vib_rms_g', 'Vib'],
  ['cht_1', 'CHT1'], ['cht_2', 'CHT2'], ['cht_3', 'CHT3'], ['cht_4', 'CHT4'],
  ['egt_1', 'EGT1'], ['egt_2', 'EGT2'], ['egt_3', 'EGT3'], ['egt_4', 'EGT4'],
];

function ChartTip({ active, payload, label, unit = '' }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="tt">
      <div className="dim" style={{ marginBottom: 4 }}>T+{clock(label)}</div>
      {payload.filter((p) => p.value != null).map((p) => (
        <div key={p.dataKey} style={{ color: p.color || p.stroke }}>
          {p.name}: <b>{typeof p.value === 'number' ? p.value.toFixed(1) : p.value}</b> {unit}
        </div>
      ))}
    </div>
  );
}

function buildEvents(tl) {
  const ev = [];
  let phase = null, degr = false, diag = null, alert = false, dec = null, twinDet = false;
  tl.forEach((r, i) => {
    if (r.twin && r.twin.p_degraded > 0.95 && !twinDet) {
      const m = r.twin.map;
      const key = m.cylinder ? `${m.fault}:${m.cylinder}` : m.fault;
      ev.push({ i, t: r.t, kind: 'twin', text: `Bayesian twin: ${HYP_LABEL[key]} degraded (P=${(r.twin.p_degraded * 100).toFixed(0)}%, health ${r.twin.health.p50.toFixed(2)})` });
      twinDet = true;
    }
    if (r.phase && r.phase !== phase) {
      ev.push({ i, t: r.t, kind: 'info', text: `Flight phase: ${r.phase.toUpperCase()}` });
      phase = r.phase;
    }
    if (r.degrading && !degr) ev.push({ i, t: r.t, kind: 'warn', text: `Health degrading – HI ${r.hi.toFixed(0)} below 80 (sustained)` });
    degr = r.degrading;
    if (r.diagnosis && r.diagnosis.fault !== diag) {
      ev.push({
        i, t: r.t, kind: 'diag',
        text: `Diagnosis: ${r.diagnosis.label}${r.diagnosis.cylinder ? `, cylinder ${r.diagnosis.cylinder}` : ''} (${(r.diagnosis.confidence * 100).toFixed(0)}% conf.)`,
      });
      diag = r.diagnosis.fault;
    }
    if (r.alert && !alert) ev.push({ i, t: r.t, kind: 'crit', text: `ALERT – Health Index below 50 for 8 consecutive windows` });
    alert = r.alert;
    if (r.advisor.decision !== dec) {
      if (dec !== null) ev.push({ i, t: r.t, kind: r.advisor.decision === 'GO' ? 'ok' : r.advisor.decision === 'CAUTION' ? 'warn' : 'crit', text: `Mission advisor → ${r.advisor.decision}` });
      dec = r.advisor.decision;
    }
  });
  return ev;
}

const TOAST_KINDS = new Set(['twin', 'crit', 'diag']);
const TOAST_TITLE = { twin: 'Bayesian twin', crit: 'Alert', diag: 'Signature check' };

const EV_ICON = {
  info: <Clock size={14} color="var(--text-3)" />,
  warn: <TriangleAlert size={14} color="var(--warn)" />,
  diag: <Brain size={14} color="var(--accent-2)" />,
  twin: <Atom size={14} color="var(--accent-2)" />,
  crit: <Siren size={14} color="var(--crit)" />,
  ok: <CircleCheck size={14} color="var(--ok)" />,
};

function openReport({ title, cur, timeline, truth, events }) {
  const minHi = Math.min(...timeline.map((r) => r.hi_smooth));
  const firstAlert = timeline.find((r) => r.alert);
  const d = cur.diagnosis || [...timeline].reverse().find((r) => r.diagnosis)?.diagnosis;
  const w = window.open('', '_blank');
  if (!w) return;
  w.document.write(`<!doctype html><html><head><title>Maintenance report – ${title}</title>
  <style>body{font-family:Inter,Arial,sans-serif;max-width:820px;margin:40px auto;color:#0f172a;line-height:1.5}
  h1{margin:0;font-size:24px}h2{font-size:15px;text-transform:uppercase;letter-spacing:.6px;color:#334155;border-bottom:2px solid #e2e8f0;padding-bottom:4px;margin-top:28px}
  table{border-collapse:collapse;width:100%;font-size:13px}td{padding:6px 8px;border-bottom:1px solid #e2e8f0}td:first-child{color:#64748b;width:42%}
  .dec{display:inline-block;padding:6px 14px;border-radius:6px;font-weight:800;color:#fff;background:${cur.advisor.decision === 'GO' ? '#16a34a' : cur.advisor.decision === 'CAUTION' ? '#d97706' : '#dc2626'}}
  .foot{margin-top:30px;font-size:11px;color:#64748b}</style></head><body>
  <div style="display:flex;justify-content:space-between;align-items:center"><div><div style="color:#0284c7;font-weight:700;font-size:12px;letter-spacing:1px">AEROTWIN · ENGINE HEALTH MAINTENANCE REPORT</div><h1>${title}</h1>
  <div style="color:#64748b;font-size:13px">Generated ${new Date().toLocaleString()} · Engine: Rotax 912 S/ULS class</div></div><div class="dec">${cur.advisor.decision}</div></div>
  <h2>Engine health summary</h2><table>
  <tr><td>Flight time analysed</td><td>${clock(cur.t)} (${timeline.length} windows of 60 s, 10 s stride)</td></tr>
  <tr><td>Health Index (current / minimum)</td><td>${cur.hi_smooth.toFixed(1)} / ${minHi.toFixed(1)}</td></tr>
  <tr><td>First sustained alert</td><td>${firstAlert ? 'T+' + clock(firstAlert.t) : 'None'}</td></tr>
  <tr><td>Remaining useful life (estimate)</td><td>${cur.rul_s != null ? fmtDur(cur.rul_s) : 'Not estimable (no sustained degradation trend)'}</td></tr>
  ${truth?.fault_type ? `<tr><td>Ground truth (simulation)</td><td>${truth.fault_type} injected at T+${clock(truth.fault_start_t)}, functional failure at T+${clock(truth.failure_t)}</td></tr>` : ''}
  </table>
  ${cur.twin ? `<h2>Bayesian health twin</h2><table>
  <tr><td>P(component degraded)</td><td>${(cur.twin.p_degraded * 100).toFixed(1)}%</td></tr>
  ${cur.twin.p_degraded > 0.95 ? `<tr><td>Most probable hypothesis</td><td><b>${HYP_LABEL[cur.twin.map.cylinder ? cur.twin.map.fault + ':' + cur.twin.map.cylinder : cur.twin.map.fault]}</b> (${(cur.twin.map.prob * 100).toFixed(0)}%)</td></tr>
  <tr><td>Estimated component health</td><td>${cur.twin.health.p50.toFixed(3)} (90% CI ${cur.twin.health.p5.toFixed(3)}–${cur.twin.health.p95.toFixed(3)})</td></tr>
  ${cur.twin.rul ? `<tr><td>RUL (median, 90% CI)</td><td>${fmtDur(cur.twin.rul.p50)} (${fmtDur(cur.twin.rul.p5)} – ${fmtDur(cur.twin.rul.p95)})</td></tr>` : ''}` : ''}
  <tr><td>P(failure within next 1 h mission)</td><td>${(cur.twin.p_fail_horizon * 100).toFixed(1)}%</td></tr></table>` : ''}
  <h2>Fault diagnosis</h2>${d ? `<table><tr><td>Fault</td><td><b>${d.label}</b>${d.cylinder ? ' – cylinder ' + d.cylinder : ''}</td></tr>
  <tr><td>Confidence</td><td>${(d.confidence * 100).toFixed(0)}%</td></tr><tr><td>Evidence</td><td>${d.evidence}</td></tr>
  <tr><td>Recommended action</td><td><b>${d.action}</b></td></tr></table>` : '<p>No fault signature detected. All 15 residual channels within healthy bounds.</p>'}
  <h2>Mission advisor</h2><ul>${cur.advisor.reasons.map((r) => `<li>${r}</li>`).join('')}</ul>
  <h2>Event log</h2><table>${events.filter((e) => e.i <= timeline.indexOf(cur)).map((e) => `<tr><td>T+${clock(e.t)}</td><td>${e.text}</td></tr>`).join('')}</table>
  <div class="foot">Prototype decision-support output from a physics-informed digital twin trained on simulated data. Not a certified airworthiness determination.</div>
  <script>setTimeout(()=>print(),300)</script></body></html>`);
  w.document.close();
}

export default function TwinViewer({ timeline, truth, title, subtitle, autoplay = true, startAtEnd = false }) {
  const n = timeline.length;
  const [idx, setIdx] = useState(startAtEnd ? n - 1 : 0);
  const [playing, setPlaying] = useState(autoplay && !startAtEnd);
  const running = playing && idx < n - 1; // playback stops itself at end of flight
  const [speed, setSpeed] = useState(1);
  const [showTruth, setShowTruth] = useState(false);
  const [signal, setSignal] = useState('cht');

  useEffect(() => {
    if (!running) return undefined;
    const id = setInterval(() => setIdx((i) => Math.min(i + 1, n - 1)), 1000 / SPEEDS[speed].wps);
    return () => clearInterval(id);
  }, [running, speed, n]);

  const events = useMemo(() => buildEvents(timeline), [timeline]);
  const maxT = timeline[n - 1]?.t ?? 3600;
  const cur = timeline[Math.min(idx, n - 1)];
  // detector percentiles on healthy data are uniform noise by construction;
  // a 6-window (60 s) rolling mean makes the trend readable
  const smoothScores = useMemo(() => {
    const keys = ['IF', 'PCA', 'LSTM', 'fused'];
    return timeline.map((_, i) => {
      const win = timeline.slice(Math.max(0, i - 5), i + 1);
      return Object.fromEntries(keys.map((k) => [k, win.reduce((a, r) => a + (k === 'fused' ? r.fused : r.scores[k]), 0) / win.length]));
    });
  }, [timeline]);
  const hist = useMemo(
    () => timeline.slice(0, idx + 1).map((r, i) => ({
      t: r.t, hi: r.hi, hi_smooth: r.hi_smooth, ...smoothScores[i],
      ...Object.fromEntries([1, 2, 3, 4].flatMap((c) => [[`cht_${c}`, r[`cht_${c}`]], [`egt_${c}`, r[`egt_${c}`]]])),
      oil_press_bar: r.oil_press_bar, oil_temp_c: r.oil_temp_c, vib_rms_g: r.vib_rms_g,
      exp_cht: r.exp.cht, exp_egt: r.exp.egt, exp_oil_press_bar: r.exp.oil_press_bar,
      exp_oil_temp_c: r.exp.oil_temp_c, exp_vib_rms_g: r.exp.vib_rms_g,
    })),
    [timeline, idx, smoothScores],
  );
  const firstAlert = timeline.find((r) => r.alert);
  const alertVisible = firstAlert && firstAlert.t <= cur.t;
  const zData = Z_CHANNELS.map(([k, label]) => ({ label, z: cur.z?.[k] ?? 0 }));
  const diag = cur.diagnosis;
  const twinDetected = cur.twin && cur.twin.p_degraded > 0.95;
  const twinRul = twinDetected ? cur.twin.rul : null;
  const flagFault = twinDetected ? cur.twin.map.fault : diag?.fault;
  const flagCyl = twinDetected ? cur.twin.map.cylinder : diag?.cylinder;
  const maxScore = diag ? Math.max(...Object.values(diag.scores), 1) : 1;
  const sig = SIGNALS[signal];
  const evNow = events.filter((e) => e.i <= idx).reverse();
  // Explanation shown: this window's, or (while health is still degraded) the
  // most recent flagged window. Raw per-window HI can briefly bounce above 80
  // inside a degraded stretch, which would otherwise blank the panel.
  let xaiRow = cur.xai ? cur : null;
  if (!xaiRow && (cur.hi_smooth < 80 || cur.alert)) {
    for (let k = idx - 1; k >= Math.max(0, idx - 30); k -= 1) {
      if (timeline[k].xai) { xaiRow = timeline[k]; break; }
    }
  }
  // Pop-up notifications: derived from playback position, so each event
  // shows for ~4 s of wall time while the replay runs past it.
  const toastSpan = SPEEDS[speed].wps * 4;
  const toasts = running ? events.filter((e) => TOAST_KINDS.has(e.kind) && e.i <= idx && e.i > idx - toastSpan).slice(-3) : [];

  // Keyboard: space play/pause, arrows step (shift = 10), Home/End jump
  useEffect(() => {
    const onKey = (e) => {
      if (['INPUT', 'SELECT', 'TEXTAREA'].includes(e.target.tagName)) return;
      const step = e.shiftKey ? 10 : 1;
      if (e.code === 'Space') {
        e.preventDefault();
        if (idx >= n - 1) { setIdx(0); setPlaying(true); } else setPlaying(!running);
      } else if (e.key === 'ArrowRight') { setPlaying(false); setIdx(Math.min(n - 1, idx + step)); }
      else if (e.key === 'ArrowLeft') { setPlaying(false); setIdx(Math.max(0, idx - step)); }
      else if (e.key === 'Home') { setIdx(0); }
      else if (e.key === 'End') { setPlaying(false); setIdx(n - 1); }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [idx, n, running]);

  const marks = [];
  if (showTruth && truth?.fault_start_t != null) {
    marks.push({ t: truth.fault_start_t, color: 'var(--warn)', label: 'onset' });
    marks.push({ t: truth.failure_t, color: 'var(--crit)', label: 'failure' });
  }
  if (firstAlert) marks.push({ t: firstAlert.t, color: 'var(--accent)', label: 'alert' });

  const xAxis = <XAxis dataKey="t" type="number" domain={[0, maxT]} tickFormatter={clock} ticks={[0, 600, 1200, 1800, 2400, 3000, 3600].filter((x) => x <= maxT)} />;
  const truthLines = showTruth && truth?.fault_start_t != null ? [
    <ReferenceArea key="ra" x1={truth.fault_start_t} x2={Math.min(truth.failure_t, maxT)} fill="rgba(245,158,11,.06)" />,
    <ReferenceLine key="on" x={truth.fault_start_t} stroke="var(--warn)" strokeDasharray="4 3" label={{ value: 'fault onset (truth)', fill: 'var(--warn)', fontSize: 10, position: 'insideTopRight' }} />,
    truth.failure_t <= maxT && <ReferenceLine key="fl" x={truth.failure_t} stroke="var(--crit)" strokeDasharray="4 3" label={{ value: 'failure (truth)', fill: 'var(--crit)', fontSize: 10, position: 'insideTopLeft' }} />,
  ] : [];

  return (
    <div>
      <div className="toasts" aria-live="polite">
        {toasts.map((e) => (
          <div key={`${e.i}-${e.text}`} className={`toast ${e.kind}`}>
            {EV_ICON[e.kind]}
            <div><b>{TOAST_TITLE[e.kind]}</b>{e.text.replace(/^(Bayesian twin|Diagnosis): /, '')}<br /><time>T+{clock(e.t)}</time></div>
          </div>
        ))}
      </div>
      {/* playback */}
      <div className="panel playbar">
        <button className="btn icon primary" onClick={() => { if (idx >= n - 1) { setIdx(0); setPlaying(true); } else setPlaying(!running); }} title={running ? 'Pause' : 'Play'}>
          {running ? <Pause size={18} /> : <Play size={18} />}
        </button>
        <button className="btn icon" onClick={() => { setIdx(0); setPlaying(true); }} title="Restart"><RotateCcw size={16} /></button>
        <div>
          <div className="clock">T+{clock(cur.t)}<span className={`rec-chip ${running ? '' : 'paused'}`}><i />{running ? 'REPLAY' : 'PAUSED'}</span></div>
          <div className="dim" style={{ fontSize: 11 }}>{title}{subtitle ? ` · ${subtitle}` : ''}</div>
          <div className="kbd-hint" style={{ marginTop: 3 }}><kbd>Space</kbd> play/pause · <kbd>←</kbd><kbd>→</kbd> step · <kbd>⇧</kbd> ×10</div>
        </div>
        <div className="scrub">
          <input type="range" min={0} max={n - 1} value={idx} onChange={(e) => { setIdx(+e.target.value); setPlaying(false); }} />
          <div className="scrub-marks">
            {marks.map((m) => (
              <div key={m.label} className="scrub-mark" style={{ left: `${(Math.min(m.t, maxT) / maxT) * 100}%`, background: m.color }}>
                <span style={{ color: m.color }}>{m.label}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="seg" title="Playback speed">
          {SPEEDS.map((s, i) => (
            <button key={s.label} className={speed === i ? 'on' : ''} onClick={() => setSpeed(i)}>{s.label}</button>
          ))}
        </div>
        <FastForward size={14} className="dim" />
        <button className="btn icon" title="Jump to end of flight" onClick={() => { setIdx(n - 1); setPlaying(false); }}>⏭</button>
        {truth?.fault_type && (
          <label className="toggle" title="Overlay the simulator's hidden ground truth (fault onset & failure time)">
            <input type="checkbox" checked={showTruth} onChange={(e) => setShowTruth(e.target.checked)} />
            <Eye size={14} /> Ground truth
          </label>
        )}
        <button className="btn" onClick={() => openReport({ title, cur, timeline, truth, events })}><FileText size={15} /> Report</button>
      </div>

      {/* top row */}
      <div className="twin-top mt">
        <div className="panel">
          {running && <div className="scan" />}
          <div className="panel-title"><Cpu size={15} /> Engine twin <span className="right badge b-mute">{cur.phase || '—'}</span></div>
          <EngineDiagram row={cur} flaggedCyl={flagCyl} flaggedSystem={flagFault} />
        </div>

        <div className="panel">
          <div className="panel-title"><Activity size={15} /> Health & prognostics</div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
            <div style={{ fontSize: 56, fontWeight: 800, color: hiColor(cur.hi_smooth), letterSpacing: -2, fontVariantNumeric: 'tabular-nums', lineHeight: 1 }}>
              {cur.hi_smooth.toFixed(0)}
            </div>
            <div className="muted" style={{ fontSize: 13 }}>Health Index<br /><span className="dim">0 = failed · 100 = as-new</span></div>
          </div>
          <div style={{ height: 8, background: 'var(--bg-2)', borderRadius: 4, margin: '12px 0 8px', overflow: 'hidden' }}>
            <div style={{ height: '100%', width: `${cur.hi_smooth}%`, background: hiColor(cur.hi_smooth), transition: 'width .25s, background .25s', borderRadius: 4 }} />
          </div>
          <div className="stat-row"><span>Remaining useful life</span>{twinRul
            ? <b style={{ color: 'var(--warn)' }}>≈ {fmtDur(twinRul.p50)} <span className="dim" style={{ fontWeight: 400 }}>({fmtDur(twinRul.p5)}–{fmtDur(twinRul.p95)})</span></b>
            : cur.alert
            ? <b style={{ color: 'var(--crit)' }}>Threshold reached</b>
            : <b style={{ color: cur.rul_s != null ? 'var(--warn)' : 'var(--ok)' }}>{cur.rul_s != null ? `≈ ${fmtDur(cur.rul_s)}` : 'Stable'}</b>}</div>
          <div className="stat-row"><span>Fused anomaly percentile</span><b>{cur.fused.toFixed(0)}<span className="dim">/100</span></b></div>
          <div className="stat-row"><span>ML ensemble alert</span>{cur.alert ? <span className="badge b-crit">Alert</span> : cur.alert_latched ? <span className="badge b-crit">Latched</span> : cur.degrading ? <span className="badge b-warn">Degrading</span> : <span className="badge b-ok">Nominal</span>}</div>
          <div className="stat-row"><span>Altitude · Throttle</span><b>{cur.altitude_ft.toFixed(0)} ft · {cur.throttle_pct.toFixed(0)}%</b></div>
          <div className={`decision d-${cur.advisor.decision} mt`}>
            <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: 1, opacity: .85 }}>NEXT-MISSION ADVISOR</div>
            <h3>{cur.advisor.decision === 'GO' ? <ShieldCheck /> : cur.advisor.decision === 'CAUTION' ? <TriangleAlert /> : <CircleX />}{cur.advisor.decision}</h3>
            <ul>{cur.advisor.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
          </div>
        </div>

        <div className="panel">
          <div className="panel-title"><Brain size={15} /> Fault signature check</div>
          {diag ? (
            <div className="diag-box">
              <div className="dim" style={{ fontSize: 11, fontWeight: 700, letterSpacing: 1 }}>MOST LIKELY FAULT</div>
              <div className="diag-name">{diag.label}{diag.cylinder ? ` · Cyl ${diag.cylinder}` : ''}</div>
              <div style={{ fontSize: 12.5, marginTop: 6 }} className="muted">{diag.evidence}</div>
              <div style={{ marginTop: 10 }}>
                {Object.entries(diag.scores).sort((a, b) => b[1] - a[1]).map(([k, v]) => (
                  <div key={k} className="diag-bar">
                    <span>{FAULT_SHORT[k]}</span>
                    <div className="track"><div className="fill" style={{ width: `${(v / maxScore) * 100}%`, background: k === diag.fault ? 'var(--crit)' : 'var(--border-2)' }} /></div>
                    <b className="mono" style={{ fontSize: 11 }}>{v.toFixed(1)}σ</b>
                  </div>
                ))}
              </div>
              <div style={{ marginTop: 12, display: 'flex', gap: 8, fontSize: 12.5 }}>
                <Wrench size={16} color="var(--warn)" style={{ flexShrink: 0, marginTop: 2 }} />
                <span><b>Action:</b> {diag.action}</span>
              </div>
            </div>
          ) : (
            <div style={{ textAlign: 'center', padding: '24px 8px' }}>
              <CircleCheck size={42} color="var(--ok)" />
              <div style={{ fontWeight: 700, marginTop: 10 }}>{twinDetected ? 'Awaiting ML confirmation' : 'No fault signature'}</div>
              <div className="muted" style={{ fontSize: 12.5, marginTop: 6, lineHeight: 1.5 }}>
                {twinDetected
                  ? 'The Bayesian twin (below) has already isolated the fault. This rule-based signature check engages once the ML Health Index degrades, as an independent second opinion.'
                  : '15 residual channels (measured − healthy twin) are monitored. The signature check engages once the Health Index shows sustained degradation.'}
              </div>
            </div>
          )}
          <div className="panel-title mt" style={{ marginBottom: 6 }}><Layers size={15} /> Residuals now (σ from healthy)</div>
          <div style={{ height: 170 }}>
            <ResponsiveContainer>
              <BarChart data={zData} margin={{ top: 4, right: 4, left: -26, bottom: 0 }}>
                <CartesianGrid vertical={false} />
                <XAxis dataKey="label" interval={0} tick={{ fontSize: 9 }} angle={-50} textAnchor="end" height={34} />
                <YAxis domain={[-8, 8]} allowDataOverflow ticks={[-6, -3, 0, 3, 6]} />
                <ReferenceLine y={3} stroke="var(--warn)" strokeDasharray="3 3" />
                <ReferenceLine y={-3} stroke="var(--warn)" strokeDasharray="3 3" />
                <Bar dataKey="z" isAnimationActive={false} radius={[3, 3, 3, 3]}>
                  {zData.map((d) => <Cell key={d.label} fill={Math.abs(d.z) > 3 ? 'var(--crit)' : Math.abs(d.z) > 1.5 ? 'var(--warn)' : 'var(--accent)'} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <BayesianTwin timeline={timeline} idx={idx} truth={truth} showTruth={showTruth} maxT={maxT} />

      {/* gauges */}
      <div className="grid g6 mt">
        <Gauge label="Engine speed" icon={GaugeIcon} value={cur.rpm} unit="rpm" min={0} max={6000} bands={[{ to: 1400, color: 'var(--warn)' }, { to: 5500, color: 'var(--ok)' }, { to: 5800, color: 'var(--warn)' }, { to: 6000, color: 'var(--crit)' }]} />
        <Gauge label="Oil pressure" icon={Droplet} value={cur.oil_press_bar} expected={cur.exp.oil_press_bar} unit="bar" min={0} max={8} decimals={2} bands={[{ to: 0.8, color: 'var(--crit)' }, { to: 2, color: 'var(--warn)' }, { to: 5, color: 'var(--ok)' }, { to: 7, color: 'var(--warn)' }, { to: 8, color: 'var(--crit)' }]} />
        <Gauge label="Oil temp" icon={Thermometer} value={cur.oil_temp_c} expected={cur.exp.oil_temp_c} unit="°C" min={20} max={150} bands={[{ to: 50, color: 'var(--warn)' }, { to: 110, color: 'var(--ok)' }, { to: 130, color: 'var(--warn)' }, { to: 150, color: 'var(--crit)' }]} />
        <Gauge label="CHT (max)" icon={Thermometer} value={Math.max(cur.cht_1, cur.cht_2, cur.cht_3, cur.cht_4)} expected={cur.exp.cht} unit="°C" min={20} max={160} bands={[{ to: 120, color: 'var(--ok)' }, { to: 135, color: 'var(--warn)' }, { to: 160, color: 'var(--crit)' }]} />
        <Gauge label="Vibration" icon={Waves} value={cur.vib_rms_g} expected={cur.exp.vib_rms_g} unit="g RMS" min={0} max={8} decimals={2} bands={[{ to: 4, color: 'var(--ok)' }, { to: 6, color: 'var(--warn)' }, { to: 8, color: 'var(--crit)' }]} />
        <Gauge label="Fuel flow" icon={Fuel} value={cur.fuel_flow_lph} expected={cur.exp.fuel_flow_lph} unit="L/h" min={0} max={30} decimals={1} bands={[{ to: 30, color: 'var(--accent)' }]} />
      </div>

      <XaiPanel row={cur} explained={xaiRow} />

      {/* charts */}
      <div className="grid g2 mt">
        <div className="panel">
          <div className="panel-title"><Activity size={15} /> Health Index timeline
            <span className="right dim" style={{ fontSize: 11 }}>— smoothed · ┄ raw · thresholds 80 / 50</span></div>
          <div style={{ height: 250 }}>
            <ResponsiveContainer>
              <ComposedChart data={hist} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="hig" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0" stopColor="var(--accent)" stopOpacity=".35" />
                    <stop offset="1" stopColor="var(--accent)" stopOpacity="0" />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" />
                {xAxis}
                <YAxis domain={[0, 100]} />
                <ReferenceArea y1={0} y2={50} fill="rgba(239,68,68,.05)" />
                <ReferenceLine y={80} stroke="var(--warn)" strokeDasharray="4 3" />
                <ReferenceLine y={50} stroke="var(--crit)" strokeDasharray="4 3" />
                {truthLines}
                {alertVisible && <ReferenceLine x={firstAlert.t} stroke="var(--accent)" label={{ value: 'first alert', fill: 'var(--accent)', fontSize: 10, position: 'insideBottomLeft' }} />}
                <Tooltip content={<ChartTip />} />
                <Line dataKey="hi" name="HI raw" stroke="rgba(147,164,195,.45)" dot={false} strokeWidth={1} isAnimationActive={false} />
                <Area dataKey="hi_smooth" name="HI" stroke="var(--accent)" fill="url(#hig)" strokeWidth={2.5} dot={false} isAnimationActive={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="panel">
          <div className="panel-title"><Brain size={15} /> Detector ensemble
            <span className="right dim" style={{ fontSize: 11 }}>percentile vs healthy flights · 60 s mean</span></div>
          <div style={{ height: 250 }}>
            <ResponsiveContainer>
              <LineChart data={hist} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" />
                {xAxis}
                <YAxis domain={[0, 100]} />
                {truthLines}
                <Tooltip content={<ChartTip />} />
                {['IF', 'PCA', 'LSTM'].map((m) => (
                  <Line key={m} dataKey={m} name={{ IF: 'Isolation Forest', PCA: 'PCA-SPE', LSTM: 'LSTM-AE' }[m]} stroke={MODEL_COLORS[m]} dot={false} strokeWidth={1.4} strokeOpacity={0.8} isAnimationActive={false} />
                ))}
                <Line dataKey="fused" name="Fused" stroke="#fff" dot={false} strokeWidth={2.2} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="grid mt" style={{ gridTemplateColumns: 'minmax(0,1.6fr) minmax(0,1fr)' }}>
        <div className="panel">
          <div className="panel-title"><Mountain size={15} /> Measured vs digital twin
            <span className="right">
              <span className="seg">
                {Object.entries(SIGNALS).map(([k, s]) => (
                  <button key={k} className={signal === k ? 'on' : ''} onClick={() => setSignal(k)}>{s.label.split(' (')[0]}</button>
                ))}
              </span>
            </span>
          </div>
          <div style={{ height: 270 }}>
            <ResponsiveContainer>
              <LineChart data={hist} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" />
                {xAxis}
                <YAxis domain={['auto', 'auto']} />
                {truthLines}
                <Tooltip content={<ChartTip unit={sig.unit} />} />
                {sig.cyl
                  ? [1, 2, 3, 4].map((c) => (
                    <Line key={c} dataKey={`${sig.cyl}_${c}`} name={`Cyl ${c}`} stroke={CYL_COLORS[c - 1]} dot={false} strokeWidth={1.6} isAnimationActive={false} />
                  ))
                  : <Line dataKey={sig.key} name="Measured" stroke="var(--accent)" dot={false} strokeWidth={2} isAnimationActive={false} />}
                <Line dataKey={`exp_${sig.exp}`} name="Healthy twin" stroke="#fff" strokeDasharray="5 4" dot={false} strokeWidth={1.6} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div className="dim" style={{ fontSize: 11.5, marginTop: 6 }}>
            Dashed white = what a perfectly healthy engine would read under the same RPM, throttle, altitude and ambient temperature (physics model with thermal lag). The gap is the residual the AI models analyse.
          </div>
        </div>

        <div className="panel">
          <div className="panel-title"><CircleAlert size={15} /> Event log <span className="right dim">{evNow.length} events</span></div>
          <div className="log">
            {evNow.length === 0 && <div className="dim">Waiting for events…</div>}
            {evNow.map((e) => (
              <div key={`${e.i}-${e.text}`} className="log-item">
                <time>T+{clock(e.t)}</time>
                {EV_ICON[e.kind]}
                <span style={{ color: e.kind === 'crit' ? '#fecaca' : 'var(--text)' }}>{e.text}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
