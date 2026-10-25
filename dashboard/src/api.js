// All requests are same-origin: in production FastAPI serves the built
// dashboard, in development Vite proxies /api to the backend (vite.config.js).
const TIMEOUT_MS = 150000; // longer than the copilot's worst-case provider fallback chain

async function req(path, opts) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
  try {
    const res = await fetch(`/api${path}`, { ...opts, signal: ctrl.signal });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      // FastAPI 422s return detail as an array of objects
      const d = body.detail;
      const msg = typeof d === 'string' ? d : d ? JSON.stringify(d) : '';
      throw new Error(msg || `${res.status} ${res.statusText}`);
    }
    return await res.json();
  } catch (e) {
    if (e.name === 'AbortError') throw new Error('Request timed out');
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

export const api = {
  meta: () => req('/meta'),
  fleet: () => req('/fleet'),
  airframe: (id) => req(`/fleet/${id}`),
  mission: (split, id) => req(`/missions/${split}/${id}`),
  results: () => req('/results'),
  gapStudy: () => req('/gap-study'),
  copilotStatus: () => req('/copilot/status'),
  copilotAsk: (body) =>
    req('/copilot', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  simulate: (body) =>
    req('/simulate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
};
