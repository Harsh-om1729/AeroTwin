import { useEffect, useState } from 'react';
import { LoaderCircle } from 'lucide-react';
import { api } from '../api';
import TwinViewer from '../components/TwinViewer';
import { decisionBadge } from '../util';

export default function LiveTwin({ fleet, selected, onSelect }) {
  const id = selected || fleet[0]?.id;
  // keyed by aircraft id, so switching aircraft shows the loader instead of stale data
  const [loaded, setLoaded] = useState({ id: null, data: null, error: null });
  const data = loaded.id === id ? loaded.data : null;
  const error = loaded.id === id ? loaded.error : null;

  useEffect(() => {
    if (!id) return;
    let live = true;
    api.airframe(id)
      .then((d) => live && setLoaded({ id, data: d, error: null }))
      .catch((e) => live && setLoaded({ id, data: null, error: e.message }));
    return () => { live = false; };
  }, [id]);

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title">Digital Twin Replay</h1>
          <div className="page-sub">
            Replay of a recorded (simulated) test flight through the full pipeline: physics twin → residuals → Isolation Forest / PCA / LSTM autoencoder →
            fused Health Index → RUL → fault diagnosis → Go/No-Go. One step = one 60 s window advanced by 10 s.
          </div>
        </div>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <span className="dim" style={{ fontSize: 12 }}>Aircraft</span>
          <select value={id} onChange={(e) => onSelect(e.target.value)}>
            {fleet.map((f) => <option key={f.id} value={f.id}>{f.id} · {f.callsign} · {f.decision}</option>)}
          </select>
          {data && <span className={`badge ${decisionBadge(data.summary.decision)}`}>{data.summary.decision}</span>}
        </div>
      </div>
      {error && <div className="panel" style={{ color: 'var(--crit)' }}>Failed to load: {error}</div>}
      {!data && !error && <div className="loading"><div><LoaderCircle className="spin" /><div>Loading flight data…</div></div></div>}
      {data && (
        <TwinViewer key={id} timeline={data.timeline} truth={data.truth} title={`${id} · ${data.summary.callsign}`} subtitle={data.summary.mission_id} />
      )}
    </>
  );
}
