import { Fragment } from 'react';
import { Atom, ChevronRight, Database, Info, Layers, Network, TriangleAlert, Workflow } from 'lucide-react';

const STEPS = [
  { n: '01', t: 'Engine telemetry', d: '17 sensors at 1 Hz: RPM, throttle, altitude, oil P/T, 4× CHT, 4× EGT, fuel flow, vibration, alternator.' },
  { n: '02', t: 'Physics twin', d: 'ISA atmosphere + Gagg-Ferrar power lapse + first-order thermal lag: what a healthy engine should read right now.' },
  { n: '03', t: 'Residuals', d: 'Measured − expected for 15 channels plus CHT/EGT spread. Removes flight-condition effects, keeps fault signal.' },
  { n: '04', t: 'Windowing', d: '60 s sliding windows (10 s stride), standardised on healthy training flights. Mean / std / slope features.' },
  { n: '05', t: 'AI ensemble', d: 'Isolation Forest + PCA (SPE) + LSTM autoencoder, trained on healthy flights only (unsupervised).' },
  { n: '06', t: 'Fusion → HI', d: 'Each score → percentile of healthy validation; averaged; mapped to a 0–100 Health Index (median healthy = 95).' },
  { n: '07', t: 'Bayesian twin', d: 'Particle filter infers hidden component health & fault hypothesis from raw 1 Hz data; RUL as a probability distribution.' },
  { n: '08', t: 'Decide', d: 'HI alert, P(failure within mission), signature check, Rotax redlines → Go / Caution / No-Go.' },
];

const STACK = [
  ['Simulation & physics', 'Python, NumPy, ISA atmosphere model, Rotax 912 S/ULS limits'],
  ['Machine learning', 'scikit-learn (Isolation Forest, PCA), PyTorch (LSTM autoencoder)'],
  ['Backend', 'FastAPI (REST + WebSocket), Pydantic, Uvicorn'],
  ['Frontend', 'React 19, Vite, Recharts, Lucide icons, custom SVG engine model'],
  ['Data', 'Parquet datasets: 140 train + 28 validation + 60 healthy test + 60 fault test flights (1 h each)'],
];

const DATA = [
  ['Train (healthy)', 'seed block 1', '140 flights', 'Standard profile', 'Fit scaler + 3 detectors'],
  ['Validation (healthy)', 'seed block 2', '28 flights', 'Standard profile', 'Fusion percentiles, HI calibration'],
  ['Development (fault)', 'seed block 4', '20 flights', '5 fault types × 4', 'The only fault data used while developing'],
  ['Test (healthy)', 'seed block 3', '60 flights', 'Hot weather (+35 °C)', 'False-alarm events (final)'],
  ['Test (fault)', 'seed block 5', '60 flights', '5 fault types × 12', 'Detection, diagnosis, RUL (final, evaluated once)'],
];

