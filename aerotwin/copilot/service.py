"""Copilot entry point: try each configured AI provider, then the offline engine.

Provider order: Gemini, then Claude (override with COPILOT_PROVIDER=claude to
prefer Claude). Only providers whose SDK is installed and whose key is
configured are tried. If one fails (bad key, no credit, quota, network,
timeout, refusal) the next is tried; if all fail, the offline engine answers
from the same evidence. The caller always gets an answer: `mode` names the
engine that produced it ("gemini", "claude" or "offline") and
`fallback_reason` says why the AI providers were not used.
"""
from __future__ import annotations

import os
import time

from aerotwin.copilot import gemini_llm, llm
from aerotwin.copilot.evidence import clock
from aerotwin.copilot.llm import CopilotUnavailable
from aerotwin.copilot.offline import answer_offline

MAX_QUESTION = 2000
MAX_HISTORY_TURNS = 8
MAX_TURN_CHARS = 4000

def _late(module, name):
    """Look the function up at call time (keeps monkeypatching and reloads working)."""
    return lambda *args, **kwargs: getattr(module, name)(*args, **kwargs)


PROVIDERS = {
    "gemini": {"label": "Gemini", "ask": _late(gemini_llm, "ask_gemini"), "sdk": _late(gemini_llm, "sdk_installed"),
               "configured": _late(gemini_llm, "credentials_configured"), "model": _late(gemini_llm, "model_name"),
               "classify": _late(gemini_llm, "classify_error")},
    "claude": {"label": "Claude", "ask": _late(llm, "ask_claude"), "sdk": _late(llm, "sdk_installed"),
               "configured": _late(llm, "credentials_configured"), "model": _late(llm, "model_name"),
               "classify": _late(llm, "classify_error")},
}


def provider_order():
    first = os.environ.get("COPILOT_PROVIDER", "gemini").strip().lower()
    return ["claude", "gemini"] if first == "claude" else ["gemini", "claude"]


def ready_providers():
    """Providers that can be called right now (SDK installed and key configured)."""
    return [p for p in provider_order() if PROVIDERS[p]["sdk"]() and PROVIDERS[p]["configured"]()]


def status():
    ready = ready_providers()
    sdk_any = any(PROVIDERS[p]["sdk"]() for p in PROVIDERS)
    reason = None
    if not ready:
        reason = "no AI SDK installed" if not sdk_any else "no API key configured (GEMINI_API_KEY or ANTHROPIC_API_KEY)"
    return {
        "llm_ready": bool(ready),
        "provider": PROVIDERS[ready[0]]["label"] if ready else None,
        "model": PROVIDERS[ready[0]]["model"]() if ready else None,
        "backup": [PROVIDERS[p]["label"] for p in ready[1:]],
        "sdk_installed": sdk_any,
        "credentials_configured": bool(ready),
        "reason": reason,
    }


def clean_history(history):
    """Keep the last few text-only turns, alternating user/assistant and starting with user."""
    turns = []
    for h in list(history or [])[-2 * MAX_HISTORY_TURNS:]:
        role, content = (h or {}).get("role"), (h or {}).get("content")
        if role not in ("user", "assistant") or not isinstance(content, str) or not content.strip():
            continue
        content = content[:MAX_TURN_CHARS]
        if turns and turns[-1]["role"] == role:
            turns[-1]["content"] += "\n\n" + content
        else:
            turns.append({"role": role, "content": content})
    while turns and turns[0]["role"] != "user":
        turns.pop(0)
    if turns and turns[-1]["role"] == "user":  # the new question will be the next user turn
        turns.pop()
    return turns


def answer(ev, question, aircraft_id=None, t=None, history=None, force_offline=False, client=None,
           gemini_client=None):
    """client / gemini_client: injected API clients (used by tests). When either is
    given, exactly those providers are used, so tests never reach a real API."""
    question = (question or "").strip()[:MAX_QUESTION]
    a = ev.resolve(aircraft_id)
    t = None if t is None or a is None else max(0, min(3600, int(t)))
    time_label = "the end of its last flight" if t is None else clock(t)
    started = time.monotonic()

    if client is not None or gemini_client is not None:
        injected = {"gemini": gemini_client, "claude": client}
        chain = [(p, injected[p]) for p in provider_order() if injected[p] is not None]
    else:
        chain = [(p, None) for p in ready_providers()]

    reason, kind = None, None
    if force_offline:
        reason, kind = "Offline mode selected", "forced"
    elif not question:
        reason, kind = "Empty question", "empty"
    elif not chain:
        sdk_any = any(PROVIDERS[p]["sdk"]() for p in PROVIDERS)
        reason, kind = ("No AI SDK installed", "sdk") if not sdk_any else ("No API key configured", "auth")
    else:
        failures = []
        hist = clean_history(history)
        for name, injected_client in chain:
            spec = PROVIDERS[name]
            try:
                out = spec["ask"](ev, question, a, time_label, hist, client=injected_client)
                return {**out, "mode": name, "provider": spec["label"],
                        "fallback_reason": "; ".join(failures) or None, "fallback_kind": None,
                        "latency_ms": round(1000 * (time.monotonic() - started)), "aircraft_id": a}
            except CopilotUnavailable as e:
                kind, msg = e.kind, e.reason
            except Exception as e:  # noqa: BLE001 -- the copilot must always answer
                kind, msg = spec["classify"](e)
            failures.append(f"{spec['label']}: {msg}")
        reason = "; ".join(failures)

    text, used = answer_offline(ev, question, a, t)
    return {
        "answer": text,
        "tools_used": [{"name": n, "input": {}} for n in used],
        "usage": None,
        "model": "offline engine",
        "mode": "offline",
        "provider": None,
        "fallback_reason": reason,
        "fallback_kind": kind,
        "latency_ms": round(1000 * (time.monotonic() - started)),
        "aircraft_id": a,
    }
