"""Gemini path of the maintenance copilot.

Same contract as the Claude path (llm.py): a tool-use loop over the read-only
evidence tools, the same system prompt and guardrails, and any failure raised
as CopilotUnavailable so the service can try the next provider or fall back
to the offline engine. Key: GEMINI_API_KEY in the git-ignored .env.

Models are tried in order (COPILOT_MODEL_GEMINI, comma-separated). If a model
is overloaded (503), retired for this key (404) or rate-limited (429), the
next model is tried; a bad key or billing problem stops immediately because
another model cannot fix it. Default order, checked on 2026-10-02 against a
real key: the fast lite models first (both answered with full tool use in
2-5 s while the larger flash models returned "high demand"), then
gemini-3.8-flash. gemini-2.5-flash is no longer available to new users.
"""
from __future__ import annotations

import os
import time

from aerotwin.copilot.evidence import TOOL_SPECS, run_tool
from aerotwin.copilot.llm import SYSTEM_PROMPT, CopilotUnavailable, _context_line

DEFAULT_MODELS = ["gemini-3.5-flash-lite", "gemini-flash-lite-latest", "gemini-3.8-flash"]
MAX_TOOL_ROUNDS = 6
REQUEST_TIMEOUT_MS = 30_000  # per request, so a stalled call falls back within seconds
TOTAL_BUDGET_S = 75.0
# errors after which another Gemini model may succeed
TRY_NEXT_MODEL = {"server", "model", "rate_limit", "timeout"}


def sdk_installed():
    try:
        import google.genai  # noqa: F401
        return True
    except ImportError:
        return False


def credentials_configured():
    return bool(os.environ.get("GEMINI_API_KEY"))


def model_list():
    raw = os.environ.get("COPILOT_MODEL_GEMINI", "")
    models = [m.strip() for m in raw.split(",") if m.strip()]
    return models or list(DEFAULT_MODELS)


def model_name():
    return model_list()[0]


def classify_error(e, model=None):
    """Map any exception from google-genai to (kind, human-readable reason)."""
    msg = str(e).lower()
    model = model or model_name()
    try:
        from google.genai import errors
    except ImportError:
        errors = None
    if errors is not None and isinstance(e, errors.APIError):
        code = e.code or 0
        if "api_key" in msg or "api key" in msg or code == 401:
            return "auth", "Gemini API key missing or invalid"
        if code == 403:
            return "permission", "Gemini API key is not allowed to use this model"
        if code == 404:
            return "model", f"model '{model}' is not available to this key"
        if code == 429:
            return "rate_limit", f"quota or rate limit reached for '{model}'"
        if "billing" in msg or "failed_precondition" in msg:
            return "billing", "Gemini API needs billing enabled (or is not available in this region)"
        if code >= 500:
            return "server", f"'{model}' is overloaded or unavailable (HTTP {code})"
        return "bad_request", f"request rejected by the Gemini API (HTTP {code})"
    name = type(e).__name__.lower()
    if "timeout" in name or "timed out" in msg:
        return "timeout", f"'{model}' timed out"
    if "connect" in name or "network" in msg or "name resolution" in msg:
        return "network", "cannot reach the Gemini API (no internet connection?)"
    return "unknown", f"unexpected error ({type(e).__name__})"


def _build_gemini_tools():
    from google.genai import types
    t_map = {"string": types.Type.STRING, "integer": types.Type.INTEGER, "number": types.Type.NUMBER,
             "boolean": types.Type.BOOLEAN}
    funcs = []
    for s in TOOL_SPECS:
        schema = s.get("input_schema", {})
        props = {k: types.Schema(type=t_map.get(v.get("type"), types.Type.STRING), description=v.get("description", ""))
                 for k, v in schema.get("properties", {}).items()}
        params = types.Schema(type=types.Type.OBJECT, properties=props, required=schema.get("required", [])) if props else None
        funcs.append(types.FunctionDeclaration(name=s["name"], description=s["description"], parameters=params))
    return [types.Tool(function_declarations=funcs)]


