# Presentation Guide: how to demo AeroTwin (≈ 8 minutes)

## Before the presentation
1. `cd aero-digital-twin && ./run.sh` and wait for the browser to open at http://localhost:8000.
2. Do this **once beforehand**. On a fresh clone it generates the seeded dataset (~1 min) and builds the validation
   cache (~3 min); later starts take about 15 s.
3. Use full-screen browser (Cmd+Ctrl+F). Works offline once started.

## Demo script

**1. The problem (30 s): no screen needed**
> "MALE UAVs fly 20+ hour missions on small piston engines like the Rotax 912. An engine failure means losing the
> aircraft. I built a physics-informed digital twin, tested in simulation, that detects developing faults, says what
> and where the fault is, estimates remaining life with uncertainty, and advises whether the next mission is safe."

**2. Fleet Command (45 s)**
- KPI row: 8 aircraft, 3 GO, 5 NO-GO, faults detected 59/60 on the simulated test flights.
- "Each card is a simulated test flight that was never used in training. AT-105 is grounded: ignition misfire on cylinder 2."

**3. Twin Replay (2 min).** Click **AT-107** (lean cylinder), then drag the time slider to about **T+27:30** and press play.
- While it plays, explain:
  - *Engine twin*: "Cylinders are coloured by live head temperature; the propeller and vibration are animated."
  - *Gauges*: "The white tick is what a **healthy** engine would read right now. That is the digital twin."
  - *Measured vs twin chart*: "This gap is the residual, the only thing the AI looks at."
- The fault is injected at T+28:16. The Bayesian twin flags *Lean · C1* at **T+28:39**, cylinder 1 blinks red, and the
  advisor turns NO-GO. The ML ensemble alarms later, at T+29:49.
- Tick **Ground truth** to show the real onset and failure time. Click **Report** for the printable maintenance report.

- Scroll to **Explainable AI**: "The ML isn't a black box. I reset each sensor to healthy and re-score the models;
  the drop is that sensor's share of the evidence. Here it is EGT 1 and the EGT spread, which is exactly the lean
  cylinder." (On AT-108, bearing wear, vibration carries about 90% and the Isolation Forest visibly gets distracted
  while PCA and the LSTM point at vibration, a good example of why the ensemble matters.)

**3b. ⭐ The flagship: Bayesian health twin (1.5 min). This is "I designed and implemented this"**
- Switch to **AT-104** (lubrication), scrub to about T+31:30, play, and scroll to the purple *Bayesian health twin* panel. Tick **Ground truth**.
- "No sensor measures oil-system health directly. My particle filter *infers* it: 11 competing fault hypotheses,
  1,320 particles, each running the physics model every second. Bayes' rule decides which hypothesis explains the data."
- Point at: hypothesis bars jumping to *Lubrication*; the hidden-health line sitting on the dashed **true** health;
  the RUL fan narrowing onto the true time to failure.
- "The fault starts at T+32:18. The twin is confident at T+33:19; the ML ensemble only alarms at T+37:29."

**4. Fault Injection Lab (2 min): proves it's not pre-recorded**
- Ask your teacher to **choose any fault**, severity and onset time. Try the *High altitude* profile ("not in the training data").
- Click **Run simulation**. A brand-new 1-hour flight is generated and analysed in about 2 s.
- The verdict box shows when the ML ensemble and the Bayesian twin detected it, the diagnosis, and the warning time.
- Also run **Healthy engine** → no false alarm.

**5. Model Validation (1.5 min)**
- Top KPIs: "On 60 simulated fault flights the ML ensemble caught 59 before failure. One bearing-wear fault was flagged
  too late; that is a real weakness. One false alarm in 80 healthy flight-hours. Every number has a 95% confidence interval."
- **Ablation table:** "Alone, the three detectors raised 10, 33 and 78 false alarms over the same hours. Fused, 1."
- **Explainable AI panel:** "I didn't just draw explanations, I checked them: the top-ranked sensor matched the
  fault's physics in 60/60 test flights, and the heatmap shows each fault lighting up its own sensors."
- **Flagship panel:** "The twin detected 60/60 with zero false alarms, and its uncertainty is validated: the 90% RUL
  interval contains the true failure time 90.0% of the time."

**6. How it works + honest limitations (1 min). Say this before you are asked**
- Walk the pipeline.
- "Everything is simulated, and my twin uses the same equations as the simulator, so these results are an upper bound.
  The next step is a reality-gap study and calibration on real engine recordings."

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
Yes for the sensor physics, and that is the main limitation. It does not know the degradation law, the rate or the onset
time, and it was tuned only on separately simulated flights. On a real engine the physics model must first be calibrated.

**Why is the twin so much faster than the ML ensemble?**
Partly design: the ML path waits for a 60 s window and 80 s of persistence before alarming, while the filter decides every
second. Partly the matched model. It is not a like-for-like comparison, and I don't claim a speed-up factor.

**How do you know the uncertainty is right?**
Coverage testing: over about 3,000 predictions, the 90% interval contained the true failure time 90.0% of the time
(95% CI 87.7–92.0%, bootstrapped over flights). The 50% interval is somewhat over-confident.

**What is α-λ accuracy?**
A standard prognostics metric (Saxena et al.): the fraction of RUL predictions within ±α (here 20%) of the true RUL.
Twin 33%; the Health-Index trend 1.2%, though that method targets a different threshold, so it isn't a fair comparison.

**How do you explain the ML's decisions? Why not SHAP?**
Sensor-level counterfactual occlusion: reset one sensor's residual to healthy, re-score all three models, and measure
the drop in their raw anomaly score. It works identically for the Isolation Forest, PCA, the LSTM and the fusion, and
answers "which sensor?" directly. TreeSHAP would only cover the Isolation Forest, at the level of 45 window statistics.
I validated the explanations against ground truth: the top sensor was physically correct in 60/60 test flights.

**Why train only on healthy data?**
Real fleets have almost no recorded failures. Unsupervised detectors learn "normal" and flag anything else, so they
need no fault labels.

**How do you avoid false alarms?**
An alert needs HI < 50 for 8 consecutive windows (80 s). On the test split: 1 false-alarm event in 80.3 healthy
flight-hours (95% CI 0.0003–0.069 per hour). One event is too few for a precise rate, so I report the interval.

**How does diagnosis work? Is it ML?**
Physics rules, which makes it explainable: oil-pressure drop = lubrication, all CHTs up = cooling, one cylinder's EGT up =
lean cylinder, one EGT down + vibration up = misfire, vibration only = bearing. I developed the rules on an earlier dataset,
then froze them and checked them on a separate development split before the final test split was evaluated once. In this
dataset the faulty cylinder is always 1 or 2, so cylinder accuracy should be re-tested with random cylinders.

**Is there data leakage?**
Every split comes from its own seed block, the scaler and models are fit on healthy training data only, and the test split
was evaluated once. The bigger caveat isn't leakage but the matched model: the twin and the simulator share equations.

**Why "lean cylinder" and not "injector fault"?**
The Rotax 912 S/ULS is carburetted, so a single lean cylinder points to an intake leak or fuel-metering problem.

**Would it work on a real engine?**
Not without calibration. The physics twin's parameters must be fitted to real recordings, then every metric re-measured.

**Tech stack?**
Python, NumPy/Pandas, scikit-learn, PyTorch (LSTM-AE), FastAPI (REST + WebSocket), React + Vite + Recharts. 49 automated
tests (`python3 -m pytest`), including physics invariants, metric correctness and dataset reproducibility.
