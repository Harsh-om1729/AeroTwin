export const FAULT_SHORT = {
  lubrication: 'Lubrication',
  cooling_degradation: 'Cooling',
  injector_abnormality: 'Lean cylinder',
  misfire: 'Misfire',
  abnormal_vibration: 'Vibration',
  none: 'Not diagnosed',
};

// Series colours sit in the validated lightness band for the plum glass surface
// (#241650). The fault set's closest pair is CVD dE 6.6, so its charts always label each fault.
export const FAULT_COLORS = {
  lubrication: '#C08811',
  cooling_degradation: '#03AF73',
  injector_abnormality: '#9F73FF',
  misfire: '#FE20AA',
  abnormal_vibration: '#04A1D8',
};

export const MODEL_COLORS = { IF: '#04A1D8', PCA: '#9F73FF', LSTM: '#FE20AA' };

export const hiColor = (hi) => (hi >= 80 ? 'var(--ok)' : hi >= 50 ? 'var(--warn)' : 'var(--crit)');
export const statusBadge = (s) => ({ nominal: 'b-ok', warning: 'b-warn', critical: 'b-crit' })[s] || 'b-mute';
export const decisionBadge = (d) => ({ GO: 'b-ok', CAUTION: 'b-warn', 'NO-GO': 'b-crit' })[d] || 'b-mute';

export const clock = (s) => {
  if (s == null || !Number.isFinite(s)) return '--:--';
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
};

export const fmtDur = (s) => {
  if (s == null || !Number.isFinite(s)) return '—';
  if (s < 90) return `${Math.round(s)} s`;
  if (s < 5400) return `${(s / 60).toFixed(1)} min`;
  return `${(s / 3600).toFixed(1)} h`;
};

export const pct = (x, d = 0) => (x == null ? '—' : `${(x * 100).toFixed(d)}%`);

export const HYP_LABEL = {
  healthy: 'Healthy',
  lubrication: 'Lubrication',
  cooling_degradation: 'Cooling',
  'injector_abnormality:1': 'Lean · C1',
  'injector_abnormality:2': 'Lean · C2',
  'injector_abnormality:3': 'Lean · C3',
  'injector_abnormality:4': 'Lean · C4',
  'misfire:1': 'Misfire · C1',
  'misfire:2': 'Misfire · C2',
  'misfire:3': 'Misfire · C3',
  'misfire:4': 'Misfire · C4',
  abnormal_vibration: 'Bearing',
};

export function trueHealth(truth, t) {
  if (!truth?.fault_type || truth.rate == null || t < truth.fault_start_t) return 1;
  const x = t - truth.fault_start_t;
  return truth.fault_type === 'misfire' ? Math.max(0, 1 - truth.rate * x) : Math.exp(-truth.rate * x);
}


export const SENSOR_LABEL = {
  oil_press_bar: 'Oil pressure', oil_temp_c: 'Oil temp', fuel_flow_lph: 'Fuel flow', vib_rms_g: 'Vibration',
  alt_voltage_v: 'Alternator', cht_1: 'CHT 1', cht_2: 'CHT 2', cht_3: 'CHT 3', cht_4: 'CHT 4',
  egt_1: 'EGT 1', egt_2: 'EGT 2', egt_3: 'EGT 3', egt_4: 'EGT 4', cht_spread: 'CHT spread', egt_spread: 'EGT spread',
};

// Detector identity colours for comparison charts: first three slots of the
// validated palette on the plum glass surface (CVD dE >= 10, contrast >= 3:1).
export const METHOD_COLORS = { ml: '#4892FD', cusum: '#DE7200', twin: '#03AF73' };
export const METHOD_LABEL = { ml: 'ML ensemble', twin: 'Bayesian twin', cusum: 'CUSUM' };