def _converse(client, model, ev, history_contents, first_message, start):
    """One complete tool-use conversation on one model."""
    from google.genai import types

    config = types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT, tools=_build_gemini_tools(), temperature=0.2)
    chat = client.chats.create(model=model, config=config, history=list(history_contents))  # fresh copy per model
    tools_used, usage = [], {"input_tokens": 0, "output_tokens": 0}
    msg = first_message
    for _ in range(MAX_TOOL_ROUNDS):
        if time.monotonic() - start > TOTAL_BUDGET_S:
            raise CopilotUnavailable("Gemini took too long to answer", "timeout")
        resp = chat.send_message(msg)
        um = getattr(resp, "usage_metadata", None)
        if um:
            usage["input_tokens"] += getattr(um, "prompt_token_count", 0) or 0
            usage["output_tokens"] += getattr(um, "candidates_token_count", 0) or 0
        if not resp.candidates:
            raise CopilotUnavailable("Gemini returned an empty answer", "empty")
        cand = resp.candidates[0]
        if "safety" in str(getattr(cand, "finish_reason", "") or "").lower():
            raise CopilotUnavailable("Gemini declined to answer this request", "refusal")
        parts = cand.content.parts if cand.content and cand.content.parts else []

        tool_calls = [p for p in parts if getattr(p, "function_call", None)]
        # skip "thought" parts (internal reasoning), keep only the answer text
        text = "".join(p.text for p in parts if getattr(p, "text", None) and not getattr(p, "thought", False)).strip()

        if not tool_calls:
            if not text:
                raise CopilotUnavailable("Gemini returned an empty answer", "empty")
            return {"answer": text, "tools_used": tools_used, "usage": usage, "model": model}

        results = []
        for tc in tool_calls:
            name = tc.function_call.name
            args = dict(tc.function_call.args or {})
            out = run_tool(ev, name, args)
            tools_used.append({"name": name, "input": args})
            results.append(types.Part.from_function_response(name=name, response={"result": out}))
        msg = results  # all results go back in one message
    raise CopilotUnavailable("Gemini needed too many tool calls", "loop")


def ask_gemini(ev, question, aircraft_id=None, time_label="the end of its last flight", history=(), client=None):
    """Returns dict(answer, tools_used, usage, model). Raises CopilotUnavailable."""
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        raise CopilotUnavailable("google-genai SDK not installed (pip install google-genai)", "sdk")
    if client is None:
        if not credentials_configured():
            raise CopilotUnavailable("No GEMINI_API_KEY configured", "auth")
        client = genai.Client(
            api_key=os.environ["GEMINI_API_KEY"],
            # one quick retry, then move on to the next model (the SDK default is 5 attempts with up to 60 s waits)
            http_options=types.HttpOptions(
                timeout=REQUEST_TIMEOUT_MS,
                retry_options=types.HttpRetryOptions(attempts=2, initial_delay=1.0, max_delay=4.0)),
        )

    history_contents = [types.Content(role="user" if h["role"] == "user" else "model",
                                      parts=[types.Part.from_text(text=h["content"])]) for h in history]
    first_message = f"{_context_line(aircraft_id, time_label)}\n\n{question}"
    start = time.monotonic()

    failures = []
    models = model_list()
    for i, model in enumerate(models):
        try:
            out = _converse(client, model, ev, history_contents, first_message, start)
            if failures:
                out["model_notes"] = failures
            return out
        except CopilotUnavailable as e:
            kind, reason = e.kind, e.reason
        except Exception as e:  # noqa: BLE001 -- classified below
            kind, reason = classify_error(e, model)
        failures.append(reason)
        if kind not in TRY_NEXT_MODEL or i == len(models) - 1 or time.monotonic() - start > TOTAL_BUDGET_S:
            detail = reason if len(failures) == 1 else "all models failed: " + "; ".join(failures)
            raise CopilotUnavailable(detail[0].upper() + detail[1:], kind)
