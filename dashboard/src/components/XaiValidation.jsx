// Validation of the explanations themselves: does the top-ranked sensor match
// the sensor the injected fault physically acts on? Plus the global view.
import { ScanSearch } from 'lucide-react';
import { FAULT_SHORT, MODEL_COLORS, SENSOR_LABEL, pct } from '../util';

const WHO = [
  ['ensemble', 'Ensemble', 'var(--accent)'],
  ['LSTM', 'LSTM-AE', MODEL_COLORS.LSTM],
  ['PCA', 'PCA-SPE', MODEL_COLORS.PCA],
  ['IF', 'Isolation Forest', MODEL_COLORS.IF],
];

export default function XaiValidation({ xai }) {
  const ch = xai.channels;
  const fa = xai.false_alarm_causes;
  return (
    <div className="panel mt">
      <div className="panel-title"><ScanSearch size={15} /> Explainable AI: are the explanations right?</div>
      <div className="grid" style={{ gridTemplateColumns: 'minmax(0,0.75fr) minmax(0,2fr)', gap: 22 }}>
        <div>
          <div className="sub-title">Top-ranked sensor is the physically correct one (first alert of each fault flight)</div>
          {WHO.map(([k, label, color]) => {
            const h = xai.top1_hit[k];
            return (
              <div key={k} className="xai-row" style={{ gridTemplateColumns: '110px 1fr 58px' }}>
                <span style={{ fontWeight: k === 'ensemble' ? 700 : 400 }}>{label}</span>
                <div className="track"><div className="fill" style={{ width: `${h.rate * 100}%`, background: color }} /></div>
                <b className="mono">{h.k}/{h.n}</b>
              </div>
            );
          })}
          <div className="dim" style={{ fontSize: 11.5, marginTop: 10, lineHeight: 1.5 }}>
            Ensemble 95% CI {pct(xai.top1_hit.ensemble.ci95[0])}–{pct(xai.top1_hit.ensemble.ci95[1])}. Ground truth is only used to
            <i> check</i> explanations, never to produce them. Combining models also makes the explanations more reliable than any
            single detector&apos;s.
          </div>
          {fa.length > 0 && (
            <div className="note mt">
              The {fa.length === 1 ? 'one false alarm' : `${fa.length} false alarms`} on healthy flights {fa.length === 1 ? 'was' : 'were'} explained
              by {fa.map((f) => `${SENSOR_LABEL[f.top[0]]} (${f.share[f.top[0]].toFixed(0)}%)`).join(', ')}: a noise blip on one
              sensor, which an engineer can dismiss in seconds instead of grounding the aircraft.
            </div>
          )}
        </div>
        <div>
          <div className="sub-title">Global view: mean evidence share per sensor, by fault type (onset → failure)</div>
          <div className="heat" style={{ gridTemplateColumns: `96px repeat(${ch.length}, minmax(0, 1fr))` }}>
            <div />
            {ch.map((c) => <div key={c} className="heat-head">{SENSOR_LABEL[c]}</div>)}
            {Object.entries(xai.heatmap).map(([ft, row]) => (
              <div key={ft} style={{ display: 'contents' }}>
                <div className="heat-row">{FAULT_SHORT[ft]}</div>
                {row.map((v, i) => (
                  <div key={ch[i]} className="heat-cell" title={`${FAULT_SHORT[ft]} · ${SENSOR_LABEL[ch[i]]}: ${v.toFixed(1)}%`}
                    style={{ background: `rgba(56,189,248,${Math.min(0.9, v / 100)})`, color: v > 35 ? '#fff' : 'var(--text-3)' }}>
                    {v >= 5 ? v.toFixed(0) : ''}
                  </div>
                ))}
              </div>
            ))}
          </div>
          <div className="dim" style={{ fontSize: 11.5, marginTop: 8 }}>
            Each fault lights up its own physical signature: lubrication → oil pressure, cooling → all four CHTs, lean cylinder →
            EGT 1 + EGT spread, misfire → EGT 2 + spread + vibration, bearing → vibration.
          </div>
        </div>
      </div>
    </div>
  );
}
