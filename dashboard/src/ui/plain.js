// Everyday wording for backend text shown in Simple view. Rules key off the
// exact strings in aerotwin/advisor/mission_advisor/go_nogo.py and
// aerotwin/diagnosis/fault_diagnosis.py; anything unrecognised is shown as-is.

export const PLAIN_FAULT = {
  lubrication: 'Oil loss (oil pump weakening)',
  cooling_degradation: 'Overheating (cooling blocked)',
  injector_abnormality: 'Too little fuel',
  misfire: 'Spark plug misfire',
  abnormal_vibration: 'Worn moving parts (shaking)',
};

const LABEL_TO_PLAIN = {
  'Lubrication system degradation': PLAIN_FAULT.lubrication,
  'Cooling system degradation': PLAIN_FAULT.cooling_degradation,
  'Lean cylinder (fuel metering / intake leak)': PLAIN_FAULT.injector_abnormality,
  'Ignition misfire': PLAIN_FAULT.misfire,
  'Abnormal vibration (bearing wear)': PLAIN_FAULT.abnormal_vibration,
};
const plainName = (name) => name.replace(/^(.*?)( \(cyl (\d)\))?$/, (_, base, __, cyl) => `${LABEL_TO_PLAIN[base] || base}${cyl ? `, cylinder ${cyl}` : ''}`);

const RULES = [
  [/^Oil pressure ([\d.]+) bar below minimum ([\d.]+) bar$/, (m) => `Oil pressure is too low (${m[1]} bar, minimum ${m[2]} bar)`],
  [/^Oil pressure ([\d.]+) bar above maximum ([\d.]+) bar$/, (m) => `Oil pressure is too high (${m[1]} bar, maximum ${m[2]} bar)`],
  [/^Oil temperature (\d+) °C above limit (\d+) °C$/, (m) => `Oil is too hot (${m[1]} °C, limit ${m[2]} °C)`],
  [/^CHT cyl (\d) (\d+) °C above limit (\d+) °C$/, (m) => `Cylinder ${m[1]} is too hot (${m[2]} °C, limit ${m[3]} °C)`],
  [/^EGT cyl (\d) (\d+) °C above limit (\d+) °C$/, (m) => `Exhaust of cylinder ${m[1]} is too hot (${m[2]} °C, limit ${m[3]} °C)`],
  [/^RPM (\d+) above max take-off (\d+)$/, (m) => `Engine spinning too fast (${m[1]} rpm, limit ${m[2]})`],
  [/^Redline exceeded at T\+(\d+):(\d+) \((.*)\) – inspect before next mission$/, (m) => `A safety limit was broken ${+m[1]} min into the flight (${plainReason(m[3])}), so it must be checked`],
  [/^Sustained Health Index alert \(HI (\d+) < 50\)$/, (m) => `Health score stayed below 50 (now ${m[1]})`],
  [/^Health alert latched earlier this flight/, () => 'A warning went off earlier in this flight, so the engine must be inspected first'],
  [/^Health degrading \(HI (\d+) < 80, sustained\)/, (m) => `Health score is slipping (now ${m[1]}, below 80), so book a check`],
  [/^Bayesian twin: P\(failure within (\d+) min mission\) = (\d+)% – (.*), health ([\d.]+)$/, (m) => `${m[2]}% chance of failure during the next ${m[1]}-minute flight: ${plainName(m[3])}`],
  [/^Bayesian twin: (.*) degraded, health ([\d.]+) – schedule inspection$/, (m) => `${plainName(m[1])} is wearing out, so book a check`],
  [/^Projected to reach alert threshold in ≈(\d+) min \(< planned (\d+) min mission\)$/, (m) => `Expected to hit the warning level in about ${m[1]} min, before a ${m[2]}-minute flight would end`],
  [/^All residuals within healthy bounds; no limit exceedance$/, () => 'Every reading is normal and within its safety limits'],
];

export function plainReason(text) {
  for (const [re, fn] of RULES) {
    const m = text.match(re);
    if (m) return fn(m);
  }
  return text;
}

export const plainFault = (diag) => (diag ? PLAIN_FAULT[diag.fault] || diag.label : null);
