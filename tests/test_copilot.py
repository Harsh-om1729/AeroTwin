"""AI maintenance copilot: grounding, offline engine, Claude tool loop and
every fallback path. The Claude path is exercised with a fake client, so no
network, API key or credit is needed to run these tests."""
import json
from types import SimpleNamespace

import anthropic
import httpx2
import pytest

from google.genai import errors as genai_errors

from aerotwin.copilot import gemini_llm, llm, service
from aerotwin.copilot.evidence import Evidence, run_tool
from aerotwin.copilot.offline import answer_offline, detect_intent, extract_aircraft
from aerotwin.inference.replay import compute_mission_timeline, get_bundle, load_mission_df

FLEET = [
    {"id": "AT-101", "callsign": "Garuda 1", "split": "test_healthy", "mission_id": "test_8_5"},
    {"id": "AT-104", "callsign": "Garuda 4", "split": "test_fault", "mission_id": "fault_10_lubrication_0"},
    {"id": "AT-107", "callsign": "Garuda 7", "split": "test_fault", "mission_id": "fault_9_injector_abnormality_2"},
]


@pytest.fixture(scope="module")
def ev():
    b = get_bundle()
    tls = {e["id"]: compute_mission_timeline(load_mission_df(e["split"], e["mission_id"]), b) for e in FLEET}
    report = json.load(open("cache/results.json"))
    return Evidence(FLEET, tls, b.cfg, report)


# ------------------------------------------------------------ grounding layer
def test_tools_return_grounded_data_and_never_raise(ev):
    s = run_tool(ev, "get_aircraft_status", {"aircraft_id": "at104"})
    assert s["aircraft_id"] == "AT-104" and s["decision"] == "NO-GO"
    assert s["bayesian_twin"]["most_likely_fault"].startswith("Lubrication")
    assert json.dumps(s)  # serialisable
    assert "error" in run_tool(ev, "get_aircraft_status", {"aircraft_id": "AT-999"})
    assert "error" in run_tool(ev, "get_aircraft_status", {"aircraft_id": "AT-104", "t_seconds": "abc"})
    assert "error" in run_tool(ev, "no_such_tool", {})
    assert "error" in run_tool(ev, "get_maintenance_actions", {"fault_type": "warp core"})
    assert run_tool(ev, "get_maintenance_actions", {"fault_type": "lean cylinder"})["fault"].startswith("Lean cylinder")


def test_fleet_overview_is_sorted_by_risk(ev):
    rows = run_tool(ev, "get_fleet_overview", {})["aircraft"]
    assert [r["decision"] for r in rows][-1] == "GO" and rows[0]["decision"] == "NO-GO"


# ------------------------------------------------------------ offline engine
@pytest.mark.parametrize("q, intent", [
    ("Which aircraft should we inspect first?", "fleet"),
    ("Give me a fleet overview", "fleet"),
    ("What should the technician inspect?", "maintenance"),
    ("Why is AT-104 grounded?", "status"),
    ("How much remaining life does it have?", "rul"),
    ("Which sensors caused the alert?", "xai"),
    ("What happened during the flight?", "timeline"),
    ("What are the engine limits?", "limits"),
    ("How reliable is this system?", "reliability"),
])
def test_intent_detection(q, intent):
    assert detect_intent(q) == intent


def test_aircraft_extraction():
    assert extract_aircraft("why is at 104 down") == "AT-104"
    assert extract_aircraft("status of AT-107?") == "AT-107"
    assert extract_aircraft("no aircraft here") is None


def test_offline_status_matches_the_twin(ev):
    text, used = answer_offline(ev, "Why is AT-104 grounded?")
    s = ev.aircraft_status("AT-104")
    assert "**AT-104" in text and "NO-GO" in text and "Lubrication" in text
    assert str(s["bayesian_twin"]["component_health"]["median"]) in text  # exact number from the evidence
    assert used == ["get_aircraft_status"]


def test_offline_maintenance_names_cylinder_for_lean_fault(ev):
    text, used = answer_offline(ev, "What should the technician check?", aircraft_id="AT-107")
    assert "cylinder 1" in text and "Rotax" in text and "get_maintenance_actions" in used


