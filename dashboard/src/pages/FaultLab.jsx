import { useState } from 'react';
import { Atom, CircleCheck, CircleX, Droplet, FlaskConical, LoaderCircle, ShieldCheck, Sparkles, Thermometer, Waves, Zap, Fuel } from 'lucide-react';
import { api } from '../api';
import TwinViewer from '../components/TwinViewer';
import { FAULT_SHORT, HYP_LABEL, clock, fmtDur } from '../util';

const FAULTS = [
  { id: '', icon: ShieldCheck, name: 'Healthy engine', desc: 'No fault. Tests that the twin does not raise false alarms.' },
  { id: 'lubrication', icon: Droplet, name: 'Lubrication loss', desc: 'Oil pump / oil starvation: oil pressure decays.' },
  { id: 'cooling_degradation', icon: Thermometer, name: 'Cooling loss', desc: 'Blocked radiator / baffles: CHT and oil temp climb.' },
  { id: 'injector_abnormality', icon: Fuel, name: 'Lean cylinder', desc: 'Intake leak / fuel metering: one cylinder runs lean (EGT↑).' },
  { id: 'misfire', icon: Zap, name: 'Ignition misfire', desc: 'Fouled plug: one cylinder EGT drops, vibration rises.' },
  { id: 'abnormal_vibration', icon: Waves, name: 'Bearing wear', desc: 'Mechanical wear: vibration grows, temperatures normal.' },
];

const PROFILES = {
  standard: 'Standard (ISA, 5,000 ft)',
  hot_weather: 'Hot day (+35 °C)',
  high_altitude: 'High altitude (15,000 ft) – unseen in training',
  rapid_throttle: 'Rapid throttle changes – unseen in training',
};

