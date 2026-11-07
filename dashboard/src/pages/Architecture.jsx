import { Fragment } from 'react';
import { Atom, BookA, BrainCircuit, ChevronRight, Copy, Database, Gauge, Info, Layers, Network, Radio, TriangleAlert, Workflow } from 'lucide-react';
import { useSimple } from '../ui/viewContext';

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
  ['Test (fault)', 'seed block 5', '60 flights', '5 fault types × 12', 'Detection, diagnosis, RUL (final, never tuned on)'],
];

const SIMPLE_STEPS = [
  { icon: Radio, t: 'Sensors listen', d: '17 sensors measure the engine every second: temperatures, oil pressure, fuel flow, shaking and more.' },
  { icon: Copy, t: 'A perfect copy predicts', d: 'A computer copy of a healthy engine (the "digital twin") works out what each sensor should read right now, for this height, power and weather.' },
  { icon: BrainCircuit, t: 'AI spots the difference', d: 'AI models that only ever saw healthy flights compare the real readings with the copy. A growing gap means a part is wearing out.' },
  { icon: Gauge, t: 'A clear answer', d: 'The system gives a health score from 0 to 100, names the likely problem, estimates the time left, and says GO or NO-GO.' },
];

const GLOSSARY = [
  ['Digital twin', 'A computer copy of the engine that knows how a healthy engine behaves, used as the reference.'],
  ['Health score (Health Index)', 'One number from 0 to 100 for how healthy the engine looks. 100 is like new; staying below 50 sets off a warning.'],
  ['GO / NO-GO', 'The final answer for the next flight: GO means safe to fly, NO-GO means repair first. CAUTION means check it soon.'],
  ['Fault', 'Something going wrong in the engine, such as low oil pressure, overheating or a bad spark plug.'],
  ['Time left (RUL)', 'Remaining useful life: an estimate of how long the faulty part can keep working before it fails.'],
  ['False alarm', 'A warning on an engine that is actually healthy. A good system raises very few.'],
  ['Simulated flight', 'A flight created by a computer model instead of a real drone, so the true problem is known and answers can be checked.'],
  ['AI ensemble', 'Three different AI models that each judge the engine; their answers are averaged so one model’s mistake matters less.'],
  ['Bayesian twin', 'A second checker that estimates how worn each part is and how sure it is, often spotting trouble before the AI models.'],
];

function SimpleHow() {
  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title">How it works</h1>
          <div className="page-sub">
            Think of a doctor checking your temperature: they compare it with the normal 37 °C. AeroTwin does the same for a
            drone engine. It knows what a healthy engine should read at every moment, and raises a warning when the real engine
            stops matching.
          </div>
        </div>
      </div>
      <div className="panel">
        <div className="panel-title"><Workflow size={15} /> Four steps, every second of the flight</div>
        <ol className="steps4">
          {SIMPLE_STEPS.map((s) => (
            <li key={s.t} className="step4">
              <span className="step4-icon"><s.icon size={20} /></span>
              <h4>{s.t}</h4>
              <p>{s.d}</p>
            </li>
          ))}
        </ol>
      </div>
      <div className="grid g-wide mt">
        <div className="panel">
          <div className="panel-title"><BookA size={15} /> Words you will see</div>
          <dl className="glossary">
            {GLOSSARY.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}
          </dl>
        </div>
        <div className="panel honest">
          <div className="panel-title"><TriangleAlert size={15} /> What it cannot do yet</div>
          <ul className="plain-list">
            <li>It has been tested on <b>computer-simulated</b> flights. Real engines are messier, so real accuracy will be lower.</li>
            <li>It looks for <b>one problem at a time</b>, and it does not yet notice a broken sensor.</li>
            <li>It helps engineers decide. It is <b>not</b> a certified safety system.</li>
          </ul>
          <div className="plain-note">Switch to <b>Detailed</b> view at the top of the page for the full technical design.</div>
        </div>
      </div>
    </>
  );
}

export default function Architecture({ meta }) {
  const simple = useSimple();
  const e = meta?.engine;
  if (simple) return <SimpleHow />;
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
        <div className="flow stagger">
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
            <li><b style={{ color: 'var(--text)' }}>Ensemble with percentile fusion.</b> Three different model families make partly uncorrelated mistakes; averaging calibrated percentiles reduced false-alarm events from 13–77 per single model to 2 on the test split (see Validation).</li>
            <li><b style={{ color: 'var(--text)' }}>Persistence rule.</b> An alert needs 8 consecutive windows (80 s) below HI 50, so single noisy windows never ground an aircraft.</li>
            <li><b style={{ color: 'var(--text)' }}>Grounded AI copilot.</b> A Claude tool-use assistant can only read the twin&apos;s outputs through six read-only tools, must cite them, and never overrides the Go/No-Go; if the API is unavailable an offline engine answers from the same evidence.</li>
            <li><b style={{ color: 'var(--text)' }}>Explainable AI, and checked.</b> Every flagged window gets a sensor-level counterfactual explanation: each sensor is reset to healthy, the three models are re-scored, and the drop in their raw anomaly score is that sensor&apos;s share of the evidence. The top-ranked sensor is then checked against the fault&apos;s physics on the test split.</li>
            <li><b style={{ color: 'var(--text)' }}>Physics-based diagnosis.</b> Fault isolation matches residual patterns to physical signatures, so it is explainable to a maintainer (&quot;EGT cyl 2 −5σ with vibration +2σ&quot;).</li>
            <li><b style={{ color: 'var(--text)' }}>No leakage, seeded data.</b> Every split comes from a disjoint seed block, so the dataset is identical on every machine. Rules and thresholds were fixed on a development split and are never tuned on the test split. Ground-truth failure time is derived analytically from the fault model.</li>
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
            <li>Reality-gap study: with an uncalibrated twin every method breaks at a small mismatch (CUSUM first, then ML, then the Bayesian twin). Per-engine calibration extends the usable range, and the filter's RUL intervals still need to account for model mismatch.</li>
            <li>One fault at a time; compound faults and sensor failures (stuck/drifting sensors) are not yet modelled.</li>
            <li>Decision support only, not a certified airworthiness system.</li>
          </ul>
        </div>
      </div>
    </>
  );
}
