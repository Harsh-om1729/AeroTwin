// Real-flight validation (NGAFID, Cessna 172): does the score separate flights
// just before unplanned maintenance from flights just after? Hidden until
// `python3 -m aerotwin.evaluation.real_report --test` has been run.
import { useEffect, useState } from 'react';
import { Plane } from 'lucide-react';
import { api } from '../api';
import { pct } from '../util';

const NAME = { Fused: 'Fused ensemble', IF: 'Isolation Forest', PCA: 'PCA (SPE)', LSTM: 'LSTM autoencoder' };
const ISSUE = { intake_rocker_other: 'Intake, rocker cover, other', baffle: 'Baffle', engine: 'Engine', cylinder: 'Cylinder', oil: 'Oil' };
const n2 = (x) => x.toFixed(2);

export default function RealFlights() {
  const [r, setR] = useState(null);
  useEffect(() => { api.realResults().then(setR).catch(() => setR(null)); }, []);
  if (!r?.test) return null;
  const t = r.test;
  const fused = t.methods.find((m) => m.method === 'Fused');
  const oil = t.methods.find((m) => m.method === 'Low oil pressure');
  const dec = t.decisions['Low oil pressure'];
  return (
    <div className="panel mt">
      <div className="panel-title"><Plane size={15} /> Real flights: NGAFID maintenance dataset
        <span className="right dim" style={{ fontSize: 11 }}>{r.dataset.aircraft} · not a Rotax 912 · {t.flights.toLocaleString()} test flights</span></div>
      <div className="grid g2">
        <div>
          <div className="sub-title">Separating flights before vs after unplanned maintenance (ROC-AUC, 0.50 = coin flip)</div>
          <table className="t">
            <thead><tr><th>Score</th><th style={{ textAlign: 'right' }}>Test AUC</th><th style={{ textAlign: 'right' }}>95% CI</th></tr></thead>
            <tbody>
              {t.methods.map((m) => (
                <tr key={m.method} className={m === oil ? 'best' : ''}>
                  <td>{NAME[m.method] || m.method}</td>
                  <td className="num">{n2(m.auc)}</td>
                  <td className="num">{n2(m.ci95[0])}–{n2(m.ci95[1])}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="dim" style={{ fontSize: 11.5, marginTop: 8, lineHeight: 1.5 }}>
            Published supervised reference: {pct(r.published.binary_accuracy, 1)} accuracy ({r.published.model}). Not directly comparable: the
            detectors here never see a label. Low oil pressure at the development threshold: balanced accuracy {pct(dec.balanced_accuracy)},
            {' '}{pct(dec.recall_before)} of pre-maintenance flights flagged, {pct(dec.false_flag_after)} of post-maintenance flights flagged.
          </div>
        </div>
        <div>
          <div className="sub-title">Fused ensemble by issue group</div>
          <table className="t">
            <thead><tr><th>Issue group</th><th style={{ textAlign: 'right' }}>Flights</th><th style={{ textAlign: 'right' }}>Test AUC (95% CI)</th></tr></thead>
            <tbody>
              {t.issues.map((i) => (
                <tr key={i.issue}><td>{ISSUE[i.issue] || i.issue}</td><td className="num">{i.flights}</td><td className="num">{n2(i.auc)} ({n2(i.ci95[0])}–{n2(i.ci95[1])})</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      {r.supervised && (
        <div className="mt">
          <div className="sub-title">Supervised models trained on the before/after labels ({r.supervised.train_flights.toLocaleString()} flights)</div>
          <table className="t">
            <thead><tr><th>Model</th><th>Sensors used</th><th style={{ textAlign: 'right' }}>Test AUC (95% CI)</th><th style={{ textAlign: 'right' }}>Balanced accuracy</th></tr></thead>
            <tbody>
              {r.supervised.results.map((x) => (
                <tr key={`${x.model}-${x.features}`}>
                  <td>{x.model}</td><td>{x.features}</td>
                  <td className="num">{n2(x.test.auc)} ({n2(x.test.ci95[0])}–{n2(x.test.ci95[1])})</td>
                  <td className="num">{pct(x.test.balanced_accuracy)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="dim" style={{ fontSize: 11.5, marginTop: 8, lineHeight: 1.5 }}>
            Without oil pressure the skill almost disappears, so these models are mostly reading one sensor. Second use of the test fold, after the unsupervised evaluation.
          </div>
        </div>
      )}
      <div className="note mt">
        <b>Honest reading:</b> on real flights the unsupervised ensemble scored AUC {n2(fused.auc)}, close to chance, far from its simulated results.
        Maintenance issues barely move these sensors, and pilots and weather move them a lot. Low oil pressure held up on the test fold (AUC {n2(oil.auc)}), but it was
        chosen on the development fold as the best of 11 scores, and it may reflect an oil change during the repair visit rather than a detected fault.
        A learned baseline replaces the physics twin here; the particle filter was not run. Aircraft identity is not in the data, so one aircraft can appear in several folds.
      </div>
    </div>
  );
}