export default function FaultLab() {
  const [fault, setFault] = useState('misfire');
  const [severity, setSeverity] = useState('moderate');
  const [onset, setOnset] = useState(1200);
  const [profile, setProfile] = useState('standard');
  const [gap, setGap] = useState(0);
  const [calibrate, setCalibrate] = useState(false);
  const [busy, setBusy] = useState(false);
  const [run, setRun] = useState(null);
  const [error, setError] = useState(null);
  const [runNo, setRunNo] = useState(0);

  const go = async () => {
    setBusy(true);
    setError(null);
    try {
      const r = await api.simulate({ fault_type: fault || null, severity, onset_s: onset, profile, gap, calibrate });
      setRun(r);
      setRunNo((n) => n + 1);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const t = run?.truth;
  const res = run?.result;
  let verdict = null;
  if (run) {
    if (!t.fault_type) {
      verdict = res.first_alert_t == null
        ? { ok: true, title: 'Correct – no false alarm', text: 'The twin flew a full healthy mission without raising an alert.' }
        : { ok: false, title: 'False alarm', text: `An alert fired at T+${clock(res.first_alert_t)} on a healthy engine.` };
    } else if (res.first_alert_t < t.fault_start_t) {
      verdict = {
        ok: false,
        title: `ML ensemble false-alarmed before the fault began (T+${clock(res.first_alert_t)})`,
        text: `The fault was injected at T+${clock(t.fault_start_t)}. A mismatch between the simulated engine and the twin can make the residuals look abnormal from take-off; compare the Bayesian twin line below.`,
      };
    } else if (res.first_alert_t == null) {
      verdict = { ok: false, title: 'Fault missed', text: 'No sustained alert before end of flight. Try a later onset or higher severity.' };
    } else {
      const diagOk = res.diagnosed_as === t.fault_type;
      const before = res.first_alert_t < t.failure_t;
      verdict = {
        ok: diagOk && before,
        title: `${before ? 'Detected before failure' : 'Detected after failure'} · ${diagOk ? 'diagnosis correct' : `diagnosed as ${FAULT_SHORT[res.diagnosed_as] || '—'}`}`,
        text: `Fault injected at T+${clock(t.fault_start_t)} → alert at T+${clock(res.first_alert_t)} (${fmtDur(res.detection_delay_s)} after onset). `
          + (before ? `Warning given ${fmtDur(res.lead_time_s)} before functional failure.` : ''),
      };
    }
  }

  let twinLine = null;
  let cusumLine = null;
  if (run) {
    const c = res.cusum_detect_t;
    const preOnset = t.fault_type && c != null && c < t.fault_start_t;
    cusumLine = !t.fault_type
      ? (c == null ? 'CUSUM baseline: no alarm.' : `CUSUM baseline: false alarm at T+${clock(c)}.`)
      : c == null ? 'CUSUM baseline: no alarm.' : preOnset ? `CUSUM baseline: already alarming at T+${clock(c)}, before the fault began.` : `CUSUM baseline: alarm ${fmtDur(c - t.fault_start_t)} after onset.`;
  }
  if (run) {
    const td = res.twin_diagnosis;
    const key = td ? (td.cylinder ? `${td.fault}:${td.cylinder}` : td.fault) : null;
    if (!t.fault_type) {
      twinLine = res.twin_detect_t == null ? 'Bayesian twin: P(degraded) stayed low all flight. No false alarm.' : `Bayesian twin raised a false detection at T+${clock(res.twin_detect_t)}.`;
    } else if (res.twin_detect_t != null) {
      const ok = td.fault === t.fault_type;
      twinLine = `Bayesian twin: detected ${fmtDur(res.twin_delay_s)} after onset as ${HYP_LABEL[key]} (${ok ? 'correct' : 'wrong'})`
        + (res.detection_delay_s != null ? `, ${fmtDur(Math.max(0, res.detection_delay_s - res.twin_delay_s))} earlier than the ML ensemble.` : '.');
    } else {
      twinLine = 'Bayesian twin: no confident detection this flight.';
    }
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title">Fault Injection Lab</h1>
          <div className="page-sub">
            Generate a brand-new flight with the physics engine model, inject a fault you choose, and watch the digital twin
            find it. Nothing here is pre-recorded: every run is a fresh mission the AI models have never seen.
          </div>
        </div>
      </div>

      <div className="panel">
        <div className="field-label">1 · Choose a fault to inject</div>
        <div className="grid g6 stagger">
          {FAULTS.map((f) => (
            <div key={f.id || 'none'} className={`fault-opt ${fault === f.id ? 'on' : ''}`} onClick={() => setFault(f.id)}>
              <f.icon size={20} color={fault === f.id ? 'var(--accent)' : 'var(--text-2)'} />
              <h4>{f.name}</h4>
              <p>{f.desc}</p>
            </div>
          ))}
        </div>

        <div className="grid g3 mt" style={{ alignItems: 'end' }}>
          <div>
            <div className="field-label">2 · Severity (degradation rate)</div>
            <div className="seg">
              {['mild', 'moderate', 'severe'].map((s) => (
                <button key={s} disabled={!fault} className={severity === s ? 'on' : ''} onClick={() => setSeverity(s)}>{s}</button>
              ))}
            </div>
          </div>
          <div>
            <div className="field-label">3 · Fault onset: T+{clock(onset)}</div>
            <input type="range" min={300} max={2700} step={30} value={onset} disabled={!fault} onChange={(e) => setOnset(+e.target.value)} />
          </div>
          <div>
            <div className="field-label">4 · Mission profile</div>
            <select value={profile} onChange={(e) => setProfile(e.target.value)} style={{ width: '100%' }}>
              {Object.entries(PROFILES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>
        </div>
        <div className="grid g2 mt" style={{ alignItems: 'end' }}>
          <div>
            <div className="field-label">5 · Reality gap: {gap.toFixed(2)} {gap === 0 ? '(engine matches the twin exactly)' : gap < 0.15 ? '(small mismatch)' : '(large mismatch)'}</div>
            <input type="range" min={0} max={1} step={0.05} value={gap} onChange={(e) => setGap(+e.target.value)} />
          </div>
          <label className="toggle" style={{ paddingBottom: 6 }} title="Fly one healthy reference flight of the same engine first and subtract its residual offsets">
            <input type="checkbox" checked={calibrate} disabled={gap === 0} onChange={(e) => setCalibrate(e.target.checked)} />
            Per-engine calibration (healthy reference flight first)
          </label>
        </div>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginTop: 18 }}>
          <button className="btn primary" onClick={go} disabled={busy} style={{ padding: '11px 20px', fontSize: 14 }}>
            {busy ? <LoaderCircle size={17} className="spin" /> : <FlaskConical size={17} />}
            {busy ? 'Simulating 1-hour flight…' : 'Run simulation'}
          </button>
          <span className="dim" style={{ fontSize: 12.5 }}>
            <Sparkles size={13} style={{ verticalAlign: -2 }} /> 3,600 physics steps, 355 ML windows and a 1,320-particle filter, ≈ 2 s
          </span>
          {error && <span style={{ color: 'var(--crit)' }}>{error}</span>}
        </div>
      </div>

      {run && (
        <>
          <div className={`verdict mt ${verdict.ok ? 'v-ok' : 'v-bad'}`}>
            {verdict.ok ? <CircleCheck size={34} color="var(--ok)" /> : <CircleX size={34} color="var(--crit)" />}
            <div>
              <div style={{ fontWeight: 800, fontSize: 17 }}>{verdict.title}</div>
              <div className="muted" style={{ fontSize: 13, marginTop: 3 }}>{verdict.text}</div>
              {twinLine && <div style={{ fontSize: 13, marginTop: 6, color: '#c7d2fe' }}><Atom size={13} style={{ verticalAlign: -2 }} /> {twinLine}</div>}
              {cusumLine && <div className="dim" style={{ fontSize: 12.5, marginTop: 4 }}>{cusumLine}</div>}
            </div>
            <div className="mono dim" style={{ marginLeft: 'auto', fontSize: 11, textAlign: 'right' }}>
              run #{runNo} · seed {run.seed}<br />{PROFILES[run.profile]}<br />reality gap {run.gap.toFixed(2)}{run.calibrated ? ' · calibrated' : ''}
            </div>
          </div>
          <div className="mt">
            <TwinViewer
              key={`${run.seed}-${runNo}`}
              timeline={run.timeline}
              truth={run.truth}
              title={`Simulated flight · ${t.fault_type ? `${FAULT_SHORT[t.fault_type]} (${t.severity})` : 'healthy'}`}
              subtitle={`seed ${run.seed}`}
            />
          </div>
        </>
      )}
    </>
  );
}
