# AeroTwin: Aero-Piston Engine Digital Twin

**Physics-informed digital twin for predictive health monitoring of MALE-UAV aero-piston engines (Rotax 912 class).**

AeroTwin compares every engine sensor against a physics model of a *healthy* engine flying the same conditions.
An ensemble of three AI detectors watches the difference (the residual). The system turns that into a 0–100 Health
Index, warns before failure, names the fault and the cylinder, estimates remaining useful life, and gives a
Go / Caution / No-Go decision for the next mission.

## ⭐ Flagship: Bayesian health twin (particle filter)

The ML ensemble answers *"is something abnormal?"*. The flagship answers *"which component is degrading, how
healthy is it right now, and when will it fail, with what certainty?"*

* **Bank of 11 hypothesis-specific particle filters** (lubrication, cooling, injector ×4 cylinders, misfire ×4,
  bearing; 120 particles each) with **Bayesian model selection** between hypotheses.
* Each particle carries hidden health `h`, degradation rate `r`, an unknown-onset flag (jump-Markov), and its own
  thermal state, pushed through the physics engine model every second.
* **RUL is a probability distribution**: each particle is extrapolated to the functional-failure health limit.
* The filter does **not** know the true degradation law, rate or onset. Parameters were tuned only on separately
  simulated flights (`aerotwin/twin/tune.py`), never on the test set.

| Held-out test set (120 flights) | Bayesian twin | ML ensemble / linear RUL |
|---|---|---|
| Median detection delay after onset | **40 s** | 109 s |
| RUL median absolute error | **68 s** | 243 s |
| RUL within ±20 % of truth (α-λ) | **33 %** | 1.4 % |
| Hidden-health tracking error (MAE) | **0.008** | n/a |
| 90 % credible-interval coverage | 87 % (tuning set: 91 %) | no intervals |
| False alarms per flight hour | **0.00** | 0.05 |
| Fault type + cylinder correct | 100 % | 100 % |

Code: `aerotwin/twin/particle_filter.py` · UI: *Live Twin → Bayesian health twin* panel and *Model Validation → Flagship*.

## Results of the ML ensemble (held-out test set, never seen in training)

| Metric | Result |
|---|---|
| Fault detection rate (5 fault types, 60 flights) | **100 %** |
| Fault diagnosis accuracy (correct fault type) | **100 %** |
| Faulty-cylinder localisation (injector / misfire) | **100 %** |
| Median warning before functional failure | **4.7 min** (lubrication: 13 min, misfire: 9 s) |
| False alarms (81 healthy flight hours, hotter climate than training) | **0.05 per flight hour** |
| False-alarm reduction of fused ensemble vs best single model | **≈ 10×** |
| RUL estimates on the conservative (safe) side | **96 %** |

All numbers are recomputed by `python3 -m aerotwin.evaluation.report` and shown live on the dashboard's
*Model Validation* page. They come from **simulated** data (see Limitations).

## Quick start

```bash
cd aero-digital-twin
./run.sh            # installs what's missing, builds the dashboard, opens http://localhost:8000
```

The first start evaluates the models on 120 held-out flights (~1 min) and caches the result. Later starts take about 6 s.

* Dashboard: http://localhost:8000
* Interactive API docs (Swagger): http://localhost:8000/docs
* Developer mode with hot reload: `./run.sh --dev` → http://localhost:5173
* Tests: `python3 -m pytest -q` (19 tests)

## Dashboard pages

| Page | What it shows |
|---|---|
| **Fleet Command** | 8 aircraft, Health Index, Go/No-Go, diagnosed fault, HI sparkline |
| **Live Twin** | Flight replay with an animated engine schematic (cylinders coloured by CHT, flagged cylinder blinks), 6 gauges with twin-expected markers, Health Index & detector charts, measured-vs-twin plots, residual bars, diagnosis, RUL, event log, printable maintenance report |
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
| `aerotwin/diagnosis/` | Physics-signature fault isolation |
| `aerotwin/advisor/` | Go / Caution / No-Go mission advisor |
| `aerotwin/inference/` | Full-pipeline replay, on-demand scenario simulation |
| `aerotwin/evaluation/` | Training, metrics, validation report |
| `backend/main.py` | FastAPI: REST + WebSocket, serves the dashboard |
| `dashboard/` | React + Vite + Recharts UI |
| `tests/` | Pytest suite |

## Rebuilding from scratch

```bash
python3 -m aerotwin.simulator.generate_dataset   # 288 one-hour flights → data/
python3 -m aerotwin.evaluation.train_models      # trains + calibrates → models/
python3 -m aerotwin.evaluation.report            # validation report → cache/results.json
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
| WS | `/api/stream/{id}?speed=5` | Live window-by-window telemetry stream |

## Limitations

* Trained and validated on **simulated** flights with idealised fault models. Real-engine accuracy will be lower and must be re-measured on recorded data (`aerotwin/real_engine/recording_protocol.md`).
* The Bayesian twin shares its physics model with the simulator (zero model mismatch in the observation model); on a real engine it must first be calibrated. Its 90 % intervals are slightly over-confident on the test set (87 % coverage).
* Single faults only; sensor faults and compound faults are not modelled.
* Decision-support prototype, not a certified airworthiness system.
# AeroTwin
