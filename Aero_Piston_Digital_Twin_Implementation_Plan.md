# Aero-Piston Engine Digital Twin — Full Implementation Plan

## 1. Project Goal

Build a **physics-informed Digital Twin prototype for predictive health monitoring of MALE UAV aero-piston engines**.

The implementation is based on verified patterns from the reference repositories supplied for this project:

- `spd151730-cell/New_dashboard` — physics model, simulator, mission profiles, residuals, rule-based anomaly detection, hysteresis, FastAPI/WebSocket architecture.
- `ganeshog01-arch/AeroTWIN-AI` — mission/environment simulation, thermal behavior, operator-oriented dashboard concepts, prototype disclaimer.
- `Mehak2513kaur/sih26054-digital-twin` — React + Vite + Tailwind + Recharts frontend, FastAPI backend, WebSocket streaming, gradual fault progression, SQLite/reporting workflow.
- `vinayraut71-source/sih26054-digital-twin` — containerized full-stack execution and team/deployment workflow.
- `Monika-Srinithi/TwinProp-DX` — FastAPI route organization, mission replay, relational persistence, Docker Compose separation.
- `Santisoutoo/Anomaly_detection` — PCA, Isolation Forest, LSTM Autoencoder and anomaly-detection evaluation methodology.
- `mouradboutrid/TurboGuard` — LSTM Autoencoder reconstruction and forecasting architecture for time-series anomaly detection.
- `naikio/LSTM_encoder_decoder_for_prognostics` — healthy-only LSTM Autoencoder → reconstruction error → Health Index → RUL methodology.

The project should **not** blindly copy these repositories. Their ideas are used as implementation references while avoiding weaknesses such as unclear fault ground truth, arbitrary RUL values, data leakage, and unsupported real-world accuracy claims.

---

# 2. Final System Architecture

```text
                    FRONTEND
                       │
              React + Vite + TS
                       │
             WebSocket + REST
                       │
                       ▼
                 FASTAPI
                       │
          ┌────────────┼────────────┐
          │            │            │
          ▼            ▼            ▼
     Simulator     Twin Core     Database
          │            │
          ▼            ▼
     Mission       Physics Model
     Profiles           │
                        ▼
                   Residuals
                        │
            ┌───────────┼───────────┐
            ▼           ▼           ▼
         Rules          IF        LSTM-AE
            │           │           │
            └───────────┼───────────┘
                        ▼
                  Fusion Engine
                        │
              ┌─────────┴─────────┐
              ▼                   ▼
        Fault Diagnosis       Health Index
                                    │
                                    ▼
                                   RUL
                                    │
                                    ▼
                              Mission Report
```

---

# 3. Technology Stack

## Backend

- Python
- FastAPI
- WebSocket
- NumPy
- Pandas
- Scikit-learn
- PyTorch
- Joblib
- SQLite

## Frontend

- React
- Vite
- TypeScript
- Tailwind CSS
- Recharts
- Lucide React

## Deployment

- Docker
- Docker Compose

## Why this stack?

The reference projects demonstrate React/FastAPI/WebSocket architecture and Docker-based separation. For the immediate prototype, SQLite is preferred over introducing PostgreSQL, TimescaleDB, MQTT and Redis simultaneously.

---

# 4. Final Project Directory

```text
aero-piston-digital-twin/
│
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── physics_model.py
│   │   ├── simulator.py
│   │   ├── mission_profiles.py
│   │   ├── fault_injection.py
│   │   ├── anomaly.py
│   │   ├── twin_core.py
│   │   ├── prognostics.py
│   │   ├── replay.py
│   │   ├── schemas.py
│   │   ├── database.py
│   │   ├── websocket_manager.py
│   │   └── config.py
│   │
│   ├── models/
│   │   ├── isolation_forest.pkl
│   │   ├── scaler.pkl
│   │   ├── lstm_autoencoder.pt
│   │   └── lstm_scaler.pkl
│   │
│   ├── data/
│   │   ├── normal_telemetry.csv
│   │   ├── fault_telemetry.csv
│   │   └── missions/
│   │
│   ├── train/
│   │   ├── train_isolation_forest.py
│   │   └── train_lstm_ae.py
│   │
│   ├── tests/
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── charts/
│   │   ├── api/
│   │   ├── hooks/
│   │   ├── types/
│   │   └── App.tsx
│   ├── package.json
│   └── vite.config.ts
│
├── reports/
├── docker-compose.yml
├── README.md
└── .gitignore
```