export default function Architecture({ meta }) {
  const e = meta?.engine;
  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title">How it works</h1>
          <div className="page-sub">
            A physics-informed digital twin for predictive health monitoring of MALE-UAV aero-piston engines. The physics
            model explains <i>normal</i> behaviour; machine learning watches what physics cannot explain.
          </div>
        </div>
      </div>

      <div className="panel">
        <div className="panel-title"><Workflow size={15} /> Processing pipeline</div>
        <div className="flow">
          {STEPS.map((s, i) => (
            <Fragment key={s.n}>
              <div className="flow-step">
                <div className="num">{s.n}</div>
                <h4>{s.t}</h4>
                <p>{s.d}</p>
              </div>
              {i < STEPS.length - 1 && <div className="flow-arrow"><ChevronRight size={18} /></div>}
            </Fragment>
          ))}
        </div>
      </div>

      <div className="panel flagship mt">
        <div className="panel-title"><Atom size={15} /> Flagship: Bayesian health twin (particle filter)</div>
        <div className="grid g2">
          <div style={{ color: 'var(--text-2)', fontSize: 13.5, lineHeight: 1.7 }}>
            The ML ensemble answers <i>&quot;is something abnormal?&quot;</i>. The Bayesian twin answers <i>&quot;which physical component is degrading,
            how healthy is it right now, and when will it fail, with what certainty?&quot;</i> It infers the <b style={{ color: 'var(--text)' }}>hidden
            health parameters</b> of the engine (oil system, cooling, each cylinder's mixture, each ignition circuit, bearings) that no sensor measures directly.
            <ul style={{ paddingLeft: 18, margin: '10px 0 0' }}>
              <li><b style={{ color: 'var(--text)' }}>Bank of 11 particle filters</b>, one per fault hypothesis (×120 particles), with Bayesian model selection between them.</li>
              <li>Each particle carries health <span className="mono">h</span>, degradation rate <span className="mono">r</span>, an unknown-onset flag (jump-Markov) and its own thermal state, pushed through the physics engine model every second.</li>
              <li>The sensor likelihood re-weights particles; each filter&apos;s evidence updates P(hypothesis | data).</li>
              <li>RUL = each particle extrapolated to the functional-failure health limit → a full probability distribution, not a single number.</li>
            </ul>
          </div>
          <div style={{ color: 'var(--text-2)', fontSize: 13.5, lineHeight: 1.7 }}>
            <b style={{ color: 'var(--text)' }}>Honest by construction</b>
            <ul style={{ paddingLeft: 18, margin: '6px 0 0' }}>
              <li>The filter does <b>not</b> know the true degradation law (exponential vs linear), its rate or onset time; it assumes a generic drifting-rate decline.</li>
              <li>Its parameters were tuned with <span className="mono">aerotwin/twin/tune.py</span> on separately simulated flights only. The held-out test set was never used for tuning.</li>
              <li>Uncertainty is validated, not just drawn: interval coverage is measured against hidden ground truth (Validation page).</li>
              <li>Limitation: it shares the physics model with the simulator. On a real engine that model must be calibrated first (sim-to-real gap).</li>
            </ul>
          </div>
        </div>
      </div>

      <div className="grid g2 mt">
        <div className="panel">
          <div className="panel-title"><Info size={15} /> Key design decisions</div>
          <ul style={{ margin: 0, paddingLeft: 18, color: 'var(--text-2)', fontSize: 13.5, lineHeight: 1.7 }}>
            <li><b style={{ color: 'var(--text)' }}>Residuals, not raw sensors.</b> A climb makes CHT rise in a healthy engine too; comparing against a lagged physics twin removes that, so models see only unexplained behaviour.</li>
            <li><b style={{ color: 'var(--text)' }}>Trained on healthy data only.</b> Real fleets have few recorded failures, so detectors learn &quot;normal&quot; and flag deviations. They need no fault labels.</li>
            <li><b style={{ color: 'var(--text)' }}>Ensemble with percentile fusion.</b> Three different model families make partly uncorrelated mistakes; averaging calibrated percentiles reduced false-alarm events from 10–78 per single model to 1 on the test split (see Validation).</li>
            <li><b style={{ color: 'var(--text)' }}>Persistence rule.</b> An alert needs 8 consecutive windows (80 s) below HI 50, so single noisy windows never ground an aircraft.</li>
            <li><b style={{ color: 'var(--text)' }}>Physics-based diagnosis.</b> Fault isolation matches residual patterns to physical signatures, so it is explainable to a maintainer (&quot;EGT cyl 2 −5σ with vibration +2σ&quot;).</li>
            <li><b style={{ color: 'var(--text)' }}>No leakage, seeded data.</b> Every split comes from a disjoint seed block, so the dataset is identical on every machine. Rules and thresholds were fixed on a development split; the test split is evaluated once. Ground-truth failure time is derived analytically from the fault model.</li>
          </ul>
        </div>
        <div className="panel">
          <div className="panel-title"><Database size={15} /> Dataset split</div>
          <table className="t">
            <thead><tr><th>Split</th><th>Seeds</th><th>Size</th><th>Conditions</th><th>Used for</th></tr></thead>
            <tbody>{DATA.map((r) => <tr key={r[0]}>{r.map((c, i) => <td key={i} style={i === 0 ? { fontWeight: 600 } : { color: 'var(--text-2)' }}>{c}</td>)}</tr>)}</tbody>
          </table>
          <div className="panel-title mt"><Layers size={15} /> Technology stack</div>
          <table className="t">
            <tbody>{STACK.map(([k, v]) => <tr key={k}><td style={{ fontWeight: 600, width: 170 }}>{k}</td><td style={{ color: 'var(--text-2)' }}>{v}</td></tr>)}</tbody>
          </table>
        </div>
      </div>

      <div className="grid g2 mt">
        <div className="panel">
          <div className="panel-title"><Network size={15} /> Engine operating limits used by the advisor</div>
          {e ? (
            <table className="t">
              <thead><tr><th>Parameter</th><th>Limit</th></tr></thead>
              <tbody>
                <tr><td>Engine speed</td><td className="mono">idle ≥ {e.rpm.idle} · max cont. {e.rpm.max_continuous} · take-off {e.rpm.max_takeoff} rpm</td></tr>
                <tr><td>Oil pressure</td><td className="mono">{e.oil_press.min}–{e.oil_press.max} bar (normal {e.oil_press.normal.join('–')})</td></tr>
                <tr><td>Oil temperature</td><td className="mono">{e.oil_temp.min}–{e.oil_temp.max} °C (normal {e.oil_temp.normal.join('–')})</td></tr>
                <tr><td>Cylinder head temp.</td><td className="mono">max {e.cht.max} °C</td></tr>
                <tr><td>Exhaust gas temp.</td><td className="mono">max {e.egt.max} °C</td></tr>
              </tbody>
            </table>
          ) : <div className="dim">Loading…</div>}
          <div className="dim" style={{ fontSize: 11.5, marginTop: 8 }}>Source: {e?.rpm.source}. Variant {e?.variant}.</div>
          {meta && (
            <div className="dim mono" style={{ fontSize: 11.5, marginTop: 8 }}>
              window {meta.window_size_s} s · stride {meta.stride_s} s · HI exponent p = {meta.hi_exponent_p.toFixed(3)} · models {meta.models.join(' + ')}
            </div>
          )}
        </div>
        <div className="panel">
          <div className="panel-title"><TriangleAlert size={15} /> Limitations & next steps</div>
          <ul style={{ margin: 0, paddingLeft: 18, color: 'var(--text-2)', fontSize: 13.5, lineHeight: 1.7 }}>
            <li>Trained and validated on <b>simulated</b> flights; the fault models are idealised. The healthy twin and the particle filter use the <b>same equations as the simulator</b> and all simulated engines are identical, so results are an upper bound. Real-engine accuracy will be lower and must be re-measured.</li>
            <li>Next step: record a real engine run (protocol in <span className="mono">aerotwin/real_engine/recording_protocol.md</span>) and use sim-to-real calibration of the twin.</li>
            <li>RUL is a linear-trend extrapolation without uncertainty bands. A probabilistic model (e.g. particle filter) would give confidence intervals.</li>
            <li>One fault at a time; compound faults and sensor failures (stuck/drifting sensors) are not yet modelled.</li>
            <li>Decision support only, not a certified airworthiness system.</li>
          </ul>
        </div>
      </div>
    </>
  );
}
