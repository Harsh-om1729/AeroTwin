"""AeroTwin Digital Twin API.

Serves the React dashboard (dashboard/dist) and a JSON API under /api.
Every number the API returns is computed by the real pipeline
(healthy physics twin -> residuals -> IF/PCA/LSTM-AE -> fusion -> Health
Index -> alert -> RUL -> fault diagnosis -> Go/No-Go); nothing is mocked.

    uvicorn backend.main:app --port 8000
"""
import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from aerotwin.diagnosis.fault_diagnosis import FAULT_ACTIONS, FAULT_LABELS
from aerotwin.evaluation.report import load_or_build
from aerotwin.inference.replay import DATA_DIR, compute_mission_timeline, get_bundle, list_missions, load_mission_df
from aerotwin.inference.simulate import PROFILES, SEVERITY_MULT, run_scenario
from aerotwin.copilot import service as copilot
from aerotwin.copilot.evidence import Evidence
from aerotwin.copilot.llm import load_env_file

ROOT = Path(__file__).parent.parent
DIST = ROOT / "dashboard" / "dist"

# Optional git-ignored .env with ANTHROPIC_API_KEY / COPILOT_MODEL for the AI copilot
load_env_file(ROOT / ".env")

# Demo fleet: each airframe's "last flight" is a real held-out test mission
# (never seen in training), replayed through the full pipeline at start-up.
FLEET = [
    {"id": "AT-101", "callsign": "Garuda 1", "split": "test_healthy", "mission_id": "test_8_5"},
    {"id": "AT-102", "callsign": "Garuda 2", "split": "test_fault", "mission_id": "fault_9_cooling_degradation_1"},
    {"id": "AT-103", "callsign": "Garuda 3", "split": "test_healthy", "mission_id": "test_9_3"},
    {"id": "AT-104", "callsign": "Garuda 4", "split": "test_fault", "mission_id": "fault_10_lubrication_0"},
    {"id": "AT-105", "callsign": "Garuda 5", "split": "test_fault", "mission_id": "fault_8_misfire_0"},
    {"id": "AT-106", "callsign": "Garuda 6", "split": "test_healthy", "mission_id": "test_10_12"},
    {"id": "AT-107", "callsign": "Garuda 7", "split": "test_fault", "mission_id": "fault_9_injector_abnormality_2"},
    {"id": "AT-108", "callsign": "Garuda 8", "split": "test_fault", "mission_id": "fault_10_abnormal_vibration_3"},
]

_state = {}


def _truth(split, mission_id):
    if split != "test_fault":
        return {"fault_type": None}
    r = _state["fault_log"].loc[mission_id]
    return {"fault_type": r["fault_type"], "fault_start_t": float(r["fault_start_t"]),
            "failure_t": float(r["failure_t"]), "rate": float(r["severity"])}


def _status(hi):
    return "nominal" if hi >= 80 else "warning" if hi >= 50 else "critical"


def _summary(entry, timeline):
    """Fleet-card summary of an airframe's last flight."""
    last = timeline[-1]
    first_alert = next((r for r in timeline if r["alert"]), None)
    diag = next((r["diagnosis"] for r in reversed(timeline) if r["diagnosis"]), None)
    hi_end = sorted(r["hi"] for r in timeline[-5:])[2]  # median of last 5 windows
    return {
        **{k: entry[k] for k in ("id", "callsign", "mission_id", "split")},
        "hi": round(hi_end, 1),
        "status": "critical" if last["alert_latched"] else _status(hi_end),
        "decision": last["advisor"]["decision"],
        "first_alert_t": first_alert["t"] if first_alert else None,
        "diagnosis": diag,
        "flight_s": last["t"],
        "spark": [round(r["hi_smooth"], 1) for r in timeline[::6]],
    }


@asynccontextmanager
async def lifespan(app):
    bundle = get_bundle()
    _state["fault_log"] = pd.read_csv(DATA_DIR / "fault_log.csv").set_index("mission_id")
    _state["timelines"] = {
        e["id"]: compute_mission_timeline(load_mission_df(e["split"], e["mission_id"]), bundle) for e in FLEET
    }
    # Validation report over the full held-out test set (cached on disk;
    # rebuilt automatically if the models are retrained).
    _state["report"] = load_or_build()
    gap_path = ROOT / "cache" / "gap_study.json"
    _state["evidence"] = Evidence(FLEET, _state["timelines"], bundle.cfg, _state["report"],
                                  json.load(open(gap_path)) if gap_path.exists() else None)
    yield


