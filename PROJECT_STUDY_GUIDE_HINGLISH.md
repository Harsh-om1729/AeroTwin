# AeroTwin – Complete Study Guide (Hinglish)

> **Ye document kis liye hai?**
> Is file mein aapke project ki poori kahani hai – bilkul zero se lekar advanced level tak. Har topic ke liye teen cheezein
> explain ki gayi hain:
> **WHAT** (ye kya hai), **WHY** (kyun banaya/zaroori hai), **HOW** (kaise kaam karta hai).
> Shuru mein engine ki basic jaankari hai, kyunki bina engine samjhe project samajhna mushkil hai.
> Aaraam se, ek-ek section padhiye. Har section ke end mein "Yaad rakhne wali baat" (key takeaway) hai.

---

## Index

1. [Engine ki basic jaankari (bilkul zero se)](#1-engine-ki-basic-jaankari-bilkul-zero-se)
2. [Problem: MALE UAV aur predictive maintenance](#2-problem-male-uav-aur-predictive-maintenance)
3. [Digital Twin kya hota hai?](#3-digital-twin-kya-hota-hai)
4. [Project ki journey – scratch se advanced tak](#4-project-ki-journey--scratch-se-advanced-tak)
5. [Simulator: engine ko computer mein banana](#5-simulator-engine-ko-computer-mein-banana)
6. [Residuals: "expected vs actual" ka farak](#6-residuals-expected-vs-actual-ka-farak)
7. [Windows aur features](#7-windows-aur-features)
8. [Unsupervised ML models (IF, PCA, LSTM)](#8-unsupervised-ml-models-if-pca-lstm)
9. [Fusion aur Health Index](#9-fusion-aur-health-index)
10. [Fault diagnosis (signature check)](#10-fault-diagnosis-signature-check)
11. [Bayesian Health Twin – Flagship (particle filter)](#11-bayesian-health-twin--flagship-particle-filter)
12. [RUL – Remaining Useful Life](#12-rul--remaining-useful-life)
13. [Mission Advisor (GO / CAUTION / NO-GO)](#13-mission-advisor-go--caution--no-go)
14. [Evaluation: results kaise naape](#14-evaluation-results-kaise-naape)
15. [Audit aur P0 fixes (galtiyan pakdi aur theek ki)](#15-audit-aur-p0-fixes-galtiyan-pakdi-aur-theek-ki)
16. [Explainable AI (XAI)](#16-explainable-ai-xai)
17. [Robustness: CUSUM baseline + Reality-Gap study](#17-robustness-cusum-baseline--reality-gap-study)
18. [AI Maintenance Copilot (Gemini / Claude / Offline)](#18-ai-maintenance-copilot-gemini--claude--offline)
19. [Dashboard, Backend, Tests – software side](#19-dashboard-backend-tests--software-side)
20. [Honest limitations (kya abhi nahi hai)](#20-honest-limitations-kya-abhi-nahi-hai)
21. [Viva / Teacher ke sawal aur jawab](#21-viva--teacher-ke-sawal-aur-jawab)
22. [Glossary – mushkil shabdon ka matlab](#22-glossary--mushkil-shabdon-ka-matlab)
23. [File map – kaunsi file kya karti hai](#23-file-map--kaunsi-file-kya-karti-hai)

---

## 1. Engine ki basic jaankari (bilkul zero se)

### 1.1 Piston engine kya hota hai?

**WHAT:** Piston engine ek machine hai jo **fuel (petrol) jala kar** usse **ghoomne wali shakti (rotation)** banati hai.
Car, bike, chhote aeroplane – sab mein ye hota hai.

**HOW – 4-stroke cycle (ek cylinder ke andar):**

```
 1. INTAKE      Piston neeche jaata hai -> hawa + petrol ka mixture andar aata hai
 2. COMPRESSION Piston upar jaata hai   -> mixture daba diya jaata hai (compress)
 3. POWER       Spark plug chingari deta hai -> mixture jalta hai -> dhamaka piston ko neeche dhakelta hai
 4. EXHAUST     Piston upar jaata hai   -> jali hui gas (exhaust) bahar nikal jaati hai
```

Piston ek **crankshaft** se juda hota hai. Piston upar-neeche hota hai, crankshaft use **ghoomne (rotation)** mein badal deta hai.
Crankshaft se **propeller** ghoomta hai (gearbox ke through), aur propeller hawa ko peeche dhakel kar aircraft ko aage le jaata hai.

### 1.2 Rotax 912 – hamara engine

**WHAT:** Rotax 912 ek bahut popular aircraft piston engine hai (Austria ki company BRP-Rotax ka). Ye light aircraft aur kai
UAVs (drones) mein use hota hai. Hamara project "912 S/ULS" variant ke limits use karta hai.

Iski main baatein (general jaankari – exact values ke liye Rotax manual dekhiye):

| Feature | Matlab |
|---|---|
| **4 cylinders** | 4 piston, har ek apne cylinder mein |
| **Horizontally opposed ("boxer")** | 2 cylinder left, 2 right, flat layout – balance achha, vibration kam |
| **4-stroke** | upar wala intake–compression–power–exhaust cycle |
| **Liquid-cooled heads + air-cooled cylinders** | Cylinder ka sir (head) coolant se thanda hota hai, baaki hawa se |
| **Dry-sump lubrication** | Oil alag tank mein rehta hai, pump use engine mein ghumata hai |
| **Dual ignition** | Har cylinder mein 2 spark plugs, 2 alag ignition circuits – ek fail ho to doosra chalta hai (safety) |
| **2 carburettors (912 ULS/S)** | Carburettor hawa aur petrol ko sahi ratio mein milata hai (fuel injector **nahi** hai) |
| **Reduction gearbox** | Engine RPM zyada hota hai, gearbox propeller ki speed kam karta hai |
| Power | Roughly 100 hp class (912 ULS/S) |

> **Yaad rakhne wali baat:** Isi liye project mein "injector fault" ko **"Lean cylinder (fuel metering / intake leak)"** kaha gaya –
> kyunki 912 S/ULS mein carburettor hota hai, injector nahi.

### 1.3 Engine ke sensors – dashboard par jo dikhta hai

Engine ko "dekhne" ke liye sensors lagaye jaate hain. Hamare project mein ye sensors hain (1 reading per second = 1 Hz):

| Sensor | Full form / matlab | Kya batata hai | Normal (approx, simulation) |
|---|---|---|---|
| **RPM** | Revolutions Per Minute | Engine kitni tezi se ghoom raha hai | cruise ~4800 |
| **Throttle %** | Pilot/autopilot ka "accelerator" | Kitni power maangi gayi | cruise 75% |
| **Oil pressure** | Oil kitne dabav se ghoom raha hai | Lubrication (chikna-pan) theek hai ya nahi | 2–5 bar normal |
| **Oil temperature** | Oil ka taapmaan | Garmi aur cooling ka haal | 90–110 °C normal (manual) |
| **CHT 1–4** | Cylinder Head Temperature | Har cylinder ka sir kitna garam | max 135 °C |
| **EGT 1–4** | Exhaust Gas Temperature | Har cylinder ki jali gas kitni garam – combustion ka haal | max 880 °C |
| **Fuel flow** | Litre per hour | Kitna petrol jal raha hai | cruise ~18 L/h |
| **Vibration** | g RMS | Engine kitna hil raha hai | ~2.5 g at cruise |
| **Altitude, ambient temp** | Unchai, bahar ka taapmaan | Environment | — |

**EGT aur CHT ka farak (bahut important):**
- **EGT** = exhaust gas ka temperature → combustion ka *turant* signal (seconds mein badalta hai).
- **CHT** = cylinder ke metal ka temperature → *dheere* badalta hai (metal garam hone mein time lagta hai).

### 1.4 Engine limits (Rotax 912 S/ULS manual se – `configs/engine_rotax912.yaml`)

| Parameter | Limit |
|---|---|
| RPM | idle ≥ 1400, max continuous 5500, max take-off 5800 (sirf 5 minute) |
| Oil pressure | 0.8 – 7.0 bar (normal 2–5 bar) |
| Oil temperature | 50 – 130 °C (normal 90–110 °C) |
| CHT | max 135 °C |
| EGT | max 880 °C |

**WHY important:** Agar koi limit cross ho jaaye to engine ko nuksaan ho sakta hai. Hamara advisor in limits ko check karta hai.

### 1.5 Engine mein kya kharab ho sakta hai? (5 faults jo humne model kiye)

| Fault | Real life mein kya hota hai | Sensor par kya dikhta hai |
|---|---|---|
| **Lubrication degradation** | Oil pump kamzor, oil kam, filter jam → engine ke parts ko chikna-pan nahi milta | **Oil pressure girta hai** |
| **Cooling degradation** | Radiator jam, coolant leak, hawa ka raasta band → engine thanda nahi hota | **Oil temp + chaaron CHT badhte hain** |
| **Lean cylinder** (code mein `injector_abnormality`) | Ek cylinder ko kam petrol/zyada hawa (intake leak) → mixture "lean" | **Us ek cylinder ka EGT badhta hai** |
| **Misfire** | Spark plug/ignition lead kharab → cylinder theek se nahi jalta | **Us cylinder ka EGT girta hai + vibration badhta hai** |
| **Bearing wear (abnormal vibration)** | Bearings ghis gaye, propeller unbalance | **Vibration badhta hai, temperatures normal** |

> **Yaad rakhne wali baat:** Har fault ka ek alag "fingerprint" hai. Isi fingerprint se hum batate hain ki **kaunsa** fault hai
> aur **kaunse cylinder** mein hai.

---

## 2. Problem: MALE UAV aur predictive maintenance

**WHAT:** **MALE UAV** = Medium-Altitude Long-Endurance Unmanned Aerial Vehicle – bina pilot ka aircraft jo lambe time
(ghanton) tak udta hai. Inmein aksar Rotax jaise piston engine hote hain.

**WHY problem hai:**
- Engine fail = poora aircraft gir sakta hai (koi pilot nahi jo emergency landing kare).
- **Fixed-interval maintenance** (har X ghante baad check) mehenga hai aur beech mein develop hone wale fault miss ho jaate hain.

**Solution ka idea – Predictive Maintenance:** Sensors ko lagataar dekho, fault ko **shuru mein hi** pakdo, batao **kya** kharab
hai, **kitna time bacha hai** (RUL), aur **agla mission udna safe hai ya nahi**.

---

## 3. Digital Twin kya hota hai?

**WHAT:** Digital twin = asli machine ka ek **computer model** jo batata hai ki *healthy* machine is waqt kya reading degi.

**Simple example:** Agar engine 75% throttle par 5000 feet par ud raha hai aur bahar 5 °C hai, to twin batayega:
"Healthy engine ka oil pressure ~4.8 bar hona chahiye, CHT ~106 °C hona chahiye..."

**WHY:** Climb ke time engine garam hota hai – ye *normal* hai. Agar hum raw temperature dekhein to har climb fault lagega.
Twin "normal" ko pehle se predict karta hai, to hum sirf **unexpected** cheez pakadte hain.

**HOW:** `measured − expected (twin) = residual`. Healthy engine mein residual ≈ 0 (sirf sensor noise). Fault aaya to residual
ek taraf khisak jaata hai.

```
   Asli engine sensors ──┐
                         ├──► residual = measured − expected ──► ML + Bayesian twin ──► fault? kaunsa? kitna time?
   Physics twin (healthy)┘
```

---

## 4. Project ki journey – scratch se advanced tak

| Step | Kya hua | Kyun |
|---|---|---|
| 0 | Aapke paas pehle se: simulator, residuals, 3 ML models, Health Index, basic FastAPI + chhota dashboard | Base project |
| 1 | **Full-stack upgrade:** fault diagnosis, Go/No-Go advisor, Fault Lab, 5-page dashboard, validation report, run.sh | Demo-ready banane ke liye |
| 2 | **Flagship – Bayesian particle-filter twin:** hidden health + RUL with uncertainty | Project ki pehchaan (unique part) |
| 3 | **Audit (code-level):** galtiyan dhoondhi – oracle twin, ISA bug, test-set tuning, false-alarm unit galat, data reproducible nahi | Honest aur defensible banane ke liye |
| 4 | **P0 fixes:** physics bugs theek, seeded dataset v2.0, dev/test split, event-based false alarms + confidence intervals | Results bharosemand banaye |
| 5 | **UI/UX:** animated background, boot screen, radar, health rings, toasts, keyboard shortcuts | Presentation achha lage |
| 6 | **Explainable AI:** kaunsa sensor alert ka kaaran – aur explanation sahi hai ya nahi, check kiya | ML ko black box nahi rehne diya |
| 7 | **Robustness:** CUSUM baseline + reality-gap study + per-engine calibration | "Twin galat ho to kya?" ka jawab |
| 8 | **AI Copilot:** Claude/Gemini se plain-language Q&A, offline fallback ke saath | Modern AI ka sahi, safe use |
| 9 | **Gemini fix:** model retired + overload → model list with auto-switch | Copilot ko reliable banaya |

---

## 5. Simulator: engine ko computer mein banana

> Asli engine ka fault data milna lagbhag namumkin hai (koi jaan-boojh kar engine kharab nahi karta). Isliye humne
> **simulator** banaya jo flights + faults generate karta hai, aur jahan **asli jawab (ground truth)** pata hota hai.

### 5.1 Atmosphere (ISA) – `aerotwin/simulator/atmosphere.py`

**WHAT:** ISA (International Standard Atmosphere) batata hai ki unchai par hawa ka temperature, pressure aur density kya hoti hai.
Unchai badhne par hawa **patli** hoti hai (density kam).

**WHY:** Patli hawa = engine mein kam oxygen = kam power. Ye **Gagg-Ferrar formula** se model kiya:

```
P_available / P_sea_level ≈ 1.132 × σ − 0.132      (σ = density ratio, sea level par 1)
```

**Bug jo humne pakda aur theek kiya (P0):** Pehle code altitude ka temperature-lapse **do baar** laga raha tha. 15,000 ft par
bahar −25 °C tha, par model −55 °C samajh raha tha! Ab `isa_from_oat()` sahi temperature use karta hai (5,000 ft par σ = 0.862 – textbook value).

### 5.2 Engine model – `aerotwin/simulator/engine_model.py`

**HOW (simple heuristic equations – ye exact Rotax physics nahi, ek approximation hai):**
- Oil pressure ≈ 1.5 + 4 × (RPM/5800) bar
- Oil temp, CHT, EGT target = ambient + (power ke hisaab se badhta hua rise)
- **Thermal lag:** temperature turant nahi badalta: `dT/dt = (T_target − T)/τ`, jahan τ = 120 s (oil), 60 s (CHT), 5 s (EGT)
- Har sensor par random noise (asli sensors jaisa)

**Faults ka asar (`apply_health()`):** har component ki "health" 1 (bilkul theek) se 0 (khatam) tak hoti hai:
- Lubrication: oil pressure × health
- Cooling: temperature ka *rise above ambient* × (2 − health) → cooling kam = zyada garam
- Lean cylinder: us cylinder ka EGT + 150 °C × (1 − health) (bounded – real physics jaisa)
- Misfire: us cylinder ka EGT − 100 °C × (1 − health), vibration badhta hai
- Bearing: vibration × (2 − health)

**P0 fix:** Pehle temperature ko °C mein multiply kiya ja raha tha (unit galti – EGT 1080 °C tak ja raha tha). Ab "rise above ambient" par lagta hai.

### 5.3 Mission profile – `mission_profiles.py`

Har flight 1 ghante (3600 s) ki: **taxi** (0–300 s) → **climb** (300–600 s, full power, 5000 ft tak) → **cruise** (75% power)
→ **descent** (last 10 min). Profiles: standard, hot weather (+35 °C), high altitude (15,000 ft), rapid throttle.

### 5.4 Fault injection – `fault_injection.py`

Fault ek random time (onset) par shuru hota hai aur health ghatti hai:

| Fault | Ghatne ka tareeka | Rate | Failure tab maana jab health < |
|---|---|---|---|
| Lubrication | exponential | 0.001 /s | 0.30 |
| Cooling | exponential | 0.002 /s | 0.40 |
| Lean cylinder (cyl 1) | exponential | 0.003 /s | 0.40 |
| Misfire (cyl 2) | linear | 0.005 /s | 0.50 |
| Bearing | exponential | 0.002 /s | 0.30 |

**Failure time** formula se exact nikalta hai (`compute_failure_t`) – isse hum "warning kitne pehle di" naap sakte hain.

### 5.5 Dataset v2.1 – `generate_dataset.py` (seeded, reproducible)

| Split | Flights | Kis kaam | Rule |
|---|---|---|---|
| train_healthy | 140 | ML models train | sirf healthy |
| val_healthy | 28 | calibration (fusion, Health Index) | sirf healthy |
| **val_fault** | 20 | **development** – rules/thresholds tune karne ke liye *yahi* fault data | |
| test_healthy | 60 (hot weather) | false alarms (final) | |
| test_fault | 60 (5 faults × 12) | final results – **sirf ek baar** evaluate | |

Total **308 flights**, har ek ka apna **seed** → kisi bhi computer par **byte-identical** data banta hai (ye humne test kiya).

> **Yaad rakhne wali baat:** Test data ko tuning ke liye kabhi use nahi kiya jaata – warna result "cheating" ho jaata hai.

---

## 6. Residuals: "expected vs actual" ka farak

**WHAT:** `residual = measured − twin_expected` – 15 channels (oil P, oil T, fuel, vibration, alternator, CHT1–4, EGT1–4,
CHT spread, EGT spread). File: `aerotwin/features/residuals.py`.

**WHY:** Flight conditions (climb, garmi, unchai) ka asar hata dete hain – sirf "unexplained" behaviour bachta hai.

**HOW:** Twin ko bilkul same RPM/throttle/altitude/temperature par chalaya jaata hai (thermal lag ke saath), phir subtract.

---

## 7. Windows aur features

**WHAT:** Har second ka data akela bahut noisy hota hai. Isliye **60-second ki window**, har **10 second** aage khiskaate hain
(1 flight = ~355 windows). File: `aerotwin/features/windowing.py`.

**HOW:** Har window aur har channel ke liye 3 numbers: **mean, std (fluctuation), slope (badhne ki disha)** → 15 × 3 = **45 features**.
Pehle `StandardScaler` se scale (sirf training healthy data par fit – leakage nahi).

---

## 8. Unsupervised ML models (IF, PCA, LSTM)

**WHY unsupervised?** Asli duniya mein fault ka data (labels) bahut kam hota hai. Isliye models ko sirf **healthy** data par
train kiya – ye "normal" seekhte hain, aur jo normal nahi wo anomaly.

| Model | Kya hai (simple) | Anomaly score |
|---|---|---|
| **Isolation Forest (IF)** | Random "kaat-ne wale" trees. Ajeeb point jaldi alag (isolate) ho jaata hai | Jitna jaldi isolate, utna ajeeb |
| **PCA (SPE)** | Normal data ke main patterns (principal components) seekhta hai | Jo hissa patterns se explain nahi hua (reconstruction error) |
| **LSTM Autoencoder** | Neural network jo 60-second sequence ko compress karke wapas banata hai | Wapas banane mein kitni galti (reconstruction error) |

Training: `aerotwin/evaluation/train_models.py` (seeded – reproducible).

---

## 9. Fusion aur Health Index

**WHAT:** Teen models ke scores ko ek number mein milana – **Health Index (HI): 0 = failed, 100 = as new**.
File: `aerotwin/models/fusion.py`, `aerotwin/health/health_index.py`.

**HOW:**
1. Har model ka score → healthy validation data ke against **percentile** (0–100).
2. Teeno percentiles ka **average** = fused score.
3. `HI = 100 × (1 − (score/100)^p)`, jahan p = 4.25 (aisa chuna ki median healthy window ka HI = 95).
4. **Alert:** HI < 50 lagataar **8 windows** (80 second) → alert. **Degrading:** HI < 80 lagataar 5 windows.

**WHY 3 models (ensemble)?** Har model alag galti karta hai. Test par false-alarm **events** (80 healthy flight-hours mein):
Isolation Forest **13**, PCA **32**, LSTM **77**, **Fused ensemble sirf 2**. Ye "ablation study" hai.

> Note: HI asal mein ek "kitna ajeeb hai" (surprise) score hai, physical health nahi. Physical health Bayesian twin deta hai (section 11).

---

## 10. Fault diagnosis (signature check)

**WHAT:** "Kya kharab hai aur kaunse cylinder mein?" – physics rules se. File: `aerotwin/diagnosis/fault_diagnosis.py`.

**HOW:** Window ke residuals ko "kitne sigma (σ) door" mein naapte hain, phir fingerprint match:
- Oil pressure bahut neeche → lubrication
- Saare CHT ek saath upar → cooling
- Ek EGT upar → lean cylinder (wahi cylinder)
- Ek EGT neeche + vibration upar → misfire (wahi cylinder)
- Sirf vibration upar → bearing

**Result (test):** fault type **58/60**, cylinder **24/24** sahi. (Honest note: rules pehle purane dataset par develop hue,
phir freeze karke dev split par check kiye, phir naya test set ek baar evaluate.)

---

## 11. Bayesian Health Twin – Flagship (particle filter)

> Ye project ka **sabse unique hissa** hai – "I designed and implemented this."

### 11.1 Idea (simple)

**WHAT:** Koi sensor seedha "oil pump ki health 0.71 hai" nahi batata. Ye **hidden** hai. Particle filter sensors se
ise **infer** (andaza) karta hai – aur saath mein **kitna pakka** hai (uncertainty) bhi batata hai.

**Analogy:** Socho 1,320 jasoos hain. Har jasoos ki apni theory hai: "mujhe lagta hai oil pump 0.85 health par hai aur
0.2% per second gir raha hai". Har second asli sensor reading aati hai. Jis jasoos ki theory reading se match karti hai,
uski baat ka "weight" badhta hai; jo galat hai uska ghatta hai. Kamzor theories hata kar achhi theories copy hoti hain
(resampling). Kuch der mein saare jasoos sach ke paas aa jaate hain.

### 11.2 HOW – technical (file: `aerotwin/twin/particle_filter.py`)

- **11 hypotheses** (theories): lubrication, cooling, lean cylinder × 4, misfire × 4, bearing → har ek ke **120 particles** = **1,320**.
- Har particle ka state: **health h**, **degradation rate r**, **onset flag** (fault shuru hua ya nahi – kyunki onset time pata nahi), apna thermal state.
- Har second:
  1. **Predict:** har particle physics model chala kar sensor reading predict karta hai.
  2. **Update:** asli reading se match → Gaussian **likelihood** → weight.
  3. **Bayes' rule:** har hypothesis ki probability update ("kaunsa fault zyada sambhav").
  4. **Resample:** kamzor particles hatao, achhe copy karo.
- Tuning **sirf alag simulated flights** par ki (`aerotwin/twin/tune.py`) – test set kabhi nahi.
- Ek problem aayi thi: **particle impoverishment** (saare particles ek jaise ho gaye, filter piche reh gaya) – rate diversity
  badha kar theek kiya.

### 11.3 Output

P(component degraded), sabse sambhav fault + cylinder, **health 0–1 with 90% interval**, degradation rate, **RUL distribution**,
P(failure within next 60-min mission).

### 11.4 Results (test split)

| | Bayesian twin | ML ensemble |
|---|---|---|
| Faults detected | **60/60** | 58/60 |
| Diagnosis (type + cylinder) | **60/60** | 58/60 |
| False-alarm events (80.3 h) | **0** | 2 |
| Median detection delay | **37.5 s** | 108 s |
| Hidden health error (MAE) | **0.006** | – |
| 90% RUL interval mein asli failure time | **91.1%** (95% CI 88.8–92.9%) – achhi calibration | – |

> **Honest note:** Twin wahi physics equations use karta hai jo simulator ne data banane mein use kiye. Isliye ye
> results "upper bound" hain. Section 17 mein dekha ki twin galat ho to kya hota hai.

---

## 12. RUL – Remaining Useful Life

**WHAT:** "Failure tak kitna time bacha hai?"

**HOW – do tareeke:**
1. **Linear trend** (`aerotwin/health/rul.py`): HI ki line ko 50 tak extend karo. Simple par weak.
2. **Particle filter RUL:** har particle `(health − failure_limit) / rate` → poori distribution → median + 90% interval.

**Result:** Twin ka median error **56 s**, linear ka **263 s**. ±20% ke andar: twin **36%**, linear **0.8%**.
(Fair comparison nahi – linear HI=50 tak ka time nikalta hai, truth physical failure hai. Isliye "x guna better" claim nahi karte.)

---

## 13. Mission Advisor (GO / CAUTION / NO-GO)

**WHAT:** Final decision – agla mission udna hai ya nahi. File: `aerotwin/advisor/mission_advisor/go_nogo.py`.

**HOW – 4 evidence sources:**
1. **Hard limits** (Rotax redlines) cross → NO-GO
2. **ML alert** (ya pehle alert latch hua) → NO-GO
3. **Bayesian twin:** P(failure in next 60-min mission) ≥ 10% → NO-GO; degraded par kam risk → CAUTION
4. **Degrading HI** → CAUTION

"Latch" = ek baar alert aaya to inspection tak NO-GO rehta hai (flicker nahi karta).

---

## 14. Evaluation: results kaise naape

- **Detection:** fault onset ke baad aur failure se pehle alert aaya? (aur ab sirf **naya** alert count hota hai)
- **Lead time:** failure se kitna pehle warning (ML median **5.1 min**; lubrication ~16 min, misfire ~10 s kyunki misfire bahut tez hai)
- **False alarms:** healthy time mein alarm **events** per flight-hour + **95% confidence interval**
- **Confidence intervals:** 60/60 ka matlab "100%" nahi – statistically "≥ 94% (95% CI)" kehna chahiye (Clopper-Pearson)
- Sab kuch `aerotwin/evaluation/report.py` se recompute hota hai (`cache/results.json`), haath se nahi likha.

---

## 15. Audit aur P0 fixes (galtiyan pakdi aur theek ki)

Ek code-level audit kiya (Claude Docs mein report bani). Critical galtiyan aur fix:

| Galti | Fix |
|---|---|
| Naya clone chalu hi nahi hota tha (`data/` git mein nahi, run.sh generate nahi karta) | run.sh ab data alag se check karke generate karta hai |
| Data reproducible nahi (random onset bina seed) | Har flight ka seed, dataset version 2.0 |
| ISA mein lapse rate do baar | `isa_from_oat()` |
| Faults °C ko multiply karte the (unit galti) | rise-above-ambient par asar |
| False alarms windows mein gine jaate the | ab **events** + confidence interval |
| Diagnosis rules test data dekh kar tune hue | dev split (`val_fault`) banaya, test sirf ek baar |
| Over-claims ("held-out airframes", "live", "10× faster") | wording sab jagah theek |

**Seekh:** Achha project woh hai jo apni kamzoriyan khud pakde aur theek kare.

---

## 16. Explainable AI (XAI)

**WHAT:** "ML ne alert **kyun** diya? Kaunse sensor ki wajah se?" File: `aerotwin/xai/attribution.py`.

**HOW – counterfactual occlusion:** Ek-ek sensor ko "healthy" value par set karo, teeno models ko dobara score karo. Score
jitna gira = us sensor ka **share of evidence**. Raw scores use kiye (percentile 100 par atak jaata hai – saturation).

Example: "Agar oil pressure healthy hota to fused anomaly percentile 97 se 49 par aa jaata."

**WHY SHAP nahi?** SHAP sirf Isolation Forest ke 45 statistics samjhata; hamara tareeka teeno models + fusion ke liye
**sensor level** par kaam karta hai.

**Validation (sabse important):** Kya explanation **sahi** hai? Top sensor = fault ka physical sensor?
Ensemble **58/58**, LSTM 58/58, PCA 57/58, IF 53/58. Do false alarms bhi explain hue: CHT 4 blip (61%) aur CHT 1 blip (74%).

---

## 17. Robustness: CUSUM baseline + Reality-Gap study

### 17.1 CUSUM baseline – `aerotwin/models/cusum.py`

**WHAT:** Textbook ka simple statistical detector – chhote-chhote deviations ko jodta rehta hai; sum threshold cross kare to alarm.
`S+ = max(0, S+ + z − k)`, k = 0.5, threshold h ≈ 15.9 (healthy validation par calibrate).

**WHY:** Agar twin bilkul sahi ho, to residual sirf white noise hai – is case mein CUSUM **theoretically optimal** hai.
Fair comparison ke liye zaroori.

**Matched comparison** (same false-alarm rate ≤ 0.05/FH par): Bayesian twin **46 s**, CUSUM **54 s**, ML ensemble is rule ke
saath reach nahi karta (apne 8-window rule ke saath 108 s). **Matlab: perfect twin par simple CUSUM bhi utna hi achha hai.**

### 17.2 Reality-Gap study – `aerotwin/simulator/variation.py`, `aerotwin/evaluation/gap_study.py`

**WHAT:** Ek "asli" engine banaya jo twin se thoda **alag** hai – knob `gap` 0 se 1: har engine ke CHT/EGT offsets, pump gain,
heat-rejection error, time constants ±30%, sensor bias, drift, coloured noise.

**HOW:** Same 30 flights 8 gap levels par (paired design) – sirf mismatch badla.

**Result – "usable" (≤ 5% healthy time false alarm, ≥ 90% faults pakde) kahan tak:**

| | ML ensemble | **Bayesian twin** | CUSUM |
|---|---|---|---|
| Bina calibration | 0.00 | **0.10** | 0.00 |
| Per-engine calibration ke saath | 0.20 | **0.50** | 0.05 |

**Seekh:**
- CUSUM perfect duniya mein best, par **sabse fragile** (gap 0.05 par 82% time false alarm).
- Bayesian twin **sabse gracefully** degrade hota hai.
- **Calibration** (ek healthy reference flight se offsets nikal kar subtract) bahut zaroori hai.
- Honest: gap badhne par twin ke RUL intervals over-confident ho jaate hain.

---

## 18. AI Maintenance Copilot (Gemini / Claude / Offline)

**WHAT:** Chat page jahan engineer simple bhasha mein poochta hai: "Kaunsa aircraft pehle inspect karein?", "AT-104 grounded kyun hai?"

**WHY:** Engineers ke liye results ko samajhna aasaan banana – **par AI decision nahi leta**, sirf explain karta hai.

**HOW (files: `aerotwin/copilot/`):**
- **Grounding:** AI sirf 6 read-only **tools** se data padh sakta hai – fleet overview, aircraft status, event timeline,
  engine limits, maintenance actions, validation summary. Har number tool se aana chahiye; nahi pata to "data mein nahi hai".
  Go/No-Go kabhi override nahi karta.
- **Providers ka order:** **Gemini** (models: `gemini-3.5-flash-lite` → `gemini-flash-lite-latest` → `gemini-3.8-flash`)
  → **Claude** (`claude-opus-5-5`, agar key ho) → **Offline engine**.
- **Hamesha jawab deta hai:** key nahi, credit khatam, internet nahi, model overloaded, rate limit, timeout – har case mein
  offline engine wahi data se jawab deta hai, aur UI batata hai kis engine ne jawab diya aur kyun.
- **Security:** API key sirf `.env` file mein (git ignore), browser ko nahi bheji jaati, log mein nahi aati.

**Gemini wali dikkat jo theek ki:** server key add karne se pehle chal raha tha (restart chahiye tha), `gemini-2.5-flash`
naye users ke liye band ho gaya, aur bade models "high demand" (503) de rahe the → model list + auto-switch + kam retries.

> **Zaroori:** Aapki Gemini key screenshot mein dikh gayi thi – AI Studio mein usse delete karke nayi key banaiye.

---

## 19. Dashboard, Backend, Tests – software side

### 19.1 Backend – `backend/main.py` (FastAPI)
REST API (`/api/fleet`, `/api/simulate`, `/api/results`, `/api/gap-study`, `/api/copilot`, …), WebSocket stream, aur
built dashboard serve karta hai. Startup par 8 fleet flights pipeline se chalti hain.

### 19.2 Dashboard – `dashboard/` (React + Vite + Recharts)
| Page | Kya hai |
|---|---|
| **Fleet Command** | 8 aircraft, radar, health rings, GO/NO-GO |
| **Twin Replay** | flight replay, animated engine, gauges, Bayesian twin panel, XAI panel, event log, report, toasts |
| **Fault Injection Lab** | apna fault chuno, nayi flight simulate (≈2 s), reality-gap slider, calibration toggle |
| **AI Copilot** | chat with grounded answers |
| **Model Validation** | saare results, confidence intervals, ablation, XAI check, robustness study |
| **How it works** | pipeline, design decisions, limitations |

Keyboard: Space = play/pause, ←/→ = step. "Reduce motion" setting par animations band.

### 19.3 Tests – `tests/` (pytest)
**103 tests** (102 pass + 1 documented "expected failure": ML ensemble bearing fault kabhi-kabhi late pakadta hai).
Physics invariants, metrics, data reproducibility, particle filter, XAI, robustness, copilot (fake Claude/Gemini clients se
har failure case).

### 19.4 Chalana kaise hai
```bash
cd aero-digital-twin
./run.sh               # sab install/generate/build karke http://localhost:8000 kholta hai
./run.sh --retrain     # models dobara train
python3 -m pytest -q   # tests
python3 -m aerotwin.evaluation.gap_study   # robustness study (~5 min)
```
`.env` badalne ke baad hamesha `./run.sh` **restart** karein.

---

## 20. Honest limitations (kya abhi nahi hai)

- **Saara data simulated hai** – asli engine par test nahi hua.
- Main test mein twin = simulator ki equations (upper bound). Mismatch ka asar gap study mein dikhaya.
- Engine equations simple heuristic hain (manifold pressure, AFR, propeller load nahi).
- Ek time par ek hi fault; **sensor faults** (stuck/drift probe) abhi model nahi.
- Test mein har fault ki ek hi severity; faulty cylinder hamesha 1 ya 2.
- Ye decision-support prototype hai, certified airworthiness system nahi.

**Next steps:** asli engine recordings (`aerotwin/real_engine/recording_protocol.md`), twin calibration, sensor-fault isolation,
mission what-if risk.

---

## 21. Viva / Teacher ke sawal aur jawab

**Q: Digital twin kya hai aapke project mein?**
A: Ek physics model jo batata hai healthy engine is waqt kya reading dega. Measured − expected = residual; ML aur Bayesian twin
isi residual ko analyse karte hain.

**Q: Unsupervised kyun?**
A: Real fleets mein fault data bahut kam hota hai. Models sirf healthy data se "normal" seekhte hain.

**Q: Teen ML models kyun?**
A: Har model alag galti karta hai. Akele 13/32/77 false-alarm events, milakar sirf 2.

**Q: Particle filter kyun, Kalman filter kyun nahi?**
A: Problem non-linear hai (thermal lag), fault onset ek jump hai, aur hypotheses discrete hain (kaunsa fault, kaunsa cylinder).
Kalman linear-Gaussian maanta hai.

**Q: Kya particle filter ne simulator copy kar liya?**
A: Sensor physics same hai – ye main limitation hai. Par degradation law, rate aur onset nahi pata. Isliye reality-gap study kiya.

**Q: Uncertainty sahi hai ye kaise pata?**
A: Coverage test: 90% interval ne asli failure time 91.1% baar pakda (95% CI 88.8–92.9%).

**Q: Simple CUSUM kyun nahi?**
A: Test kiya! Perfect twin par CUSUM utna hi achha (54 s vs 46 s). Par reality gap 0.05 par hi fail – sabse fragile.

**Q: AI copilot galat data bana dega (hallucinate)?**
A: Sirf 6 read-only tools se data milta hai, har number tool se aana chahiye, aur ye kabhi decision nahi leta. Har answer ke
neeche dikhta hai kaunsa data use hua.

**Q: API fail ho jaaye to?**
A: Gemini → Claude → offline engine. Har failure type test kiya, real invalid-key call bhi.

**Q: Results 100% kyun – fake to nahi?**
A: Simulated aur matched twin ki wajah se. Isliye CI ke saath report karte hain (≥ 94%), aur gap study mein dikhate hain ki
mismatch par kitna girta hai.

**Q: Ye real engine par kaam karega?**
A: Calibration ke bina nahi. Twin ke parameters real recordings se fit karne honge, phir saare metrics dobara naapne honge.

---

## 22. Glossary – mushkil shabdon ka matlab

| Shabd | Matlab |
|---|---|
| **RPM** | engine ek minute mein kitni baar ghoomta hai |
| **CHT / EGT** | cylinder head temperature / exhaust gas temperature |
| **Lean mixture** | petrol kam, hawa zyada – EGT badhta hai |
| **Misfire** | cylinder mein mixture theek se nahi jalta |
| **Residual** | measured − expected |
| **σ (sigma)** | standard deviation – "normal noise kitna hota hai"; 5σ = bahut asaamanya |
| **Window / stride** | 60 s ka tukda / har 10 s aage |
| **Anomaly** | jo normal nahi |
| **Percentile** | healthy data mein se kitne % se zyada ajeeb |
| **Health Index** | 0–100 score (ML ensemble se) |
| **RUL** | failure tak bacha hua time |
| **Particle filter** | bahut saari "theories" (particles) jo data se weight hoti hain |
| **Posterior** | data dekhne ke baad probability |
| **Likelihood** | ye reading is theory ke under kitni sambhav hai |
| **Credible / confidence interval** | range jismein sach hone ki X% sambhavna |
| **Coverage** | 90% interval ne asli value kitni baar pakdi |
| **Calibration** | model ko asli engine ke hisaab se adjust karna / uncertainty ka sahi hona |
| **Ablation** | ek-ek part hata kar dekhna uska kya role hai |
| **False alarm** | healthy engine par galat alarm |
| **Ground truth** | asli sahi jawab (simulator ko pata hota hai) |
| **Data leakage** | test data ka galti se training/tuning mein aa jaana |
| **CUSUM** | cumulative sum – chhote deviations jodne wala detector |
| **Reality gap** | simulation aur asli duniya ka farak |
| **XAI** | Explainable AI – model ka faisla samjhana |
| **LLM** | Large Language Model (Gemini, Claude) |
| **Tool use / grounding** | AI sirf diye gaye tools se data leta hai |
| **Fallback** | pehla tareeka fail ho to backup |

---

## 23. File map – kaunsi file kya karti hai

| File / folder | Kaam |
|---|---|
| `configs/engine_rotax912.yaml` | Rotax engine limits |
| `aerotwin/simulator/` | atmosphere, engine model, missions, faults, dataset, reality-gap engine |
| `aerotwin/features/` | residuals, windows/features |
| `aerotwin/models/` | Isolation Forest, PCA, LSTM-AE, fusion, CUSUM |
| `aerotwin/health/` | Health Index, alert logic, linear RUL |
| `aerotwin/diagnosis/` | signature-check diagnosis |
| `aerotwin/twin/` | **Bayesian particle-filter twin** + tuning |
| `aerotwin/xai/` | explainable AI attribution |
| `aerotwin/advisor/` | GO / CAUTION / NO-GO |
| `aerotwin/inference/` | poori pipeline ek flight par (`replay.py`), Fault Lab simulation |
| `aerotwin/evaluation/` | training, metrics, report, gap study, stats (CI) |
| `aerotwin/copilot/` | AI copilot: evidence tools, Gemini, Claude, offline engine, service |
| `backend/main.py` | FastAPI server |
| `dashboard/src/` | React dashboard (pages + components) |
| `tests/` | 103 automated tests |
| `run.sh` | ek command mein sab chalana |
| `README.md`, `PRESENTATION_GUIDE.md` | English docs + demo script |
| `.env.example` | API keys ka template (`.env` git mein nahi jaata) |

---

> **Last tip:** Presentation se pehle ek baar khud `./run.sh` chala kar har page dekhiye, aur section 21 ke sawal zor se
> bol kar practice kariye. Jo cheez aap simple shabdon mein samjha sakte ho, wahi aapko sach mein aati hai. All the best! ✈️

---

## Real flights (NGAFID) – update

Simulated results upper bound hain, isliye detectors ko **real Cessna 172 flights** par bhi test kiya (NGAFID dataset, Rotax 912 nahi).
Physics twin is engine par laagu nahi hota, isliye ek **learned healthy baseline** banaya (`aerotwin/real_engine/sim2real.py`).

- **Fused ensemble: AUC 0.51** (95% CI 0.49–0.53) – yaani coin flip jaisa. Development fold par 0.54 tha, test par tika nahi.
- **Low oil pressure: AUC 0.68** (95% CI 0.66–0.70) – test par tika, par shayad repair ke saath oil change hone ki wajah se. Isse validated detector mat kehna.
- **Supervised training (labels ke saath):** gradient boosting **AUC 0.74**, par oil pressure hatane par sirf **0.56**. Yaani model zyadatar ek hi sensor padh raha hai.
- Test fold dekhne ke baad kuch tune nahi kiya. Supervised models us fold ka doosra use hain, ye bhi batana.

**Teacher ko kaise bolna hai:** "Simulation par numbers bahut achhe hain, par real flights par ensemble chance level par tha. Maintenance issues in sensors ko bahut kam badalte hain, aur pilot aur mausam bahut zyada."
