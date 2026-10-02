import { useEffect, useRef, useState } from 'react';
import { Bot, Cloud, Database, Send, Trash2, User, WifiOff } from 'lucide-react';
import { api } from '../api';
import Markdown from '../components/Markdown';

const TOOL_LABEL = {
  get_fleet_overview: 'Fleet overview',
  get_aircraft_status: 'Aircraft status',
  get_event_timeline: 'Event timeline',
  get_engine_limits: 'Engine limits',
  get_maintenance_actions: 'Maintenance actions',
  get_validation_summary: 'Validation results',
};
const STORE = 'aerotwin-copilot-chat';

const suggestions = (id, decision) => (id ? [
  decision === 'GO' ? `Is ${id} safe to fly?` : `Why is ${id} grounded?`,
  `What should the technician check on ${id}?`,
  `How much remaining useful life does ${id} have?`,
  `Which sensors caused the alert on ${id}?`,
  `What happened during ${id}'s last flight?`,
] : [
  'Which aircraft should we inspect first?',
  'Why is AT-104 grounded?',
  'What should the technician check on AT-107?',
  'How reliable is this system?',
  'What are the engine limits?',
]);

function loadChat() {
  try { return JSON.parse(sessionStorage.getItem(STORE) || '[]'); } catch { return []; }
}