app = FastAPI(title="AeroTwin Digital Twin API", version="2.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/api/meta")
def meta():
    b = get_bundle()
    return {
        "engine": b.cfg,
        "fault_labels": FAULT_LABELS,
        "fault_actions": FAULT_ACTIONS,
        "profiles": PROFILES,
        "severities": list(SEVERITY_MULT),
        "models": b.model_names,
        "window_size_s": b.window_size,
        "stride_s": b.stride,
        "hi_exponent_p": b.p_calibrated,
    }


@app.get("/api/fleet")
def fleet():
    return [_summary(e, _state["timelines"][e["id"]]) for e in FLEET]


@app.get("/api/fleet/{airframe_id}")
def airframe(airframe_id: str):
    entry = next((e for e in FLEET if e["id"] == airframe_id), None)
    if entry is None:
        raise HTTPException(404, "Airframe not found")
    tl = _state["timelines"][airframe_id]
    return {"summary": _summary(entry, tl), "truth": _truth(entry["split"], entry["mission_id"]), "timeline": tl}


@app.get("/api/missions")
def missions():
    return list_missions()


@app.get("/api/missions/{split}/{mission_id}")
def mission(split: str, mission_id: str):
    if split not in ("test_healthy", "test_fault"):
        raise HTTPException(400, "split must be test_healthy or test_fault")
    try:
        df = load_mission_df(split, mission_id)
    except KeyError:
        raise HTTPException(404, "Mission not found")
    return {"truth": _truth(split, mission_id), "timeline": compute_mission_timeline(df, get_bundle())}


@app.get("/api/results")
def results():
    return _state["report"]


class CopilotQuestion(BaseModel):
    question: str
    aircraft_id: Optional[str] = None
    t: Optional[float] = None
    history: list = []
    force_offline: bool = False


@app.get("/api/copilot/status")
def copilot_status():
    """Whether the Claude path is configured. Never exposes the key."""
    return copilot.status()


@app.post("/api/copilot")
async def copilot_ask(q: CopilotQuestion):
    """Grounded maintenance Q&A. Always answers: Claude when available, otherwise
    the offline engine, with the reason in `fallback_reason`."""
    return await asyncio.to_thread(copilot.answer, _state["evidence"], q.question, q.aircraft_id, q.t,
                                   q.history, q.force_offline)


@app.get("/api/gap-study")
def gap_study():
    """Reality-gap robustness study (python3 -m aerotwin.evaluation.gap_study)."""
    path = ROOT / "cache" / "gap_study.json"
    if not path.exists():
        raise HTTPException(404, "Run `python3 -m aerotwin.evaluation.gap_study` to build the reality-gap study.")
    return json.load(open(path))


class Scenario(BaseModel):
    fault_type: Optional[str] = None
    severity: str = "moderate"
    onset_s: int = 1200
    profile: str = "standard"
    seed: Optional[int] = None
    gap: float = 0.0
    calibrate: bool = False


@app.post("/api/simulate")
async def simulate(s: Scenario):
    try:
        # CPU-bound (~0.5 s); keep the event loop free for other requests
        return await asyncio.to_thread(run_scenario, s.fault_type or None, s.severity, s.onset_s, s.profile, s.seed,
                                       s.gap, s.calibrate)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.websocket("/api/stream/{airframe_id}")
async def stream(websocket: WebSocket, airframe_id: str, speed: float = 5.0):
    """Streams an airframe's timeline window-by-window (one window = 10 s of
    flight) at `speed` windows/second, looping -- a live telemetry feed for
    external clients. The dashboard itself replays client-side so it can
    pause and scrub."""
    await websocket.accept()
    tl = _state["timelines"].get(airframe_id)
    if tl is None:
        await websocket.close(code=4404)
        return
    try:
        i = 0
        while True:
            await websocket.send_json(tl[i % len(tl)])
            await asyncio.sleep(1.0 / max(0.5, min(speed, 50.0)))
            i += 1
    except (WebSocketDisconnect, RuntimeError):
        pass


# ---- Dashboard (production build) ----------------------------------------
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = DIST / path
        return FileResponse(f if path and f.is_file() else DIST / "index.html")
else:
    @app.get("/", include_in_schema=False)
    def root():
        return {"message": "AeroTwin API running. Build the dashboard (cd dashboard && npm run build) "
                           "or run it with `npm run dev`. API docs at /docs."}