---

# 5. Phase 1 — Physics Simulator

## 5.1 `physics_model.py`

Use the module separation demonstrated by `New_dashboard`.

The physics model predicts the expected healthy state from:

- RPM
- Throttle
- Altitude
- Ambient temperature

Expected outputs:

```text
expected_egt
expected_cht
expected_oil_temp
expected_oil_pressure
expected_map
expected_fuel_flow
expected_iat
expected_vibration
air_density
barometric_pressure
```

Core concept:

```text
Operating Conditions
        ↓
Physics Model
        ↓
Expected Healthy State
```

The reference repository includes relationships for EGT, CHT, oil temperature, MAP, oil pressure, fuel flow, IAT and vibration.

Do not invent arbitrary equations without documenting assumptions. Reuse the verified structure and clearly label the result as a simplified prototype model.

---

# 6. Phase 2 — Mission Profiles

Implement `mission_profiles.py`.

Initial mission profiles:

## Mission 1 — Normal Cruise

```text
Takeoff
   ↓
Climb
   ↓
Cruise
   ↓
Descent
   ↓
Landing
```

## Mission 2 — High Altitude Hot Weather

```text
Takeoff
↓
Climb
↓
High altitude
↓
Hot ambient conditions
↓
High thermal load
↓
Cruise
```

## Mission 3 — Endurance

```text
Takeoff
↓
Climb
↓
Long cruise
↓
Moderate throttle
↓
Descent
↓
Landing
```

Frontend controls:

```text
Mission Profile
Altitude
Throttle
Ambient Temperature
Mission Duration
```

---

# 7. Phase 3 — Engine Simulator

Implement `simulator.py`.

Generate continuous telemetry based on the reference simulator architecture.

Telemetry channels:

```text
timestamp
rpm
throttle
altitude
ambient_temp
egt
cht
oil_temp
oil_pressure
map
fuel_flow
iat
vibration
```

Example:

```json
{
  "timestamp": "...",
  "rpm": 3200,
  "throttle": 0.62,
  "altitude": 8500,
  "ambient_temp": 31,
  "egt": 742,
  "cht": 168,
  "oil_temp": 96,
  "oil_pressure": 4.2,
  "map": 27.1,
  "fuel_flow": 18.4,
  "iat": 31.8,
  "vibration": 1.1
}
```

The simulator should include realistic small sensor noise.

---

# 8. Phase 4 — Gradual Fault Injection

Implement `fault_injection.py`.

This is a key improvement over simple instant fault triggering.

Fault lifecycle:

```text
HEALTHY
   ↓
fault_start_t
   ↓
LOW
   ↓
MEDIUM
   ↓
HIGH
   ↓
failure_t
```

Initial faults:

| Fault | Main effect |
|---|---|
| Overheating | CHT ↑, EGT ↑, Oil Temp ↑ |
| Lubrication Failure | Oil Pressure ↓, Oil Temp ↑ |
| Fuel Restriction | Fuel Flow ↓, EGT ↑ |
| Excessive Vibration | Vibration ↑ |
| Cylinder Misfire | RPM fluctuation + vibration ↑ |

Later additions:

```text
Sensor Drift
Bearing Degradation
Exhaust Leak
```

---

# 9. Ground Truth Logging

Every fault simulation must save ground truth.

Example:

```json
{
  "fault": "OVERHEATING",
  "fault_start_t": 420,
  "failure_t": 720
}
```

