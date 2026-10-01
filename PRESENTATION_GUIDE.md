# Presentation Guide: how to demo AeroTwin (≈ 8 minutes)

## Before the presentation
1. `cd aero-digital-twin && ./run.sh` and wait for the browser to open at http://localhost:8000.
2. Do this **once beforehand** so the validation cache is built (first start ~1 min, later ~6 s).
3. Use full-screen browser (Cmd+Ctrl+F). Works offline once started.

## Demo script

**1. The problem (30 s): no screen needed**
> "MALE UAVs fly 20+ hour missions on small piston engines like the Rotax 912. An engine failure means losing the
> aircraft. Fixed-interval maintenance is wasteful and still misses developing faults. I built a digital twin that
> detects faults early, says what and where the fault is, and tells the operator whether the next mission is safe."

**2. Fleet Command (45 s)**
- Point at the KPI row: 8 aircraft, 3 GO, 5 NO-GO, 100% detection.
- "Each card is a real test flight the AI never saw during training. AT-105 is grounded: ignition misfire on cylinder 2."

**3. Live Twin (2 min): the highlight.** Click **AT-107** (injector fault).
- Playback starts at 4×. While it plays, explain:
  - *Engine twin*: "Cylinders are coloured by live head temperature; the propeller and vibration are animated."
  - *Gauges*: "The white tick is what a **healthy** engine would read right now. That is the digital twin."
  - *Measured vs twin chart*: "This gap is the residual, the only thing the AI looks at."
- At ~T+14:00 the fault appears: **cylinder 1 blinks red**, diagnosis reads *Fuel injector abnormality · Cyl 1*,
  advisor turns **NO-GO**, and the event log fills.
- Tick **Ground truth**: "The orange line is when the fault was really injected. We caught it ~90 s later, minutes before failure."
- Click **Report**: a printable maintenance report for the technician.

**3b. ⭐ The flagship: Bayesian health twin (1.5 min). This is "I designed and implemented this"**
- Stay on AT-104 (lubrication) and scroll to the purple *Bayesian health twin* panel. Tick **Ground truth**.
- "No sensor measures oil-system health directly. My particle filter *infers* it: 11 competing fault hypotheses,
  1,320 particles, each running the physics model every second. Bayes' rule decides which hypothesis explains the data."
- Point at: hypothesis bars jumping to *Lubrication 100%*; the hidden-health line sitting on the dashed **true**
  health; the RUL fan narrowing onto the true time to failure.
- "It detected the fault at T+23:19, 90 seconds before the ML ensemble flagged anything (T+24:49)."

**4. Fault Injection Lab (2 min): proves it's not pre-recorded**
- Ask your teacher to **choose any fault**, severity and onset time. Pick *High altitude* profile ("never seen in training").
- Click **Run simulation**. A brand-new 1-hour flight is generated and analysed in ~1 s.
- The green verdict box shows: detected X s after onset, correct diagnosis, Y min before failure.
- Also run **Healthy engine** → "no false alarm".

**5. Model Validation (1.5 min)**
- KPIs: 100% detection, 100% diagnosis, 0.05 false alarms per flight hour.
- **Ablation table** (the strongest point): "Each AI model alone raises a false alarm every 0.5–2 flight hours.
  Fusing three different model families cuts that by 10× without losing a single detection."
- Confusion matrix: perfect diagonal. RUL chart: "96% of predictions are conservative, the safe direction for aviation."

- **Flagship section** (top purple panel): "Same 120 test flights. The Bayesian twin detects faults 2.7× faster,
  RUL error 68 s vs 243 s, zero false alarms. And the uncertainty is validated: this calibration plot checks that a
  90% interval really contains the truth ~90% of the time. We get 87%, slightly over-confident, which I report honestly."

**6. How it works + honest limitations (1 min)**
- Walk the 7-step pipeline.
- End on the limitations card: "Everything is validated on simulated data. The next step is recording a real engine
  and calibrating the twin, which is why I wrote the recording protocol."

## Likely questions and answers

**What exactly is your flagship / what did YOU design?**
A Bayesian health twin: a bank of hypothesis-specific particle filters (one per fault mode and cylinder) with Bayesian
model selection, a jump-Markov onset model, and physics-model-in-the-loop prediction. It turns sensor data into
*hidden component health with uncertainty* and *RUL as a probability distribution*.

**Why a particle filter and not a Kalman filter?**
The problem is non-linear (thermal lag, multiplicative health effects), the onset is a discrete jump, and the
hypotheses are discrete (which fault, which cylinder). Particle filters handle non-linear, non-Gaussian and mixed
discrete/continuous states. Kalman filters assume linear-Gaussian.

**Didn't the particle filter just copy the simulator?**
Partly, and I say so: it uses the same sensor physics. But it does not know the degradation law (exponential vs linear),
the rate or the onset time, and it was tuned only on separate simulated flights. On a real engine the physics model must be
calibrated first; that is the sim-to-real next step.

**How do you know the uncertainty is right?**
Coverage testing: over 3,012 predictions, the 90% interval contained the true failure time 87% of the time (91% on the
tuning set). That's slightly over-confident, and I report it rather than hide it.

**What is α-λ accuracy?**
A standard prognostics metric (Saxena et al.): the fraction of RUL predictions within ±α (here 20%) of the true RUL.
Twin 33% vs linear trend 1.4%.

**Why not just put thresholds on the sensors?**
Thresholds only fire at the redline, when it's already too late, and a healthy engine in a climb looks "hot". Residuals against the twin remove
flight-condition effects, so a fault is visible while values are still inside the normal range (see AT-107: EGT rises
long before 880 °C).

**Why train only on healthy data?**
Real fleets have almost no recorded failures. Unsupervised detectors learn "normal" and flag anything else, so they
need no fault labels and can catch fault types never seen before.

**Why three models?**
They fail differently: Isolation Forest is tree-based, PCA is linear, and the LSTM autoencoder is temporal. Their noise is
uncorrelated, so averaging calibrated percentiles cancels it out (ablation: 0.51–1.99 → 0.05 false alarms/FH).

**How is the Health Index computed?**
Each model's score → percentile of healthy validation flights → averaged → HI = 100·(1 − (score/100)^p), where p is
calibrated so a typical healthy window gives HI 95.

**How do you avoid false alarms?**
An alert needs HI < 50 for 8 consecutive windows (80 s). Measured 0.05/FH over 81 healthy flight hours.

**How does diagnosis work? Is it ML?**
It is physics rules, which makes it explainable. Each fault leaves a fingerprint: oil-pressure drop = lubrication, all CHTs up =
cooling, one cylinder's EGT up = injector, one EGT down + vibration up = misfire, vibration only = bearing. The rules
were written from physics, not fitted to the test set, so the 100% is a fair held-out result.

**Is there data leakage?**
No. Test aircraft UAV-08…10 never appear in training, healthy test flights are in hot weather (training was standard
ISA), and ground-truth failure time is computed analytically from the fault model.

**Why is misfire warning only 9 s?**
Misfire progresses to functional failure in ~100 s in the model. Detection takes ~90 s because the system waits for
enough evidence to avoid false alarms. This is a real trade-off and is shown honestly.

**Would it work on a real engine?**
Not without calibration. The architecture is ready (the physics twin's parameters would be fitted to real recordings), but
accuracy must be re-measured. That is the stated next step.

**Tech stack?**
Python, NumPy/Pandas, scikit-learn, PyTorch (LSTM-AE), FastAPI (REST + WebSocket), React + Vite + Recharts. There are 19
automated tests (`python3 -m pytest`).