def test_offline_healthy_aircraft_has_no_fault(ev):
    text, _ = answer_offline(ev, "What should we inspect?", aircraft_id="AT-101")
    assert "no fault signature" in text.lower()


def test_fleet_question_wins_over_selected_aircraft(ev):
    text, used = answer_offline(ev, "Which aircraft should we inspect first?", aircraft_id="AT-104")
    assert used == ["get_fleet_overview"] and "AT-107" in text
    text, used = answer_offline(ev, "Give me an overview of AT-107")
    assert used == ["get_aircraft_status"] and "AT-107" in text


def test_offline_other_intents(ev):
    assert "AT-104" in answer_offline(ev, "Give me a fleet overview")[0]
    assert "880" in answer_offline(ev, "What are the engine limits?")[0]
    assert "simulated" in answer_offline(ev, "How reliable is this?")[0].lower()
    assert "T+" in answer_offline(ev, "What happened?", aircraft_id="AT-104")[0]
    assert "%" in answer_offline(ev, "Which sensors caused the alert?", aircraft_id="AT-104")[0]
    assert "Unknown aircraft" in answer_offline(ev, "status of AT-999")[0]
    assert "fleet" in answer_offline(ev, "Why is it grounded?")[0].lower()  # no aircraft selected


# ------------------------------------------------------------ Claude path (fake client)
def _resp(stop_reason, content, model="claude-opus-5-5"):
    return SimpleNamespace(stop_reason=stop_reason, content=content, model=model,
                           usage=SimpleNamespace(input_tokens=100, output_tokens=20))


class FakeClient:
    """Mimics client.beta.messages.create / client.messages.create."""

    def __init__(self, script=None, beta_error=None, plain_script=None):
        self.script, self.calls, self.beta_error = list(script or []), [], beta_error
        self.plain_script = list(plain_script or [])
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._beta))
        self.messages = SimpleNamespace(create=self._plain)

    def _beta(self, **kw):
        self.calls.append(("beta", kw))
        if self.beta_error:
            raise self.beta_error
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def _plain(self, **kw):
        self.calls.append(("plain", kw))
        return self.plain_script.pop(0)


def test_claude_tool_loop_grounds_answer(ev):
    tool_call = SimpleNamespace(type="tool_use", id="tu1", name="get_aircraft_status", input={"aircraft_id": "AT-104"})
    client = FakeClient([
        _resp("tool_use", [SimpleNamespace(type="thinking", thinking=""), tool_call]),
        _resp("end_turn", [SimpleNamespace(type="text", text="**AT-104 is NO-GO** due to lubrication degradation.")]),
    ])
    out = service.answer(ev, "Why is AT-104 grounded?", "AT-104", client=client)
    assert out["mode"] == "claude" and out["fallback_reason"] is None
    assert out["tools_used"][0]["name"] == "get_aircraft_status"
    assert out["usage"] == {"input_tokens": 200, "output_tokens": 40}
    second = client.calls[1][1]
    # request shape: system prompt, all tools, effort, refusal fallbacks on the beta endpoint
    assert second["model"] == "claude-opus-5-5" and second["fallbacks"] == "default"
    assert second["betas"] == ["server-side-fallback-2026-07-01"] and second["output_config"]["effort"] == "medium"
    assert len(second["tools"]) == 6
    # history: user, assistant (unchanged content incl. thinking), ONE user turn with every tool result
    msgs = second["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant", "user"]
    assert "AT-104" in msgs[0]["content"] and msgs[1]["content"][0].type == "thinking"
    result = msgs[2]["content"][0]
    assert result["tool_use_id"] == "tu1" and json.loads(result["content"])["decision"] == "NO-GO"


def test_claude_receives_dashboard_time_context(ev):
    client = FakeClient([_resp("end_turn", [SimpleNamespace(type="text", text="ok")])])
    service.answer(ev, "status?", "AT-104", t=2000, client=client)
    assert "T+33:20" in client.calls[0][1]["messages"][-1]["content"]