Telemetry should also contain a fault label during synthetic dataset generation.

This allows calculation of:

- Detection time
- Detection delay
- Lead time
- False alarms
- Detection rate
- False alarm rate

This is one of the project's important differentiators.

---

# 10. Phase 5 — Physics Residual

The Digital Twin compares observed telemetry against expected physics state.

Formula:

```text
Residual = Observed - Expected
```

Example:

```text
Observed EGT  = 820 °C
Expected EGT  = 735 °C

Residual = +85 °C
```

Pipeline:

```text
Telemetry
   ↓
Physics Model
   ↓
Expected State
   ↓
Observed - Expected
   ↓
Residual Vector
```

Dashboard example:

```text
EGT

Observed     820 °C
Expected     735 °C
Residual     +85 °C
```

---

# 11. Phase 6 — Rule-Based Baseline

Implement `anomaly.py`.

Use:

```text
Residual
   ↓
Threshold
   ↓
Anomaly Candidate
   ↓
Persistence / Hysteresis
   ↓
Confirmed Anomaly
```

Do not trigger an alarm from one abnormal sample.

Example:

```text
3 consecutive abnormal samples
        ↓
Confirmed anomaly
```

The reference `New_dashboard` uses thresholding and hysteresis to reduce transient false alarms.

---

# 12. Phase 7 — Isolation Forest

Isolation Forest is used for:

> "Something abnormal is happening."

It is not the final fault classifier.

Feature vector:

```text
[
 rpm,
 throttle,
 egt,
 cht,
 oil_temp,
 oil_pressure,
 map,
 fuel_flow,
 iat,
 vibration,
 egt_residual,
 cht_residual,
 oil_temp_residual,
 oil_pressure_residual,
 vibration_residual
]
```

Pipeline:

```text
Telemetry + Residuals
        ↓
Feature Vector
        ↓
Isolation Forest
        ↓
Anomaly Score
```

Train only on healthy baseline data.

---

# 13. Phase 8 — PCA

Use PCA primarily as a diagnostic and visualization method.

Pipeline:

```text
Healthy Telemetry
       ↓
StandardScaler
       ↓
PCA
       ↓
2D Projection
```

Dashboard:

```text
PCA Health Map

Normal points     ● ● ● ●
                  ● ● ●

Current state                 X
                              ↑
                         abnormal
```

The `Santisoutoo/Anomaly_detection` repository uses PCA together with Isolation Forest, One-Class SVM and deep-learning methods.

---

# 14. Phase 9 — LSTM Autoencoder

Use a healthy-only LSTM Autoencoder for temporal anomaly detection.

Architecture:

```text
Healthy telemetry
       ↓
Scaling
       ↓
Sequences
       ↓
LSTM Encoder
       ↓
Latent Representation
       ↓
LSTM Decoder
       ↓
Reconstructed telemetry
```

Then calculate:

```text
Reconstruction Error
```

Healthy example:

```text
Actual:
EGT 720, CHT 150, OilTemp 90, Vib 0.9

Reconstructed:
EGT 719, CHT 151, OilTemp 90, Vib 0.91

→ Small error
```

Fault example:

```text
Actual:
EGT 820, CHT 180, OilTemp 115, Vib 2.8

Reconstructed:
EGT 730, CHT 152, OilTemp 94, Vib 1.0

→ Large error
```

The TurboGuard and `naikio/LSTM_encoder_decoder_for_prognostics` repositories provide the relevant methodology.

---

# 15. Adaptive LSTM-AE Threshold

Do not hardcode:

```text
threshold = 0.5
```

Instead:

```text
Healthy training/validation errors
          ↓
Distribution
          ↓
Percentile / statistical threshold
          ↓
Anomaly threshold
```

Store the threshold with the trained model.

Example metadata:

```json
{
  "threshold": "...",
  "method": "healthy_validation_percentile"
}
```

---

# 16. Phase 10 — Anomaly Fusion