export default function Copilot({ fleet, selected }) {
  const [status, setStatus] = useState(null);
  const [aircraft, setAircraft] = useState(() => (fleet.some((f) => f.id === selected) ? selected : ''));
  const [offline, setOffline] = useState(false);
  const [chat, setChat] = useState(loadChat);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const endRef = useRef(null);

  useEffect(() => { api.copilotStatus().then(setStatus).catch(() => setStatus(null)); }, []);
  useEffect(() => {
    try { sessionStorage.setItem(STORE, JSON.stringify(chat.slice(-40))); } catch { /* storage unavailable */ }
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [chat, busy]);

  const ask = async (q) => {
    const question = (q ?? input).trim();
    if (!question || busy) return;
    setInput('');
    const history = chat.filter((m) => !m.error).map((m) => ({ role: m.role, content: m.content }));
    setChat((c) => [...c, { role: 'user', content: question, aircraft }]);
    setBusy(true);
    try {
      const r = await api.copilotAsk({ question, aircraft_id: aircraft || null, history, force_offline: offline });
      setChat((c) => [...c, { role: 'assistant', content: r.answer, meta: r }]);
    } catch (e) {
      setChat((c) => [...c, { role: 'assistant', content: `The dashboard could not reach the AeroTwin backend (${e.message}). Is \`./run.sh\` running?`, error: true }]);
    } finally {
      setBusy(false);
    }
  };

  const online = status?.llm_ready && !offline;
  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title">AI Maintenance Copilot</h1>
          <div className="page-sub">
            Ask about the fleet in plain language. Every answer is grounded in the digital twin&apos;s own evidence (Go/No-Go
            reasons, Bayesian health and RUL, signature check, explainable-AI attributions, engine limits). The copilot explains
            decisions; it never makes or overrides them.
          </div>
        </div>
        <div className="copilot-mode">
          {online ? (
            <span className="badge b-info"><Cloud size={12} /> Claude · {status.model}</span>
          ) : (
            <span className="badge b-mute"><WifiOff size={12} /> Offline engine</span>
          )}
          <label className="toggle" title="Answer with the built-in offline engine only (no API call)">
            <input type="checkbox" checked={offline} onChange={(e) => setOffline(e.target.checked)} /> Offline mode
          </label>
        </div>
      </div>

      {status && !status.llm_ready && !offline && (
        <div className="note" style={{ marginBottom: 14 }}>
          Claude is not configured: {status.reason}. The copilot answers with its offline engine from the same evidence.
          To enable Claude, copy <span className="mono">.env.example</span> to <span className="mono">.env</span>, add an API key and restart.
        </div>
      )}

      <div className="copilot">
        <aside className="panel copilot-side">
          <div className="field-label">Context</div>
          <select value={aircraft} onChange={(e) => setAircraft(e.target.value)} style={{ width: '100%' }}>
            <option value="">Whole fleet</option>
            {fleet.map((f) => <option key={f.id} value={f.id}>{f.id} · {f.callsign} · {f.decision}</option>)}
          </select>
          <div className="field-label mt">Try asking</div>
          <div className="copilot-suggest">
            {suggestions(aircraft, fleet.find((f) => f.id === aircraft)?.decision).map((s) => (
              <button key={s} className="chip" disabled={busy} onClick={() => ask(s)}>{s}</button>
            ))}
          </div>
          <div className="dim" style={{ fontSize: 11.5, lineHeight: 1.55, marginTop: 14 }}>
            Prototype decision support on simulated flights. Follow the approved Rotax maintenance documentation.
          </div>
        </aside>

        <section className="panel copilot-chat">
          <div className="copilot-thread">
            {chat.length === 0 && (
              <div className="copilot-empty">
                <Bot size={34} />
                <div style={{ fontWeight: 700, marginTop: 8 }}>Ask the copilot about the fleet</div>
                <div className="muted" style={{ fontSize: 13, marginTop: 4 }}>Pick a suggestion on the left or type a question below.</div>
              </div>
            )}
            {chat.map((m, i) => (
              <div key={i} className={`msg ${m.role} ${m.error ? 'err' : ''}`}>
                <div className="msg-icon">{m.role === 'user' ? <User size={15} /> : <Bot size={15} />}</div>
                <div className="msg-body">
                  {m.role === 'user' ? <div>{m.content}{m.aircraft ? <span className="dim"> · {m.aircraft}</span> : null}</div> : <Markdown text={m.content} />}
                  {m.meta && (
                    <div className="msg-meta">
                      <span className={`badge ${m.meta.mode === 'claude' ? 'b-info' : 'b-mute'}`}>
                        {m.meta.mode === 'claude' ? <><Cloud size={11} /> {m.meta.model}</> : <><WifiOff size={11} /> Offline engine</>}
                      </span>
                      {m.meta.tools_used?.length > 0 && (
                        <span className="msg-tools"><Database size={11} /> {[...new Set(m.meta.tools_used.map((t) => TOOL_LABEL[t.name] || t.name))].join(' · ')}</span>
                      )}
                      <span className="dim">{(m.meta.latency_ms / 1000).toFixed(1)} s</span>
                      {m.meta.usage && <span className="dim">{m.meta.usage.input_tokens + m.meta.usage.output_tokens} tokens</span>}
                    </div>
                  )}
                  {status?.llm_ready && m.meta?.mode === 'offline' && m.meta.fallback_kind !== 'forced' && m.meta.fallback_reason && (
                    <div className="msg-fallback">Claude unavailable: {m.meta.fallback_reason}. Answered by the offline engine from the same digital-twin data.</div>
                  )}
                </div>
              </div>
            ))}
            {busy && (
              <div className="msg assistant">
                <div className="msg-icon"><Bot size={15} /></div>
                <div className="msg-body typing">Consulting the digital twin<span>.</span><span>.</span><span>.</span></div>
              </div>
            )}
            <div ref={endRef} />
          </div>
          <form className="copilot-input" onSubmit={(e) => { e.preventDefault(); ask(); }}>
            <input value={input} onChange={(e) => setInput(e.target.value)} maxLength={2000} disabled={busy}
              placeholder={aircraft ? `Ask about ${aircraft}…` : 'Ask about the fleet…'} />
            <button className="btn primary" type="submit" disabled={busy || !input.trim()}><Send size={15} /> Ask</button>
            <button className="btn icon" type="button" title="Clear conversation" disabled={busy || chat.length === 0} onClick={() => setChat([])}><Trash2 size={15} /></button>
          </form>
        </section>
      </div>
    </>
  );
}
