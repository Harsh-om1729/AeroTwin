# AeroTwin: Aero-Piston Engine Digital Twin

**Physics-informed digital twin for predictive health monitoring of MALE-UAV aero-piston engines (Rotax 912 class).**

AeroTwin compares every engine sensor against a physics model of a *healthy* engine flying the same conditions.
An ensemble of three AI detectors watches the difference (the residual). The system turns that into a 0–100 Health
Index, warns before failure, names the fault and the cylinder, estimates remaining useful life, and gives a
Go / Caution / No-Go decision for the next mission.

> **Read this first.** All fault results are **simulated**. The healthy twin and the particle filter use the *same equations*
> as the simulator, and every simulated engine is physically identical. The numbers below are therefore an
> **upper bound** on what this design can do, not a measurement of a real engine. They come from a frozen test
> split (dataset v2.1) generated from disjoint seeds. Thresholds and diagnosis rules were fixed on a separate
> development split and never tuned on the test split, but the split has been re-run after retraining and bug fixes.

## ⭐ Flagship: Bayesian health twin (particle filter)

The ML ensemble answers *"is something abnormal?"*. The flagship answers *"which component is degrading, how
healthy is it right now, and when will it fail, with what certainty?"*

* **Bank of 11 hypothesis-specific particle filters** (lubrication, cooling, lean cylinder ×4, misfire ×4,
  bearing; 120 particles each) with **Bayesian model selection** between hypotheses.
* Each particle carries hidden health `h`, degradation rate `r`, an unknown-onset flag (jump-Markov), and its own
  thermal state, pushed through the physics engine model every second.
* **RUL is a probability distribution**: each particle is extrapolated to the functional-failure health limit.
* The filter does **not** know the true degradation law, rate or onset. Its parameters were tuned only on separately
  simulated flights (`aerotwin/twin/tune.py`), never on the test split.

| Test split (60 fault + 60 healthy simulated flights) | Bayesian twin | ML ensemble |
|---|---|---|
| Faults detected before failure | 60/60 (95% CI 94–100%) | 58/60 (95% CI 88–100%) |
| Fault type + cylinder correct | 60/60 (95% CI 94–100%) | 58/60 type, 24/24 cylinder |
| False-alarm events in 80.3 healthy flight-hours | **0** (95% upper bound 0.046 /FH) | 2 (95% CI 0.003–0.090 /FH) |
| Median detection delay after onset | 37.5 s | 108 s |
| 90% RUL interval contains the true failure time | **91.1%** (95% CI 88.8–92.9%) | no intervals |
| RUL median absolute error | 56 s | 263 s (HI linear trend)* |
| RUL within ±20% of truth (α-λ) | 36% | 0.8% (HI linear trend)* |
| Hidden-health tracking error (MAE) | 0.006 | n/a |

The delays are not a like-for-like race: the ML path waits for a 60 s window plus 8 × 10 s of persistence, while
the filter decides at 1 Hz using the simulator's own equations. *The HI linear trend extrapolates the anomaly
index to 50, not to the physical failure threshold that defines the truth, so part of its error is a definition
mismatch.

Code: `aerotwin/twin/particle_filter.py` · UI: *Twin Replay → Bayesian health twin* and *Model Validation → Flagship*.

## AI Maintenance Copilot (Claude, with an offline fallback)

A chat page (**AI Copilot**) where an engineer asks plain-language questions: "Which aircraft should we inspect
first?", "Why is AT-104 grounded?", "What should the technician check on AT-107?", "How reliable is this system?".

* **Grounded by construction** (`aerotwin/copilot/`). The model can only read the twin's own outputs through six
  read-only tools: fleet overview, aircraft status at any flight time, event timeline, engine limits, maintenance
  actions, validation results. The system prompt requires every number to come from a tool, says "not in the data"
  otherwise, and forbids overriding or softening a Go/No-Go decision.
* **Two AI providers with automatic backup** (`service.py`): Google **Gemini** (`gemini_llm.py`, models tried in order `gemini-3.5-flash-lite`, `gemini-flash-lite-latest`, `gemini-3.8-flash`;
  change with `COPILOT_MODEL_GEMINI`) is tried first, then **Claude** (`llm.py`, `claude-opus-5-5`, change with
  `COPILOT_MODEL`; effort `medium`, server-side refusal fallbacks), then the offline engine. Set `COPILOT_PROVIDER=claude`
  to try Claude first. Both use the same tools, prompt and guardrails, at most 6 tool rounds, 30 s per request.