Combine three signals:

```text
Rule Engine
     +
Isolation Forest
     +
LSTM Autoencoder
```

Architecture:

```text
             Rule Engine
                  │
             Isolation Forest
                  │
             LSTM-AE
                  │
                  ↓
             Fusion Engine
                  ↓
             Final Anomaly
```

Dashboard:

```text
PHYSICS RESIDUAL       HIGH
ISOLATION FOREST       HIGH
LSTM RECONSTRUCTION    HIGH
--------------------------------
FINAL STATUS           WARNING
```

---

# 17. Phase 11 — Fault Diagnosis

Fault classification is separate from anomaly detection.

Pipeline:

```text
Anomaly detected
       ↓
Fault Diagnosis
       ↓
Fault Type
       ↓
Confidence
       ↓
Contributing Parameters
```

Example:

```json
{
  "fault": "OVERHEATING",
  "confidence": 0.91,
  "severity": "HIGH",
  "contributors": [
    "CHT residual",
    "EGT residual",
    "Oil temperature trend"
  ]
}
```

Important:

Synthetic-data classifier accuracy must be reported as:

> "Validation accuracy on our synthetic hold-out dataset."

Do not claim it represents real-world engine diagnostic accuracy.

---

# 18. Phase 12 — Health Index

The `naikio/LSTM_encoder_decoder_for_prognostics` project uses reconstruction errors to construct a Health Index and then uses the health trend for RUL estimation.

Concept:

```text
LSTM Reconstruction Error
          ↓
Health Index
          ↓
Health Trend
```

Dashboard scale:

```text
100 → Healthy
  0 → Critical
```

Example curve:

```text
100 ────────────────
 90              ╲
 80               ╲
 70                ╲
 60                 ╲
 50                  ╲
 40                   ╲
 30                    ╲
 20                     ╲
 10                      ╲
  0                       X
       Mission Time →
```

---

# 19. Phase 13 — RUL

RUL must not be a hardcoded number.

Use:

```text
Current Health Index
+
Health degradation slope
+
Historical degradation trend
        ↓
Prototype RUL
```

Dashboard:

```text
Estimated RUL

143 h

Trend: Degrading

Prototype estimate
```

If uncertainty has not been calibrated, do not show a fake confidence interval.

Use:

```text
Confidence interval: Not calibrated
```

rather than inventing:

```text
± 18.4 h
```

---

# 20. Phase 14 — Backend API

## System

```http
GET /api/health
GET /api/status
```

## Telemetry

```http
GET /api/telemetry/latest
GET /api/telemetry/history
```

## Digital Twin

```http
GET /api/twin/state
GET /api/twin/residuals
```

## Mission

```http
GET  /api/missions
POST /api/missions/start
POST /api/missions/pause
POST /api/missions/resume
POST /api/missions/stop
POST /api/missions/reset
```

## Fault

```http
POST /api/fault/inject
POST /api/fault/clear
```

## AI

```http
GET /api/anomaly
GET /api/diagnostics
GET /api/health-index
GET /api/rul
```

## Replay

```http
GET /api/missions/{id}/replay
```

## Reports

```http
GET /api/missions/{id}/report
GET /api/missions/{id}/report/pdf
```

## WebSocket

```text
WS /ws/engine
```

---

# 21. WebSocket Data

Every simulation tick should broadcast:

```json
{
  "timestamp": 172345,
  "telemetry": {},
  "expected": {},
  "residuals": {},
  "anomaly": {},
  "health": {},
  "fault": {},
  "rul": {}
}
```

Frontend receives this and updates:

```text
Charts
Cards
Alerts
Health Index
Fault Status
RUL
Engine Visualization
```

This avoids excessive polling.

---

# 22. Phase 15 — Frontend Pages

Build exactly six main pages.

## Page 1 — Mission Control

