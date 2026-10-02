"""Claude path of the maintenance copilot.

A tool-use loop over the read-only evidence tools in evidence.py. Claude never
sees raw files or the network; it can only call those tools, and the system
prompt requires every number to come from them. Any failure (no SDK, no key,
no credit, rate limit, network, timeout, refusal, empty answer) raises
CopilotUnavailable with a human-readable reason, and the service falls back to
the offline engine.

Defaults: model claude-opus-5-5 (override with COPILOT_MODEL), effort medium
(COPILOT_EFFORT), short request timeout so a failing call falls back within
seconds, and server-side refusal fallbacks (beta) enabled.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from aerotwin.copilot.evidence import TOOL_SPECS, run_tool

DEFAULT_MODEL = "claude-opus-5-5"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
MAX_TOOL_ROUNDS = 6
REQUEST_TIMEOUT_S = 30.0
TOTAL_BUDGET_S = 75.0

SYSTEM_PROMPT = """You are the AeroTwin Maintenance Copilot. You help UAV maintenance engineers understand the output of a \
physics-informed digital twin of Rotax 912-class aero-piston engines: an unsupervised ML ensemble, a Bayesian particle-filter \
health twin, a physics signature check, explainable-AI sensor attributions and a Go/No-Go mission advisor.

How to answer:
- Base every statement about an aircraft, fault, reading, limit or number on data returned by your tools in this \
conversation. Call the tools you need before answering; for a question about one aircraft, call get_aircraft_status.
- Quote numbers as the tools return them, with units, and name the source ("Bayesian twin", "ML ensemble", "signature \
check", "explainable AI", "engine limits", "validation results").
- If the tools do not contain the answer, say that it is not in the digital-twin data and suggest what to check. Never \
invent readings, limits, part numbers, intervals or procedures.
- The Go/No-Go decision belongs to the digital twin's mission advisor. Explain it; never override it, and never suggest \
flying an aircraft that is NO-GO.
- Maintenance recommendations come from get_maintenance_actions; remind the reader to follow the approved Rotax \
maintenance documentation.
- Be honest about uncertainty: give the 90% intervals when they exist, and say that the data come from simulated flights \
when the user asks about reliability or real-world use.

Style: concise and technician-friendly. Lead with the answer in one sentence that contains the decision or the key number \
in **bold**, then short bullet points. Use plain markdown only: paragraphs, bullet lists, numbered lists, **bold** and \
### headings. No tables, no HTML. Stay under about 250 words unless the user asks for more detail."""


class CopilotUnavailable(Exception):
    def __init__(self, reason, kind="unknown"):
        super().__init__(reason)
        self.reason = reason
        self.kind = kind


def load_env_file(path):
    """Minimal .env reader (KEY=VALUE lines) so the API key can live in a git-ignored
    file next to the project. Existing environment variables win."""
    p = Path(path)
    if not p.is_file():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and v and k not in os.environ:
            os.environ[k] = v


def sdk_installed():
    try:
        import anthropic  # noqa: F401
        return True
    except ImportError:
        return False


def credentials_configured():
    """True when the SDK can find credentials: an API key / auth token, or an
    `ant auth login` profile on disk. Never returns or logs the key itself."""
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return True
    return (Path.home() / ".config" / "anthropic").is_dir()


def model_name():
    return os.environ.get("COPILOT_MODEL", DEFAULT_MODEL)


def classify_error(e):
    """Map any exception from the SDK to (kind, human-readable reason)."""
    try:
        import anthropic
    except ImportError:
        return "sdk", "Anthropic SDK not installed"
    msg = str(getattr(e, "message", "") or e)
    low = msg.lower()
    if isinstance(e, anthropic.APIStatusError) and ("credit" in low or "billing" in low):
        return "billing", "API credit balance too low; add credits at console.anthropic.com"
    if isinstance(e, anthropic.AuthenticationError):
        return "auth", "API key missing or invalid"
    if isinstance(e, anthropic.PermissionDeniedError):
        return "permission", "API key is not allowed to use this model"
    if isinstance(e, anthropic.NotFoundError):
        return "model", f"Model '{model_name()}' is not available to this API key"
    if isinstance(e, anthropic.RateLimitError):
        return "rate_limit", "API rate limit reached; try again in a minute"
    if isinstance(e, anthropic.BadRequestError):
        return "bad_request", f"Request rejected by the API: {msg[:160]}"
    if isinstance(e, anthropic.APITimeoutError):  # subclass of APIConnectionError, so check first
        return "timeout", "Claude API timed out"
    if isinstance(e, anthropic.APIConnectionError):
        return "network", "Cannot reach the Claude API (no internet connection?)"
    if isinstance(e, anthropic.APIStatusError):
        return "server", f"Claude API unavailable (HTTP {e.status_code})"
    return "unknown", f"Unexpected error ({type(e).__name__})"