def _status_error(cls, code, message):
    req = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    return cls(message, response=httpx2.Response(code, request=req), body=None)


REQ = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


@pytest.mark.parametrize("error, kind", [
    (_status_error(anthropic.BadRequestError, 400, "Your credit balance is too low to access the Anthropic API."), "billing"),
    (_status_error(anthropic.AuthenticationError, 401, "invalid x-api-key"), "auth"),
    (_status_error(anthropic.PermissionDeniedError, 403, "not allowed"), "permission"),
    (_status_error(anthropic.NotFoundError, 404, "model not found"), "model"),
    (_status_error(anthropic.RateLimitError, 429, "rate limited"), "rate_limit"),
    (_status_error(anthropic.InternalServerError, 529, "overloaded"), "server"),
    (anthropic.APITimeoutError(request=REQ), "timeout"),
    (anthropic.APIConnectionError(request=REQ), "network"),
    (RuntimeError("boom"), "unknown"),
])
def test_every_failure_falls_back_to_offline(ev, error, kind):
    out = service.answer(ev, "Why is AT-104 grounded?", "AT-104", client=FakeClient([error]))
    assert out["mode"] == "offline" and out["fallback_kind"] == kind and out["fallback_reason"]
    assert "AT-104" in out["answer"] and "NO-GO" in out["answer"]  # still a real, grounded answer


def test_refusal_and_empty_answers_fall_back(ev):
    out = service.answer(ev, "q about AT-104", "AT-104", client=FakeClient([_resp("refusal", [])]))
    assert out["mode"] == "offline" and out["fallback_kind"] == "refusal"
    out = service.answer(ev, "q about AT-104", "AT-104", client=FakeClient([_resp("end_turn", [])]))
    assert out["mode"] == "offline" and out["fallback_kind"] == "empty"


def test_endless_tool_calls_are_capped(ev):
    loop = _resp("tool_use", [SimpleNamespace(type="tool_use", id="x", name="get_engine_limits", input={})])
    out = service.answer(ev, "limits?", None, client=FakeClient([loop] * 10))
    assert out["mode"] == "offline" and out["fallback_kind"] == "loop"


def test_rejected_refusal_fallbacks_retry_once_without_them(ev):
    err = _status_error(anthropic.BadRequestError, 400, "fallbacks: not supported for this account")
    client = FakeClient(beta_error=err, plain_script=[_resp("end_turn", [SimpleNamespace(type="text", text="fine")])])
    out = service.answer(ev, "status of AT-104", "AT-104", client=client)
    assert out["mode"] == "claude" and out["answer"] == "fine"
    assert [c[0] for c in client.calls] == ["beta", "plain"] and "fallbacks" not in client.calls[1][1]