```text
AERO-TWIN
Digital Twin for MALE UAV Aero-Piston Engine

Mission Profile
[ High Altitude Endurance ]

Altitude
[ slider ]

Ambient Temperature
[ slider ]

Throttle
[ slider ]

Mission Duration
[ slider ]

[ START MISSION ]
[ PAUSE ]
[ STOP ]
```

---

# 23. Page 2 — Live Health Dashboard

Hero:

```text
ENGINE HEALTH

82.4

CAUTION
```

Telemetry cards:

```text
RPM
EGT
CHT
Oil Temp
Oil Pressure
Vibration
Fuel Flow
MAP
```

Charts:

```text
EGT Trend
CHT Trend
Oil Temperature
Vibration
```

---

# 24. Page 3 — Digital Twin

Display observed vs expected:

```text
Parameter     Observed     Expected     Residual

EGT           812°C        748°C        +64°C
CHT           178°C        154°C        +24°C
Oil Temp      108°C        94°C         +14°C
Oil Pressure  3.1 bar      4.2 bar      -1.1 bar
```

Also display:

```text
Physics Consistency
████████████░░ 82%
```

---

# 25. Page 4 — AI Diagnostics

Example:

```text
AI DIAGNOSTICS

Anomaly Status
⚠ ANOMALY DETECTED

Isolation Forest
0.87

LSTM Reconstruction
0.91

Physics Residual
0.84
```

Fault:

```text
Probable Fault

OVERHEATING

Confidence: 0.89
```

Contributors:

```text
CHT residual       ██████████
EGT residual       █████████
Oil temperature    ███████
Throttle           █████
```

---

# 26. Page 5 — Prognostics

```text
HEALTH INDEX

74.2
```

Show:

- Health Index curve
- Degradation trend
- RUL
- Fault timeline
- Current severity

Example:

```text
Estimated RUL

143 hours

Trend: degrading
```

---

# 27. Page 6 — Mission Replay

Mission card:

```text
Mission #004

Duration: 47 min
Status: Completed

[▶ Replay]
```

Timeline:

```text
00:00          23:42        47:00
              ●
```

During replay, synchronize:

```text
RPM
EGT
CHT
Oil Temperature
Health
Anomaly
Fault
```

---

# 28. Engine Visualization

Do not build a complicated Three.js engine before the core system works.

For the first showcase, use an SVG/CSS engine diagram.

Represent:

```text
Cylinder
Cylinder
Cylinder
Cylinder
   ↓
Crankshaft
   ↓
Propeller
```

Dynamic effects:

```text
RPM → propeller rotation
EGT → exhaust thermal indicator
CHT → cylinder heat
Oil Temp → oil indicator
Vibration → engine shake
Health → status
```

Three.js can be added later.

---

# 29. Database

Use SQLite for the first complete prototype.

## `missions`

```text
id
mission_name
start_time
end_time
mission_type
status
```

## `telemetry`

```text
id
mission_id
timestamp
rpm
throttle
altitude
ambient_temp
egt
cht
oil_temp
oil_pressure
map
fuel_flow
vibration
```

## `fault_events`

```text
id
mission_id
fault_type
fault_start_t
failure_t
severity
```

## `diagnostics`

```text
id
mission_id
timestamp
anomaly_score
health_index
fault_type
rul
```

TwinProp-DX's separation of engines, telemetry, missions and fault logs is the reference pattern.

---

# 30. Mission Report / PDF

Generate a technical mission debrief.

Example:

```text
AERO-TWIN MISSION REPORT

Mission:
High Altitude Endurance

Duration:
47 min

Maximum EGT:
812°C

Maximum CHT:
178°C

Minimum Oil Pressure:
3.1 bar

Final Health Index:
74.2

Detected Fault:
OVERHEATING

Fault Start:
00:31:24

Detection:
00:33:12

Detection Lead Time:
...
```

Include trend graphs and anomaly timeline.

---

# 31. Evaluation Metrics

Do not rely only on accuracy.

Calculate:

```text
Detection Rate
False Positive Rate
False Alarms / Flight Hour
Detection Delay
Lead Time
Precision
Recall
F1
```

