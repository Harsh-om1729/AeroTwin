// Explainable AI panel: which sensors made the ML ensemble flag the current
// window, per model and for the ensemble, plus a counterfactual sentence.
import { Lightbulb, ScanSearch } from 'lucide-react';
import { MODEL_COLORS, SENSOR_LABEL, clock } from '../util';

const MODEL_NAME = { IF: 'Isolation Forest', PCA: 'PCA-SPE', LSTM: 'LSTM-AE' };

function Bars({ data, color, max = 100, rows = 6 }) {
  const items = Object.entries(data).sort((a, b) => b[1] - a[1]).slice(0, rows);
  return items.map(([ch, v]) => (
    <div key={ch} className="xai-row">
      <span>{SENSOR_LABEL[ch] || ch}</span>
      <div className="track"><div className="fill" style={{ width: `${Math.min(100, (v / max) * 100)}%`, background: color }} /></div>
      <b className="mono">{v.toFixed(0)}%</b>
    </div>
  ));
}

export default function XaiPanel({ row, explained }) {
  const x = explained?.xai;
  const stale = explained && explained !== row;
  return (
    <div className="panel mt">
      <div className="panel-title">
        <ScanSearch size={15} /> Explainable AI: why did the ML ensemble flag this?
        <span className="right dim" style={{ fontSize: 11 }}>sensor-level counterfactual occlusion · each sensor reset to healthy, models re-scored</span>
      </div>
      {!x ? (
        <div className="xai-empty">
          The ensemble sees healthy behaviour (Health Index {row.hi_smooth.toFixed(0)}, fused anomaly percentile {row.fused.toFixed(0)}),
          so there is nothing to explain. Explanations appear as soon as the models flag a window.
        </div>
      ) : (
        <div className="grid" style={{ gridTemplateColumns: 'minmax(0,1.15fr) minmax(0,1.6fr)', gap: 22 }}>
          <div>
            <div className="sub-title">Ensemble: share of anomaly evidence per sensor
              {stale && <span className="dim" style={{ fontWeight: 400 }}> · latest flagged window, T+{clock(explained.t)}</span>}</div>
            <Bars data={x.share} color="linear-gradient(90deg, var(--accent), var(--accent-2))" />
            <div className="xai-cf">
              <Lightbulb size={16} color="var(--warn)" style={{ flexShrink: 0, marginTop: 1 }} />
              <span>
                If the <b>{SENSOR_LABEL[x.counterfactual.channel]}</b> residual had been healthy, the fused anomaly percentile would
                drop from <b>{x.base.fused.toFixed(0)}</b> to <b>{x.counterfactual.fused_without.toFixed(0)}</b>
                {x.counterfactual.fused_without >= 95 ? ' (other sensors still carry the anomaly on their own)' : ''}.
              </span>
            </div>
          </div>
          <div>
            <div className="sub-title">Per model: what each detector is reacting to</div>
            <div className="grid g3" style={{ gap: 12 }}>
              {Object.entries(x.models).map(([m, d]) => (
                <div key={m} className="xai-model">
                  <div className="xai-model-head">
                    <span style={{ color: MODEL_COLORS[m] }}>●</span> {MODEL_NAME[m]}
                    <span className="mono dim" style={{ marginLeft: 'auto' }}>{x.base[m].toFixed(0)} pct</span>
                  </div>
                  {Object.keys(d).length ? <Bars data={d} color={MODEL_COLORS[m]} rows={4} /> : <div className="dim" style={{ fontSize: 12 }}>no single sensor dominates</div>}
                </div>
              ))}
            </div>
            <div className="dim" style={{ fontSize: 11.5, marginTop: 10, lineHeight: 1.5 }}>
              Shares can sum to more than 100% when sensors overlap (e.g. EGT 1 and the EGT spread both rise for a lean cylinder).
              When the three models disagree, the ensemble average is what drives the alert.
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