* **Always answers** (`service.py`, `offline.py`). If no AI provider can answer (no key, credit exhausted, invalid key,
  rate limit, no internet, timeout, refusal, empty reply), the offline engine answers the same question from the
  *same* evidence functions, and the UI shows which engine answered and why. Verified against the real API with an
  invalid key: a 401 fell back to a full offline answer in 0.7 s.
* **Key safety:** the key lives only in a git-ignored `.env` (see `.env.example`), is never sent to the browser and
  never logged.

Enable an AI provider (optional):

```bash
cp .env.example .env        # then add GEMINI_API_KEY= and/or ANTHROPIC_API_KEY=
pip install google-genai anthropic   # both already in requirements.txt
./run.sh
```

Without a key the copilot runs entirely offline, so the demo works with no internet.

## Robustness: a fair race, and what happens when the twin is wrong

**1. CUSUM baseline and matched comparison** (`aerotwin/models/cusum.py`, `report._amoc`). With an exact twin,
healthy residuals are white noise, and Page's CUSUM is the textbook optimal detector for a mean shift in that
case. Its threshold is calibrated on healthy validation flights only. Sweeping every method's threshold with the
same 3-window persistence and comparing at **≤ 0.05 false-alarm events per flight-hour (≥ 95% detected)**:

| Method | Median detection delay |
|---|---|
| Bayesian twin | 46 s |
| CUSUM | 54 s |
| ML ensemble (fused score) | not reachable under a 3-window rule; with its own 8-window rule: 0.025 /FH, 97% detected, 108 s |

On a perfectly matched twin, plain CUSUM is as good as anything else. The ML ensemble's value is not detection speed.
These thresholds were picked by sweeping the test split itself, so this comparison is descriptive, not a tuned result.

**2. Reality-gap study** (`aerotwin/simulator/variation.py`, `aerotwin/evaluation/gap_study.py`). A "true" engine
departs from the twin by a knob `gap` ∈ [0, 1]: per-engine CHT/EGT offsets, oil-pump and vibration gains,
heat-rejection error, thermal time constants ±30%, sensor bias, random-walk drift and AR(1) noise (magnitudes at
gap = 1 are listed in the code, fixed before the study). The same 30 flights (10 healthy, 20 faulty) are flown at 8
gap levels with identical noise, onsets and engine identities, and each method keeps its deployed threshold. A
detection only counts if a *new* alarm starts after the fault begins.

Largest gap at which a method stays usable (≤ 5% of healthy time in false alarm, ≥ 90% of faults caught):

| | ML ensemble | Bayesian twin | CUSUM |
|---|---|---|---|
| Uncalibrated twin | 0.00 | **0.10** | 0.00 |
| Per-engine calibration (one healthy reference flight) | 0.20 | **0.50** | 0.05 |

* The optimal-on-paper CUSUM is the **most fragile**: at gap 0.05 it spends 82% of healthy time in alarm.
* The Bayesian twin degrades most gracefully, and with calibration keeps ≥ 95% correct diagnosis up to gap 0.75 (74% at gap 1.0).
* **Honest caveats:** even calibrated, the twin's short false-alarm *events* grow with the gap (20 in 17 h at gap 0.2),
  and its 90% RUL intervals become over-confident as the gap grows (calibrated: 88% coverage at gap 0.1, 63% at
  gap 0.5), because the filter does not yet model mismatch. No method is deployable on a poorly matched engine without calibration.

Run: `python3 -m aerotwin.evaluation.gap_study` (~5 min, cached in `cache/gap_study.json`). The Fault Injection Lab
has a reality-gap slider and a calibration toggle to see this live.

## Explainable AI: which sensors caused the alert, and are the explanations right?