def _context_line(aircraft_id, time_label):
    if aircraft_id:
        return f"[Dashboard context: the engineer is viewing aircraft {aircraft_id} at {time_label}.]"
    return "[Dashboard context: fleet view, no aircraft selected.]"


def _create(client, messages, use_fallbacks):
    kwargs = dict(
        model=model_name(),
        max_tokens=16000,
        system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
        tools=TOOL_SPECS,
        messages=messages,
        output_config={"effort": os.environ.get("COPILOT_EFFORT", "medium")},
    )
    if use_fallbacks:
        # Server-side refusal fallback: a declined request is re-run on Anthropic's
        # recommended fallback model inside the same call.
        return client.beta.messages.create(betas=[FALLBACK_BETA], fallbacks="default", **kwargs)
    return client.messages.create(**kwargs)


def ask_claude(ev, question, aircraft_id=None, time_label="the end of its last flight", history=(), client=None):
    """Returns dict(answer, tools_used, usage, model). Raises CopilotUnavailable."""
    if client is None:
        try:
            import anthropic
        except ImportError:
            raise CopilotUnavailable("Anthropic SDK not installed (pip install anthropic)", "sdk")
        client = anthropic.Anthropic(timeout=REQUEST_TIMEOUT_S, max_retries=1)

    base = list(history) + [{"role": "user", "content": f"{_context_line(aircraft_id, time_label)}\n\n{question}"}]
    use_fallbacks = os.environ.get("COPILOT_FALLBACKS", "1") != "0"
    start = time.monotonic()

    while True:  # at most two passes: with refusal fallbacks, then once without if the API rejects them
        messages = list(base)
        tools_used, usage = [], {"input_tokens": 0, "output_tokens": 0}
        try:
            for _ in range(MAX_TOOL_ROUNDS):
                if time.monotonic() - start > TOTAL_BUDGET_S:
                    raise CopilotUnavailable("Claude took too long to answer", "timeout")
                resp = _create(client, messages, use_fallbacks)
                u = getattr(resp, "usage", None)
                if u is not None:
                    usage["input_tokens"] += getattr(u, "input_tokens", 0) or 0
                    usage["output_tokens"] += getattr(u, "output_tokens", 0) or 0

                if resp.stop_reason == "refusal":
                    raise CopilotUnavailable("Claude declined to answer this request", "refusal")

                if resp.stop_reason == "tool_use":
                    # append the assistant turn unchanged (keeps thinking blocks valid), then all results in ONE user turn
                    messages.append({"role": "assistant", "content": resp.content})
                    results = []
                    for block in resp.content:
                        if getattr(block, "type", None) != "tool_use":
                            continue
                        out = run_tool(ev, block.name, block.input)
                        tools_used.append({"name": block.name, "input": block.input if isinstance(block.input, dict) else {}})
                        results.append({"type": "tool_result", "tool_use_id": block.id,
                                        "content": json.dumps(out, ensure_ascii=False), "is_error": "error" in out})
                    if not results:
                        raise CopilotUnavailable("Claude asked for a tool but sent no tool call", "protocol")
                    messages.append({"role": "user", "content": results})
                    continue

                text = "".join(getattr(b, "text", "") for b in resp.content if getattr(b, "type", None) == "text").strip()
                if not text:
                    raise CopilotUnavailable("Claude returned an empty answer", "empty")
                if resp.stop_reason == "max_tokens":
                    text += "\n\n_(Answer cut short.)_"
                return {"answer": text, "tools_used": tools_used, "usage": usage, "model": getattr(resp, "model", model_name())}
            raise CopilotUnavailable("Claude needed too many tool calls", "loop")
        except CopilotUnavailable:
            raise
        except Exception as e:  # noqa: BLE001 -- every SDK failure becomes a fallback reason
            kind, reason = classify_error(e)
            if use_fallbacks and kind == "bad_request" and "fallback" in reason.lower():
                use_fallbacks = False  # account or model does not accept refusal fallbacks: retry once without
                continue
            raise CopilotUnavailable(reason, kind) from e
