export const FAULT_SHORT = {
  lubrication: 'Lubrication',
  cooling_degradation: 'Cooling',
  injector_abnormality: 'Lean cylinder',
  misfire: 'Misfire',
  abnormal_vibration: 'Vibration',
  none: 'Not diagnosed',
};

export const FAULT_COLORS = {
  lubrication: '#f59e0b',
  cooling_degradation: '#ef4444',
  injector_abnormality: '#a78bfa',
  misfire: '#f472b6',
  abnormal_vibration: '#38bdf8',
};

export const MODEL_COLORS = { IF: '#38bdf8', PCA: '#a78bfa', LSTM: '#f472b6' };

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

