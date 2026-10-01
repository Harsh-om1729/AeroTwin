// All requests are same-origin: in production FastAPI serves the built
// dashboard, in development Vite proxies /api to the backend (vite.config.js).
async function req(path, opts) {
  const res = await fetch(`/api${path}`, opts);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `${res.status} ${res.statusText}`);
  }
  return res.json();
}

export const api = {
  meta: () => req('/meta'),
  fleet: () => req('/fleet'),
  airframe: (id) => req(`/fleet/${id}`),
  mission: (split, id) => req(`/missions/${split}/${id}`),
  results: () => req('/results'),
  simulate: (body) =>
    req('/simulate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
};
