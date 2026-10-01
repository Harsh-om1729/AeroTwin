import { useEffect, useState } from 'react';
import { CircleCheck, LoaderCircle, Plane } from 'lucide-react';

// Shown while the backend replays the fleet through the pipeline. The steps
// are the real start-up stages of backend/main.py:lifespan.
const STEPS = [
  'Loading Rotax 912 S/ULS operating limits',
  'Starting physics twin (ISA atmosphere + thermal model)',
  'Loading Isolation Forest · PCA · LSTM-AE ensemble',
  'Initialising 1,320-particle Bayesian health twin',
  'Replaying 8 fleet flights through the pipeline',
];

export default function BootScreen() {
  const [done, setDone] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setDone((d) => Math.min(d + 1, STEPS.length - 1)), 650);
    return () => clearInterval(id);
  }, []);
  return (
    <div className="boot">
      <div className="boot-card">
        <div className="boot-logo"><Plane size={28} /></div>
        <div className="boot-title">AeroTwin</div>
        <div className="boot-sub">Aero-piston engine digital twin · initialising</div>
        <div className="boot-bar"><div style={{ width: `${((done + 1) / STEPS.length) * 100}%` }} /></div>
        <ul className="boot-steps">
          {STEPS.map((s, i) => (
            <li key={s} className={i < done ? 'ok' : i === done ? 'run' : ''}>
              {i < done ? <CircleCheck size={15} /> : i === done ? <LoaderCircle size={15} className="spin" /> : <span className="dot" />}
              {s}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
