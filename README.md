# AeroTwin: Aero-Piston Engine Digital Twin

**Physics-informed digital twin for predictive health monitoring of MALE-UAV aero-piston engines (Rotax 912 class).**

AeroTwin compares every engine sensor against a physics model of a *healthy* engine flying the same conditions.
An ensemble of three AI detectors watches the difference (the residual). The system turns that into a 0–100 Health
Index, warns before failure, names the fault and the cylinder, estimates remaining useful life, and gives a
Go / Caution / No-Go decision for the next mission.

> **Read this first.** All data is **simulated**. The healthy twin and the particle filter use the *same equations*
> as the simulator, and every simulated engine is physically identical. The numbers below are therefore an
> **upper bound** on what this design can do, not a measurement of a real engine. They come from a frozen test
> split (dataset v2.0) that was generated from disjoint seeds and evaluated once, after thresholds and diagnosis
> rules had been fixed on a separate development split.

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
| Faults detected before failure | 60/60 (95% CI 94–100%) | 59/60 (95% CI 91–100%) |
| Fault type + cylinder correct | 60/60 (95% CI 94–100%) | 60/60 type, 24/24 cylinder |
| False-alarm events in 80.3 healthy flight-hours | **0** (95% upper bound 0.046 /FH) | 1 (95% CI 0.0003–0.069 /FH) |
| Median detection delay after onset | 37 s | 107 s |
| 90% RUL interval contains the true failure time | **90.0%** (95% CI 87.7–92.0%) | no intervals |
| RUL median absolute error | 68 s | 262 s (HI linear trend)* |
| RUL within ±20% of truth (α-λ) | 33% | 1.2% (HI linear trend)* |
| Hidden-health tracking error (MAE) | 0.006 | n/a |

The delays are not a like-for-like race: the ML path waits for a 60 s window plus 8 × 10 s of persistence, while
the filter decides at 1 Hz using the simulator's own equations. *The HI linear trend extrapolates the anomaly
index to 50, not to the physical failure threshold that defines the truth, so part of its error is a definition
mismatch.

Code: `aerotwin/twin/particle_filter.py` · UI: *Twin Replay → Bayesian health twin* and *Model Validation → Flagship*.

## Explainable AI: which sensors caused the alert, and are the explanations right?

Every window the ensemble flags gets a **sensor-level counterfactual explanation** (`aerotwin/xai/attribution.py`):
each of the 15 residual channels is reset to its healthy baseline, all three detectors are re-scored, and the drop in
each model's *raw* score (not its saturating percentile) is that sensor's share of the anomaly evidence. The dashboard
shows it per model and for the ensemble, with a counterfactual sentence ("if oil pressure had been healthy, the fused
percentile would drop from 97 to 49"). SHAP was not used: TreeSHAP covers only the Isolation Forest, and only at the
level of 45 window statistics, not sensors.

Explanations are **validated against the simulator's ground truth**: at the first alert of each test fault flight, is
the top-ranked sensor one the fault physically acts on?

| Whose explanation | Top sensor physically correct |
|---|---|
| Ensemble | **60/60** (95% CI 94–100%) |
| LSTM-AE | 60/60 |
| PCA-SPE | 58/60 |
| Isolation Forest | 54/60 |

The single false alarm on healthy flights is explained by a CHT 1 blip (74% of the evidence).

## ML ensemble results (same test split)

| Metric | Result |
|---|---|
| Faults detected after onset, before failure | 59/60 (one bearing-wear fault was flagged after its failure threshold) |
| Fault type correct at first alert (signature rules) | 60/60 |
| Faulty cylinder (lean cylinder / misfire flights) | 24/24 — the fault is always on cylinder 1 or 2 in this dataset |
| Median warning before the simulated failure threshold | 3.6 min (lubrication 16 min, misfire 10 s) |
| False-alarm events, single detectors vs fused | Isolation Forest 10 · PCA 33 · LSTM-AE 78 · **fused 1** |
| HI-trend RUL estimates on the conservative side | 97% |

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
* Retrain the models: `./run.sh --retrain`
* Tests: `python3 -m pytest -q` (49 tests, one documented expected failure)

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
| `aerotwin/xai/` | Explainable AI: sensor-level counterfactual attribution |
| `aerotwin/diagnosis/` | Physics-signature fault isolation |
| `aerotwin/advisor/` | Go / Caution / No-Go mission advisor |
| `aerotwin/inference/` | Full-pipeline replay, on-demand scenario simulation |
| `aerotwin/evaluation/` | Training, metrics, validation report |
| `backend/main.py` | FastAPI: REST + WebSocket, serves the dashboard |
| `dashboard/` | React + Vite + Recharts UI |
| `tests/` | Pytest suite |

## Rebuilding from scratch

```bash
python3 -m aerotwin.simulator.generate_dataset   # 308 seeded one-hour flights → data/ (dataset v2.0)
python3 -m aerotwin.evaluation.train_models      # trains + calibrates → models/
python3 -m aerotwin.evaluation.report --dev      # development split only (safe to look at while tuning)
python3 -m aerotwin.evaluation.report            # frozen test split → cache/results.json
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
| GET | `/api/meta` | Engine limits, model configuration |
| WS | `/api/stream/{id}?speed=5` | Window-by-window stream of a replayed flight (the dashboard itself replays client-side) |

## Data splits (dataset v2.0)

| Split | Flights | Seed block | Used for |
|---|---|---|---|
| `train_healthy` | 140 | 1 | Fit scaler and the three detectors |
| `val_healthy` | 28 | 2 | Fusion percentiles, Health-Index calibration |
| `val_fault` | 20 (5 faults × 4) | 4 | The only fault data used while developing rules, thresholds and filter settings |
| `test_healthy` | 60 (hot-weather profile) | 3 | False-alarm events (final) |
| `test_fault` | 60 (5 faults × 12, one severity each) | 5 | Detection, diagnosis, RUL (final, evaluated once) |

Every flight has its own seed, recorded in the fault logs with the dataset version.

## Limitations

* Trained and validated on **simulated** flights with idealised, single, smoothly progressing faults. Real-engine accuracy will be lower and must be re-measured on recorded data (`aerotwin/real_engine/recording_protocol.md`).
* **The healthy twin and the Bayesian twin use the same equations as the simulator**, and all simulated engines are identical. With no model mismatch, healthy residuals are pure sensor noise, which makes detection much easier than on a real engine.
* The engine equations are heuristic (linear in power, first-order thermal lag); there is no manifold pressure, AFR, propeller load or airspeed-dependent cooling.
* The "lean cylinder" fault key is still `injector_abnormality` in code; the 912 S/ULS is carburetted, so it models an intake leak or fuel-metering fault.
* The test split has one severity per fault type, and faulty cylinders are always 1 or 2.
* Single faults only; sensor faults and compound faults are not modelled.
* Decision-support prototype, not a certified airworthiness system.