def test_no_key_means_offline_without_any_network_call(ev, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(llm, "credentials_configured", lambda: False)
    monkeypatch.setattr(gemini_llm, "credentials_configured", lambda: False)
    out = service.answer(ev, "Why is AT-104 grounded?", "AT-104")
    assert out["mode"] == "offline" and out["fallback_kind"] == "auth"
    assert service.status()["llm_ready"] is False


def test_force_offline(ev):
    out = service.answer(ev, "fleet overview", None, force_offline=True, client=FakeClient([]))
    assert out["mode"] == "offline" and out["fallback_kind"] == "forced"


def test_history_is_sanitised():
    h = [{"role": "assistant", "content": "hi"}, {"role": "user", "content": "a"}, {"role": "user", "content": "b"},
         {"role": "assistant", "content": "c"}, {"role": "system", "content": "evil"}, {"role": "user", "content": 5},
         {"role": "user", "content": "dangling"}]
    assert service.clean_history(h) == [{"role": "user", "content": "a\n\nb"}, {"role": "assistant", "content": "c"}]


def test_env_file_loader(tmp_path, monkeypatch):
    monkeypatch.delenv("COPILOT_TEST_KEY", raising=False)
    (tmp_path / ".env").write_text("# comment\nCOPILOT_TEST_KEY='abc'\nBROKEN LINE\n")
    llm.load_env_file(tmp_path / ".env")
    import os
    assert os.environ["COPILOT_TEST_KEY"] == "abc"


# ------------------------------------------------------------ Gemini path (fake client) + provider chain
def _gresp(parts, finish="STOP"):
    return SimpleNamespace(
        usage_metadata=SimpleNamespace(prompt_token_count=50, candidates_token_count=10),
        candidates=[SimpleNamespace(finish_reason=finish, content=SimpleNamespace(parts=parts))])


def _gpart(text=None, call=None, thought=None):
    return SimpleNamespace(text=text, thought=thought,
                           function_call=SimpleNamespace(name=call[0], args=call[1]) if call else None)


class FakeGemini:
    """Mimics google-genai: client.chats.create(...).send_message(...)."""

    def __init__(self, script):
        self.script, self.sent, self.created = list(script), [], []
        self.chats = SimpleNamespace(create=self._create)

    def _create(self, model, config, history):
        self.created.append({"model": model, "config": config, "history": history})
        return SimpleNamespace(send_message=self._send)

    def _send(self, msg):
        self.sent.append(msg)
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture(autouse=True)
def _single_gemini_model(monkeypatch):
    """Most tests use one Gemini model so a scripted failure is final; model fallback is tested separately."""
    monkeypatch.setenv("COPILOT_MODEL_GEMINI", "gemini-test-model")


def test_gemini_tool_loop_grounds_answer(ev):
    g = FakeGemini([
        _gresp([_gpart(call=("get_aircraft_status", {"aircraft_id": "AT-104"}))]),
        _gresp([_gpart(text="thinking...", thought=True), _gpart(text="**AT-104 is NO-GO** (lubrication).")]),
    ])
    out = service.answer(ev, "Why is AT-104 grounded?", "AT-104", gemini_client=g)
    assert out["mode"] == "gemini" and out["provider"] == "Gemini" and out["fallback_reason"] is None
    assert out["answer"] == "**AT-104 is NO-GO** (lubrication)."  # thought part excluded
    assert out["tools_used"][0]["name"] == "get_aircraft_status"
    assert out["usage"] == {"input_tokens": 100, "output_tokens": 20}
    cfg = g.created[0]["config"]
    assert cfg.system_instruction == llm.SYSTEM_PROMPT and len(cfg.tools[0].function_declarations) == 6
    assert "AT-104" in g.sent[0]  # first message: context + question
    fr = g.sent[1][0].function_response  # second message: the tool result, sent back as a function response
    assert fr.name == "get_aircraft_status" and fr.response["result"]["decision"] == "NO-GO"


@pytest.mark.parametrize("error, kind", [
    (genai_errors.ClientError(400, {"error": {"code": 400, "message": "API key not valid.", "status": "INVALID_ARGUMENT",
                                              "details": [{"reason": "API_KEY_INVALID"}]}}), "auth"),
    (genai_errors.ClientError(403, {"error": {"code": 403, "message": "denied", "status": "PERMISSION_DENIED"}}), "permission"),
    (genai_errors.ClientError(404, {"error": {"code": 404, "message": "model not found", "status": "NOT_FOUND"}}), "model"),
    (genai_errors.ClientError(429, {"error": {"code": 429, "message": "Resource exhausted", "status": "RESOURCE_EXHAUSTED"}}), "rate_limit"),
    (genai_errors.ServerError(503, {"error": {"code": 503, "message": "overloaded", "status": "UNAVAILABLE"}}), "server"),
    (TimeoutError("timed out"), "timeout"),
])
def test_gemini_failures_fall_back_to_offline(ev, error, kind):
    out = service.answer(ev, "Why is AT-104 grounded?", "AT-104", gemini_client=FakeGemini([error]))
    assert out["mode"] == "offline" and out["fallback_kind"] == kind and out["fallback_reason"].startswith("Gemini:")
    assert "NO-GO" in out["answer"]


def test_gemini_safety_block_and_empty_answer_fall_back(ev):
    out = service.answer(ev, "q AT-104", "AT-104", gemini_client=FakeGemini([_gresp([], finish="SAFETY")]))
    assert out["mode"] == "offline" and out["fallback_kind"] == "refusal"
    out = service.answer(ev, "q AT-104", "AT-104", gemini_client=FakeGemini([_gresp([_gpart(text="")])]))
    assert out["mode"] == "offline" and out["fallback_kind"] == "empty"


def test_gemini_failure_falls_back_to_claude_before_offline(ev):
    g = FakeGemini([genai_errors.ClientError(429, {"error": {"code": 429, "message": "quota", "status": "RESOURCE_EXHAUSTED"}})])
    c = FakeClient([_resp("end_turn", [SimpleNamespace(type="text", text="**AT-104 is NO-GO** (from Claude).")])])
    out = service.answer(ev, "Why is AT-104 grounded?", "AT-104", client=c, gemini_client=g)
    assert out["mode"] == "claude" and "from Claude" in out["answer"]
    assert out["fallback_reason"].startswith("Gemini: Quota or rate limit reached")


def test_provider_order_and_status(monkeypatch):
    monkeypatch.setattr(gemini_llm, "sdk_installed", lambda: True)
    monkeypatch.setattr(gemini_llm, "credentials_configured", lambda: True)
    monkeypatch.setattr(llm, "sdk_installed", lambda: True)
    monkeypatch.setattr(llm, "credentials_configured", lambda: True)
    monkeypatch.delenv("COPILOT_PROVIDER", raising=False)
    st = service.status()
    assert st["llm_ready"] and st["provider"] == "Gemini" and st["backup"] == ["Claude"]
    monkeypatch.setenv("COPILOT_PROVIDER", "claude")
    assert service.status()["provider"] == "Claude"
    monkeypatch.setattr(gemini_llm, "credentials_configured", lambda: False)
    monkeypatch.setattr(llm, "credentials_configured", lambda: False)
    st = service.status()
    assert not st["llm_ready"] and st["provider"] is None and "API key" in st["reason"]


def test_gemini_overloaded_model_falls_through_to_next_model(ev, monkeypatch):
    monkeypatch.setenv("COPILOT_MODEL_GEMINI", "model-a, model-b")
    busy = genai_errors.ServerError(503, {"error": {"code": 503, "message": "high demand", "status": "UNAVAILABLE"}})
    g = FakeGemini([busy, _gresp([_gpart(text="**AT-104 is NO-GO**")])])
    out = service.answer(ev, "Why is AT-104 grounded?", "AT-104", gemini_client=g)
    assert out["mode"] == "gemini" and out["model"] == "model-b"
    assert [c["model"] for c in g.created] == ["model-a", "model-b"]
    assert g.created[1]["history"] == []  # second model starts clean


def test_gemini_bad_key_does_not_try_other_models(ev, monkeypatch):
    monkeypatch.setenv("COPILOT_MODEL_GEMINI", "model-a, model-b")
    bad = genai_errors.ClientError(400, {"error": {"code": 400, "message": "API key not valid.", "status": "INVALID_ARGUMENT"}})
    g = FakeGemini([bad])
    out = service.answer(ev, "Why is AT-104 grounded?", "AT-104", gemini_client=g)
    assert out["mode"] == "offline" and out["fallback_kind"] == "auth" and len(g.created) == 1


def test_gemini_all_models_overloaded_reports_each(ev, monkeypatch):
    monkeypatch.setenv("COPILOT_MODEL_GEMINI", "model-a,model-b")
    busy = lambda: genai_errors.ServerError(503, {"error": {"code": 503, "message": "x", "status": "UNAVAILABLE"}})
    out = service.answer(ev, "Why is AT-104 grounded?", "AT-104", gemini_client=FakeGemini([busy(), busy()]))
    assert out["mode"] == "offline" and "model-a" in out["fallback_reason"] and "model-b" in out["fallback_reason"]


def test_default_gemini_models(monkeypatch):
    monkeypatch.delenv("COPILOT_MODEL_GEMINI", raising=False)
    assert gemini_llm.model_list() == gemini_llm.DEFAULT_MODELS and "gemini-2.5-flash" not in gemini_llm.DEFAULT_MODELS