These metrics should be calculated using the explicit ground-truth fault timeline.

---

# 32. Lead Time

If:

```text
fault_start_t = 1200 sec
detection_t   = 1050 sec
```

then:

```text
Lead Time = 1200 - 1050
          = 150 sec
```

Dashboard:

```text
EARLY WARNING

Fault starts in:
150 sec

✓ Early detection
```

---

# 33. False Alarms per Flight Hour

Formula:

```text
False Alarm Rate =
Number of False Alarms
----------------------
Total Flight Hours
```

Example:

```text
3 false alarms
2 flight hours

= 1.5 false alarms/hour
```

---

# 34. Threshold Trade-off

For LSTM-AE:

```text
Lower threshold
    ↓
More detections
    ↓
More false alarms
```

versus:

```text
Higher threshold
    ↓
Fewer false alarms
    ↓
Later detection
```

Create a trade-off plot:

```text
False Alarm Rate
       ↑
       │       ●
       │     ●
       │   ●
       │ ●
       └────────────────→
             Lead Time
```

This demonstrates the practical trade-off between sensitivity and false alarms.

---

# 35. Things NOT to Copy Blindly

## 35.1 Do not blindly copy synthetic accuracy claims

Some reference projects report very high accuracy on synthetic data.

This does not establish real-world engine diagnostic performance.

Always state:

```text
Validation accuracy on synthetic hold-out data
```

when appropriate.

---

## 35.2 Do not hardcode RUL

Avoid:

```text
Healthy → 480 h
Warning → 140 h
Critical → 30 h
```

unless these are actually produced by the implemented prognostic model.

---

## 35.3 Do not train and test on identical fault patterns

Bad:

```text
Generate fault
↓
Train
↓
Generate same pattern
↓
Test
```

Better:

```text
Generator
↓
Different random seeds / operating conditions
↓
Train
↓
Validation
↓
Independent test conditions
```

---

## 35.4 Do not mix turbofan physics with piston-engine physics

TurboGuard/CMAPSS is useful for:

```text
ML methodology
Time-series anomaly detection
LSTM-AE
Forecasting
Evaluation
```

but CMAPSS is a turbofan dataset.

Do not present it as piston-engine physical data.

---

## 35.5 Do not introduce too many infrastructure components immediately

Do not start with:

```text
MQTT
Redis
TimescaleDB
PostgreSQL
Kafka
CAN
```

all at once.

For the immediate prototype:

```text
React
   ↕
FastAPI
   ↕
SQLite
   ↕
Simulator
```

is sufficient.

---

# 36. Final Implementation Order

Follow this order exactly.

## Step 1

```text
Create project
↓
FastAPI
↓
React
↓
Test frontend/backend connection
```

## Step 2

```text
physics_model.py
↓
Unit tests
```

## Step 3

```text
simulator.py
↓
Generate telemetry
↓
Save CSV
```

## Step 4

```text
mission_profiles.py
↓
Takeoff
↓
Climb
↓
Cruise
↓
Descent
```

## Step 5

```text
fault_injection.py
↓
Gradual fault
↓
fault_start_t
↓
failure_t
```

## Step 6

```text
twin_core.py
↓
Expected state
↓
Residual
```

## Step 7

```text
Rule anomaly
↓
Hysteresis
```

## Step 8

```text
Isolation Forest
```

## Step 9

```text
LSTM Autoencoder
```

## Step 10

```text
Fusion Engine
```

## Step 11

```text
Health Index
```

## Step 12

```text
RUL
```

## Step 13

```text
WebSocket
```

## Step 14

```text
React Dashboard
```

## Step 15

```text
Mission Replay
```

## Step 16

```text
PDF Report
```

## Step 17

```text
Docker Compose
```

Do not change the order until each previous stage works.

---

# 37. Tomorrow Showcase Flow

Use a 5-minute demonstration.

## 00:00 — Healthy engine

