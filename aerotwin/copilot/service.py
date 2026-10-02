"""Copilot entry point: try Claude, fall back to the offline engine.

The caller always gets an answer. `mode` says who produced it ("claude" or
"offline") and `fallback_reason` says why Claude was not used, so the UI can
show it honestly.
"""
from __future__ import annotations

import time

from aerotwin.copilot.evidence import clock
from aerotwin.copilot.llm import (CopilotUnavailable, ask_claude, classify_error, credentials_configured,
                                  model_name, sdk_installed)
from aerotwin.copilot.offline import answer_offline

MAX_QUESTION = 2000
MAX_HISTORY_TURNS = 8
MAX_TURN_CHARS = 4000


def status():
    sdk, creds = sdk_installed(), credentials_configured()
    return {
        "llm_ready": sdk and creds,
        "model": model_name(),
        "sdk_installed": sdk,
        "credentials_configured": creds,
        "reason": None if sdk and creds else
        ("Anthropic SDK not installed" if not sdk else "no API key configured"),
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


def answer(ev, question, aircraft_id=None, t=None, history=None, force_offline=False, client=None):
    question = (question or "").strip()[:MAX_QUESTION]
    a = ev.resolve(aircraft_id)
    t = None if t is None or a is None else max(0, min(3600, int(t)))
    time_label = "the end of its last flight" if t is None else clock(t)
    started = time.monotonic()

    reason, kind = None, None
    if force_offline:
        reason, kind = "Offline mode selected", "forced"
    elif not question:
        reason, kind = "Empty question", "empty"
    elif client is None and not sdk_installed():
        reason, kind = "Anthropic SDK not installed", "sdk"
    elif client is None and not credentials_configured():
        reason, kind = "No API key configured", "auth"
    else:
        try:
            out = ask_claude(ev, question, a, time_label, clean_history(history), client=client)
            return {**out, "mode": "claude", "fallback_reason": None, "fallback_kind": None,
                    "latency_ms": round(1000 * (time.monotonic() - started)), "aircraft_id": a}
        except CopilotUnavailable as e:
            reason, kind = e.reason, e.kind
        except Exception as e:  # noqa: BLE001 -- the copilot must always answer
            kind, reason = classify_error(e)

    text, used = answer_offline(ev, question, a, t)
    return {
        "answer": text,
        "tools_used": [{"name": n, "input": {}} for n in used],
        "usage": None,
        "model": "offline engine",
        "mode": "offline",
        "fallback_reason": reason,
        "fallback_kind": kind,
        "latency_ms": round(1000 * (time.monotonic() - started)),
        "aircraft_id": a,
    }