Every window the ensemble flags gets a **sensor-level counterfactual explanation** (`aerotwin/xai/attribution.py`):
each of the 15 residual channels is reset to its healthy baseline, all three detectors are re-scored, and the drop in
each model's *raw* score (not its saturating percentile) is that sensor's share of the anomaly evidence. The dashboard
shows it per model and for the ensemble, with a counterfactual sentence ("if oil pressure had been healthy, the fused
percentile would drop from 97 to 49"). SHAP was not used: TreeSHAP covers only the Isolation Forest, and only at the
level of 45 window statistics, not sensors.

Explanations are **validated against the simulator's ground truth**: at the first alert of each test fault flight, is
the top-ranked sensor one the fault physically acts on? (58 flights: the two faults the ensemble missed have no alert to explain.)

| Whose explanation | Top sensor physically correct |
|---|---|
| Ensemble | **58/58** (95% CI 94–100%) |
| LSTM-AE | 58/58 |
| PCA-SPE | 57/58 |
| Isolation Forest | 53/58 |

The two false alarms on healthy flights are explained by a CHT 4 blip (61% of the evidence) and a CHT 1 blip (74%).

## Real flights: what happens outside the simulator

The simulated numbers above are an upper bound, so the same detectors were also run on real data: the
[NGAFID Aviation Maintenance Dataset](https://arxiv.org/abs/2210.07317) (flight-school Cessna 172s, not a Rotax 912).
The physics twin does not apply to this engine, so a **learned healthy baseline** (`aerotwin/real_engine/sim2real.py`)
predicts each sensor from RPM, fuel flow, outside air temperature, altitude, airspeed and vertical speed, using
after-maintenance flights. Its error on unseen healthy flights is about 9 °C for CHT and 18 °C for EGT. The particle
filter was not run. 10,177 of 11,269 usable benchmark flights (10,855 airborne hours) passed the data checks.

| Before vs after unplanned maintenance (1,986 test flights, ROC-AUC, 0.50 = coin flip) | Test | 95% CI |
|---|---|---|
| Fused ML ensemble | **0.51** | 0.49–0.53 |
| Isolation Forest / PCA / LSTM alone | 0.52 / 0.51 / 0.50 | all include 0.50 |
| Plain residual threshold | 0.50 | 0.47–0.53 |
| Low oil pressure (one residual) | **0.68** | 0.66–0.70 |

* **The ensemble is at chance level on real data.** It scored 0.54 on the development fold, and that did not hold on
  the test fold. Nothing was tuned after seeing the test fold. A supervised deep model reached 76.1% accuracy in the
  dataset paper, but it trains on these labels, so that is a reference and not a like-for-like comparison.
* **Low oil pressure held up, but be careful with it.** It was picked on the development fold as the best of 11 simple
  scores, and it was just as strong for baffle problems there (0.64), which should not change oil pressure. A repair
  visit that also changes the oil would produce the same pattern, so it is a lead to investigate, not a validated detector.
* **Limits of this data:** labels are per flight (before/after a repair), not fault times. "After" means the reported
  part was fixed, not that the engine is fault-free. There is no vibration or throttle channel and no aircraft or
  event id. Folds are consecutive blocks; flights of repairs inferred to cross folds were dropped, but one aircraft can
  still appear in several folds. Confidence intervals resample inferred repair groups, which over-split the true
  events (5,614 groups for 2,111 events), so they may be slightly narrow.

**Supervised training on the labels** (`aerotwin/evaluation/real_supervised.py`). Trained on 3,964 flights, chosen on the
development fold, then scored on 2,112 test flights. This is a second use of the test fold, after the evaluation above.

| Test AUC (95% CI) | All sensors | Without oil pressure | Oil pressure only |
|---|---|---|---|
| Gradient boosting | **0.74** (0.72–0.77) | 0.56 (0.54–0.58) | 0.72 (0.70–0.74) |
| 1D CNN | 0.70 (0.68–0.72) | 0.55 (0.52–0.57) | 0.75 (0.72–0.77) |

The main model has 67% balanced accuracy: it flags 67% of pre-maintenance flights and 32% of post-maintenance flights.
Removing one sensor removes most of the skill, so the models are mainly reading the oil-pressure shift. That makes
this a maintenance-*visit* classifier until the oil-change explanation is ruled out, not a proven fault detector. The
dataset has no service records to test that.

Run: extract the dataset anywhere under `data/`, then `python3 -m aerotwin.evaluation.real_report` (development fold,
~6 min the first time) and `--test` (frozen fold), then `python3 -m aerotwin.evaluation.real_supervised --test`. `2days/flight_data.pkl` is never loaded, because pickles can run code.

## ML ensemble results (same test split)

| Metric | Result |
|---|---|
| Faults detected after onset, before failure | 58/60 (two bearing-wear faults raised no new alert before their failure threshold) |
| Fault type correct at first alert (signature rules) | 58/60 (the same two flights have no alert to diagnose) |
| Faulty cylinder (lean cylinder / misfire flights) | 24/24 — the fault is always on cylinder 1 or 2 in this dataset |
| Median warning before the simulated failure threshold | 5.1 min (lubrication 16 min, misfire 10 s) |
| False-alarm events, single detectors vs fused | Isolation Forest 13 · PCA 32 · LSTM-AE 77 · **fused 2** |
| HI-trend RUL estimates on the conservative side | 97% |
| Healthy flights ever shown NO-GO | 2/60 (those two false alarms; none from a redline) |

All numbers are recomputed by `python3 -m aerotwin.evaluation.report` (cached in `cache/results.json`) and shown on the
dashboard's *Model Validation* page. Development numbers on the separate `val_fault` split come from
`python3 -m aerotwin.evaluation.report --dev`.

## Quick start

```bash
cd aero-digital-twin
./run.sh            # installs what's missing, builds the dashboard, opens http://localhost:8000
```

On a fresh clone, `run.sh` first generates the seeded dataset (~1 min; byte-identical on every machine) and the first
start evaluates the 120 test flights (~3 min), cached afterwards. Later starts take about 15 s.

* Dashboard: http://localhost:8000
* Interactive API docs (Swagger): http://localhost:8000/docs
* Developer mode with hot reload: `./run.sh --dev` → http://localhost:5173
* Stop everything: `./stop.sh` from the project folder, or Ctrl+C. Forgot? `./run.sh` clears an old copy by itself.
* Retrain the models: `./run.sh --retrain`
* Tests: `python3 -m pytest -q` (145 tests, one documented expected failure)

## Dashboard pages

| Page | What it shows |
|---|---|
| **Fleet Command** | 8 aircraft, Health Index, Go/No-Go, diagnosed fault, HI sparkline |
| **Twin Replay** | Replay of a simulated test flight with an animated engine schematic (cylinders coloured by CHT, flagged cylinder blinks), 6 gauges with twin-expected markers, Health Index & detector charts, measured-vs-twin plots, residual bars, diagnosis, RUL, event log, printable maintenance report |
| **Fault Injection Lab** | Pick a fault, severity, onset time and flight profile → a brand-new flight is simulated and analysed in ~1 s, with a verdict against hidden ground truth |
| **Model Validation** | KPIs, ablation (each model vs ensemble), confusion matrix, warning time per fault, RUL vs truth, healthy-HI distribution, all 60 fault flights (click to replay) |
| **How it works** | Pipeline, design decisions, dataset split, engine limits (Rotax manual), limitations |

## Architecture

```
telemetry (17 sensors, 1 Hz)
   │
   ├─► Physics twin (ISA atmosphere, Gagg-Ferrar power lapse, thermal lag) ─► expected healthy values
   │
   ▼
residuals = measured − expected   (15 channels + CHT/EGT spread)
   │  60 s windows, 10 s stride, standardised on healthy flights
   ├─► Isolation Forest ─┐
   ├─► PCA (SPE)        ─┼─► percentile fusion ─► Health Index 0–100 ─► alert (HI<50 for 80 s)
   └─► LSTM autoencoder ─┘                                │            ─► RUL (trend extrapolation)
                                                          ▼
                       physics-signature fault diagnosis (type + cylinder)
                                                          ▼
                       Go / Caution / No-Go advisor (+ Rotax 912 redlines)
```

| Folder | Contents |
|---|---|
| `aerotwin/simulator/` | Engine physics model, atmosphere, mission profiles, fault injection, dataset generator |
| `aerotwin/features/` | Residuals vs healthy twin, windowing + feature pipeline |
| `aerotwin/models/` | Isolation Forest, PCA-SPE, LSTM autoencoder, score fusion |
| `aerotwin/health/` | Health Index, alert logic, RUL |
| `aerotwin/twin/` | **Flagship** particle-filter health twin + tuning harness |
| `aerotwin/copilot/` | AI maintenance copilot: grounded tools, Claude tool loop, offline engine |
| `aerotwin/xai/` | Explainable AI: sensor-level counterfactual attribution |
| `aerotwin/models/cusum.py`, `aerotwin/simulator/variation.py` | CUSUM baseline; reality-gap engine for robustness studies |
| `aerotwin/diagnosis/` | Physics-signature fault isolation |
| `aerotwin/advisor/` | Go / Caution / No-Go mission advisor |
| `aerotwin/inference/` | Full-pipeline replay, on-demand scenario simulation |
| `aerotwin/real_engine/` | NGAFID loader and learned healthy baseline |
| `aerotwin/evaluation/` | Training, metrics, validation report, real-flight report |
| `backend/main.py` | FastAPI: REST + WebSocket, serves the dashboard |
| `dashboard/` | React + Vite + Recharts UI |
| `tests/` | Pytest suite |

## Rebuilding from scratch

```bash
python3 -m aerotwin.simulator.generate_dataset   # 308 seeded one-hour flights → data/ (dataset v2.1)
python3 -m aerotwin.evaluation.train_models      # trains + calibrates → models/
python3 -m aerotwin.evaluation.report --dev      # development split only (safe to look at while tuning)
python3 -m aerotwin.evaluation.report            # frozen test split → cache/results.json
python3 -m aerotwin.evaluation.gap_study         # reality-gap study → cache/gap_study.json (hidden if older than the models)
```

## API

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/fleet` | Fleet summary |
| GET | `/api/fleet/{id}` | Full timeline for one aircraft |
| GET | `/api/missions` | All test missions with ground truth |
| GET | `/api/missions/{split}/{id}` | Run the pipeline on any test mission |
| POST | `/api/simulate` | `{fault_type, severity, onset_s, profile, seed}` → new simulated flight + analysis |
| GET | `/api/results` | Validation report |
| GET | `/api/real-results` | Real-flight validation on NGAFID (404 until built) |
| GET | `/api/meta` | Engine limits, model configuration |
| POST | `/api/copilot` | `{question, aircraft_id?, t?, history?, force_offline?}` → grounded answer, mode, evidence used, fallback reason |
| GET | `/api/copilot/status` | Whether Claude is configured (never returns the key) |
| WS | `/api/stream/{id}?speed=5` | Window-by-window stream of a replayed flight (the dashboard itself replays client-side) |

## Data splits (dataset v2.1)

| Split | Flights | Seed block | Used for |
|---|---|---|---|
| `train_healthy` | 140 | 1 | Fit scaler and the three detectors |
| `val_healthy` | 28 | 2 | Fusion percentiles, Health-Index calibration |
| `val_fault` | 20 (5 faults × 4) | 4 | The only fault data used while developing rules, thresholds and filter settings |
| `test_healthy` | 60 (hot-weather profile) | 3 | False-alarm events (final) |
| `test_fault` | 60 (5 faults × 12, one severity each) | 5 | Detection, diagnosis, RUL (final, never tuned on) |

Every flight has its own seed, recorded in the fault logs with the dataset version.

## Limitations

* Fault results come from **simulated** flights with idealised, single, smoothly progressing faults. On real Cessna 172 flights the ensemble was at chance level (see *Real flights*); Rotax 912 performance has not been measured on any real engine.
* **The main test split uses an exact twin** (the healthy twin and the Bayesian twin share the simulator's equations, and all engines are identical), so its numbers are an upper bound. The reality-gap study above measures how quickly each method degrades when that assumption fails.
* The engine equations are heuristic (linear in power, first-order thermal lag); there is no manifold pressure, AFR, propeller load or airspeed-dependent cooling.
* The "lean cylinder" fault key is still `injector_abnormality` in code; the 912 S/ULS is carburetted, so it models an intake leak or fuel-metering fault.
* The test split has one severity per fault type, and faulty cylinders are always 1 or 2.
* Single faults only; sensor faults and compound faults are not modelled.
* Decision-support prototype, not a certified airworthiness system.