```text
Health = 96
Status = NOMINAL
Anomaly = NONE
```

## 00:45 — Start mission

```text
High Altitude Endurance
```

Altitude begins increasing.

## 01:30 — Inject gradual overheating

```text
Fault:
OVERHEATING

Severity:
Gradual
```

Show:

```text
CHT ↑
EGT ↑
Oil Temp ↑
```

## 02:00 — Show Digital Twin residual

```text
Expected EGT: 748°C
Observed EGT: 801°C
Residual: +53°C
```

## 02:30 — Show AI detection

```text
Isolation Forest → anomaly
LSTM-AE → anomaly
Rule Engine → warning
```

## 03:00 — Show fault diagnosis

```text
FAULT:
OVERHEATING

Confidence:
0.89
```

## 03:30 — Show health degradation

```text
96
 ↓
88
 ↓
79
 ↓
68
```

## 04:00 — Show RUL

```text
Health Index
↓
Degradation slope
↓
Prototype RUL
```

## 04:30 — Mission Replay

Replay the exact fault progression.

## 05:00 — Mission Report

Generate and show the PDF.

---

# 38. Immediate Prototype vs Later Enhancements

| Feature | Immediate Prototype | Later |
|---|---:|---:|
| Physics simulator | YES | |
| Mission profiles | YES | |
| Gradual fault injection | YES | |
| Ground truth | YES | |
| Residual analysis | YES | |
| Rule anomaly | YES | |
| Isolation Forest | YES | |
| LSTM-AE | YES | |
| Health Index | YES | |
| Prototype RUL | YES | |
| React dashboard | YES | |
| FastAPI | YES | |
| WebSocket | YES | |
| Mission replay | YES | |
| PDF report | YES | |
| SQLite | YES | |
| Three.js engine | Later | YES |
| PostgreSQL | Later | YES |
| TimescaleDB | Later | YES |
| MQTT | Later | YES |
| Redis | Later | YES |
| CAN simulation | Later | YES |
| TCN-VAE | Later | YES |
| Forecasting LSTM | Later | YES |
| Real engine data | Later | YES |
| Hardware integration | Later | YES |

---

# 39. Final Design Principle

The repositories should not simply be merged into one giant application.

Use them as references for specific modules:

```text
New_dashboard
    → Physics + Simulator + Mission Profiles + Residuals + Hysteresis

AeroTWIN-AI
    → Thermal/Mission Simulation + Operator Presentation + Disclaimer

Mehak SIH
    → React + FastAPI + WebSocket + Gradual Faults + Reporting

TwinProp-DX
    → API Organization + Persistence + Replay + Docker

Santisoutoo
    → PCA + Isolation Forest + LSTM-AE + Evaluation

TurboGuard
    → LSTM-AE Time-Series Anomaly Methodology

naikio
    → Reconstruction Error → Health Index → RUL
```

The final project should therefore be:

```text
Physics-informed
        +
Synthetic telemetry
        +
Gradual fault injection
        +
Ground-truth logging
        +
Physics residuals
        +
Rule-based baseline
        +
Isolation Forest
        +
LSTM Autoencoder
        +
Health Index
        +
Prototype RUL
        +
Lead-time evaluation
        +
False-alarm evaluation
        +
React dashboard
        +
FastAPI backend
        +
WebSocket streaming
        +
Mission replay
        +
PDF mission report
```

This gives a complete **research/demo prototype** while keeping the architecture understandable and implementable.

---

# 40. Prototype Disclaimer

Use a disclaimer similar in intent to the reference projects:

> **Research Prototype — Simulated Engine Data**
>
> This Digital Twin is a software research and presentation prototype using simulated aero-piston engine telemetry. The displayed physics states, anomaly scores, fault classifications, Health Index and RUL are prototype estimates based on simplified models and synthetic data. The system is not connected to a real UAV or aircraft engine and must not be used for flight-critical control, certified maintenance decisions, or operational safety decisions.

