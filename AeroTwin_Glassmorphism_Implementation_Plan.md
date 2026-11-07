# AeroTwin — Glassmorphism 2.0 Redesign: Implementation Plan

> **Goal:** Restyle the AeroTwin Engine Digital Twin dashboard as a premium aerospace command center using *Premium Industrial Glassmorphism 2.0*. This changes **only the presentation layer**. Features, data, routes and logic stay as they are.

---

## 0. Scope & Guardrails

### In scope
- Global design tokens (colour, type, spacing, radius, elevation, motion)
- Background and ambient lighting
- Sidebar, Hero / Fleet Command header, radar, KPI cards, aircraft health cards, charts
- Micro-interactions and responsive layout
- Applying the same system to the other pages (Twin Replay, Fault Injection Lab, AI Copilot, Model Validation, How it Works)

### Out of scope (do not touch)
| Area | Rule |
|---|---|
| Backend / API | No changes to endpoints, payloads or fetch logic |
| ML / Bayesian twin | No changes to prediction, health-index or GO/NO-GO logic |
| Data | No dummy data. Every number stays bound to its current source |
| Routing | All 6 routes keep their paths and behaviour |
| Interactions | Aircraft-card click, radar-blip click → replay, "Open replay", chart tooltips all keep working |
| Dependencies | No new UI or animation libraries. CSS plus existing chart lib only |

### Definition of done
1. Every item in the verification checklist (§12) passes.
2. Before/after screenshots at 4 breakpoints show no lost information.
3. No console errors. No network requests change, apart from optional font files.

---

## 1. Phase 0 — Discovery (before any edits)

**Time: ~0.5 day**

1. **Identify the stack**
   - `package.json`: React / Vite / Next? Tailwind, CSS Modules, styled-components or plain CSS?
   - Chart library in use (Recharts, Chart.js, ECharts, D3, or hand-rolled SVG?)
   - Icon set (the screenshot looks like Lucide or Tabler stroke icons. Keep it.)
2. **Map the components** and fill in this table:

   | UI element (screenshot) | Component / file | Styling source | Data source |
   |---|---|---|---|
   | Sidebar + nav | | | route config |
   | "Backend connected" status | | | health-check call |
   | Hero (Twin online, title, chips) | | | fleet summary |
   | Fleet radar | | | aircraft list |
   | KPI cards ×5 | | | fleet summary |
   | Aircraft card ×8 | | | per-aircraft result |
   | Health ring | | | `healthIndex` |
   | Sparkline / trend chart | | | health time series |

3. **Record the data contract per aircraft card.** Find the exact field names for: `id`, `name`, `flightDuration`, `decision` (GO / CAUTION / NO-GO), `healthIndex`, `healthCategory` (nominal / critical / …), `trend[]`, `faultLabel`, `alertTime`.
4. **Capture a baseline:** screenshots at 1440, 1024, 768 and 390 px wide, plus a short screen recording of: card click → replay, radar blip click → replay, nav through all 6 pages.
5. **Create a branch:** `feature/glass-ui-redesign`.

> ⚠️ **Observation to confirm (don't fix in logic):** In the screenshot, AT-104 shows HI 61 with an **amber** ring, but a **"critical"** badge and a **NO-GO** status. The visual layer should take colours from one field, defined in §7.3, so a card never shows mixed signals. If this mismatch comes from the data, raise it with the logic owner rather than patching it in the UI.

---

## 2. Phase 1 — Design Tokens

**Time: ~0.5 day** · New file: `src/styles/tokens.css` (or `tailwind.config` `theme.extend` if the project uses Tailwind)

```css
:root {
  /* — Surfaces — */
  --bg-0: #080D1A;                       /* app canvas */
  --bg-1: #0D1425;                       /* secondary / sidebar base */
  --glass-1: rgba(20, 30, 52, 0.72);     /* standard glass */
  --glass-2: rgba(30, 42, 68, 0.78);     /* elevated glass */
  --glass-inset: rgba(8, 13, 26, 0.45);  /* wells, chart backgrounds */

  /* — Borders — */
  --line-1: rgba(255, 255, 255, 0.06);
  --line-2: rgba(255, 255, 255, 0.10);
  --line-3: rgba(255, 255, 255, 0.16);   /* hover / focus */
  --highlight-top: inset 0 1px 0 rgba(255, 255, 255, 0.06);

  /* — Accents — */
  --accent: #38BDF8;        /* cyan  */
  --accent-2: #818CF8;      /* violet */
  --go: #2DD4A7;
  --caution: #FBBF24;
  --nogo: #FB647B;

  /* tinted variants for badges / fills */
  --go-a12: rgba(45, 212, 167, 0.12);
  --caution-a12: rgba(251, 191, 36, 0.12);
  --nogo-a12: rgba(251, 100, 123, 0.12);
  --accent-a12: rgba(56, 189, 248, 0.12);

  /* — Text — */
  --text-1: #F1F5F9;
  --text-2: #94A3B8;
  --text-3: #64748B;        /* tertiary: axis labels, meta */

  /* — Radius — */
  --r-sm: 8px;  --r-md: 12px;  --r-lg: 16px;  --r-xl: 20px;  --r-2xl: 24px;
  --r-pill: 999px;

  /* — Spacing (4px grid) — */
  --s-1: 4px; --s-2: 8px; --s-3: 12px; --s-4: 16px;
  --s-5: 20px; --s-6: 24px; --s-8: 32px; --s-10: 40px; --s-12: 48px;

  /* — Shadows — */
  --shadow-1: 0 1px 2px rgba(0,0,0,.30), 0 4px 16px rgba(0,0,0,.20);
  --shadow-2: 0 2px 4px rgba(0,0,0,.30), 0 12px 32px rgba(0,0,0,.28);
  --shadow-3: 0 4px 8px rgba(0,0,0,.35), 0 24px 56px rgba(0,0,0,.35);

  /* — Motion — */
  --ease-out: cubic-bezier(0.22, 1, 0.36, 1);
  --t-fast: 150ms;  --t-base: 240ms;  --t-slow: 600ms;

  /* — Type — */
  --font-sans: "Inter", ui-sans-serif, system-ui, sans-serif;
  --font-mono: "JetBrains Mono", ui-monospace, "SF Mono", Menlo, monospace;
}
```

**Typography scale**

| Token | Size / weight / tracking | Use |
|---|---|---|
| `display` | 44–56px / 650 / −0.03em | "Fleet Command" |
| `h2` | 20px / 600 / −0.01em | Section titles |
| `card-title` | 18px / 600 / −0.01em | Aircraft ID (AT-101) |
| `kpi` | 36–40px / 600 / −0.02em, `tabular-nums` | KPI numbers |
| `body` | 14–15px / 400 / 1.6 line-height | Descriptions |
| `label` | 11–12px / 500 / +0.08em, UPPERCASE | KPI labels, badges, meta |
| `mono` | 12–13px / 500, `tabular-nums` | UTC clock, T+ timestamps, flight duration |

> Use whatever font the project already loads. Adding Inter or JetBrains Mono is optional (self-hosted or Google Fonts). If neither is wanted, the system fallbacks above are fine.

---

## 3. Phase 1b — Glass Elevation System

New file: `src/styles/glass.css`. The panels must **not** all look the same. Five levels give depth:

| Level | Class | Used by | Background | Blur | Border | Radius | Shadow |
|---|---|---|---|---|---|---|---|
| **L0** Canvas | `body` | App background | `--bg-0` + ambient glows | — | — | — | — |
| **L1** Rail | `.glass-rail` | Sidebar | `rgba(13,20,37,0.82)` | 24px | right edge `--line-1` only | 0 | none |
| **L2** Stage | `.glass-stage` | Hero | `--glass-1` | 20px | `--line-2` + top highlight | `--r-2xl` | `--shadow-3` |
| **L3** Tile | `.glass-tile` | KPI cards | `rgba(20,30,52,0.55)` | 12px | `--line-1` | `--r-lg` | `--shadow-1` |
| **L4** Module | `.glass-module` | Aircraft cards | `--glass-2` | 16px | `--line-2` + status hairline | `--r-xl` | `--shadow-2` |
| Inset | `.glass-well` | Chart area, radar well | `--glass-inset` | none | `--line-1` | `--r-md` | inset only |

```css
.glass {
  position: relative;
  border: 1px solid var(--line-2);
  box-shadow: var(--highlight-top), var(--shadow-2);
  -webkit-backdrop-filter: blur(var(--blur, 16px)) saturate(140%);
          backdrop-filter: blur(var(--blur, 16px)) saturate(140%);
}
.glass-stage  { --blur: 20px; background: var(--glass-1); border-radius: var(--r-2xl); box-shadow: var(--highlight-top), var(--shadow-3); }
.glass-tile   { --blur: 12px; background: rgba(20,30,52,.55); border-color: var(--line-1); border-radius: var(--r-lg); box-shadow: var(--highlight-top), var(--shadow-1); }
.glass-module { --blur: 16px; background: var(--glass-2); border-radius: var(--r-xl); }

/* Fallback when backdrop-filter is unsupported or slow */
@supports not ((backdrop-filter: blur(1px)) or (-webkit-backdrop-filter: blur(1px))) {
  .glass { background: #121B30; }
}
```

### Ambient background (replaces the magenta/orange wash)

The current full-screen pink → orange → blue gradient is the biggest source of the "generic" look. Replace it with a dark canvas and **2–3 large, low-opacity light sources**, fixed so they don't scroll:

```css
body { background: var(--bg-0); color: var(--text-1); }
.app-ambient {
  position: fixed; inset: 0; z-index: -1; pointer-events: none;
  background:
    radial-gradient(900px 600px at 85% -10%, rgba(56,189,248,.10), transparent 60%),
    radial-gradient(800px 700px at 10% 110%, rgba(129,140,248,.09), transparent 60%),
    radial-gradient(600px 400px at 50% 40%, rgba(56,189,248,.03), transparent 70%);
}
/* Optional: faint 1px engineering grid, masked toward the edges */
.app-ambient::after {
  content: ""; position: absolute; inset: 0;
  background-image: linear-gradient(var(--line-1) 1px, transparent 1px),
                    linear-gradient(90deg, var(--line-1) 1px, transparent 1px);
  background-size: 48px 48px;
  mask-image: radial-gradient(ellipse at 60% 30%, #000 20%, transparent 75%);
  opacity: .35;
}
```

---

## 4. Phase 2 — Sidebar

**Time: ~0.5 day**

**Current problems:** heavy magenta surface, oversized logo tile, a gradient pill for the active item, and status text floating at the bottom.

**Target spec**
- Width **248px** on desktop, **72px** icon rail on laptop/tablet, drawer on mobile.
- Surface: `.glass-rail`, solid enough that it reads as structure rather than a floating card.
- **Brand block** (64px tall): 32px logo mark (keep the existing glyph, recolour it to a cyan→violet stroke or plain `--text-1`), "AeroTwin" at 15px/600 and "Engine Digital Twin" as a `label` in `--text-3`.
- **Section label:** `OPERATIONS` (`label` style) above the 6 nav items.
- **Nav item:** 40px tall, `--r-md`, icon 18px with stroke 1.75, text 14px/500 `--text-2`.
  - Hover: background `rgba(255,255,255,.04)`, text `--text-1`, 150ms.
  - **Active:** background `--accent-a12`, 1px border `rgba(56,189,248,.28)`, text `--text-1`, icon `--accent`, a 2px left indicator bar with `box-shadow: 0 0 12px rgba(56,189,248,.6)`. The indicator **slides** between items (`transform: translateY`) instead of jumping.
  - Focus-visible: 2px `--accent` outline, offset 2px.
- **Divider** (`--line-1`), then a **System Status block** pinned to the bottom:
  - `● Backend connected`: an 8px dot in `--go` with a soft pulse, bound to the existing health-check state (red `--nogo` when disconnected).
  - Description text at 12px `--text-3`.
  - Optional: show the model or twin version if it already exists in the data. Don't invent one.

**Files:** `Sidebar.*`, `NavItem.*`, route config (read only).

---

## 5. Phase 3 — Hero / Fleet Command

**Time: ~1 day**

**Layout:** `.glass-stage`, padding 40px, a two-column grid of `1fr | 340px` (the radar). The columns stack below 1024px.

**Left column, top to bottom**
1. **Status pill:** `● TWIN ONLINE` in `label` style, background `--go-a12`, border `rgba(45,212,167,.3)`, dot with a 2s pulse ring. Bound to the existing twin-online flag.
2. **Heading** "Fleet Command" in `display` style. Optionally a very subtle `--text-1 → #CBD5E1` text gradient. No neon glow.
3. **Description:** 15px `--text-2`, max-width 64ch.
4. **Telemetry strip**, a row of chips. Each chip is 32px tall, `--r-pill`, `--glass-inset` background, `--line-2` border:
   - `13:45:45 UTC`: mono, `--accent`, ticking every second (existing clock logic)
   - `● 3 CLEARED`: `--go` dot and text
   - `● 5 GROUNDED`: `--nogo` dot and text
   - `ENGINE · Rotax 912 S/ULS`: key in `--text-3`, value in `--text-1`

   Chips use a `label` prefix plus a value, so they read as instrument readouts rather than tags.

### Fleet radar (rebuild the visuals, keep the data and clicks)

Render it as **SVG** (likely already SVG). Keep the blip → replay click handler.

| Element | Spec |
|---|---|
| Container | `.glass-well`, circular, 300–320px |
| Range rings | 4 concentric rings, 1px `rgba(148,163,184,.12)`. Outer ring `.2` |
| Crosshair | 1px `rgba(148,163,184,.08)` plus small tick marks every 15° on the outer ring |
| Bearing labels | `000 / 090 / 180 / 270` at 9px mono `--text-3` |
| Sweep | conic-gradient wedge `rgba(56,189,248,.18) → transparent` over 40°, rotating in 6s linear. **Replaces the orange wedge** |
| Blips | 6px core in the status colour plus a 14px halo at 20% opacity. NO-GO blips get a slow 2.4s pulse ring |
| Blip labels | 10px mono `--text-2`, with a leader line if they overlap |
| Hover / focus | blip scales to 1.3, a tooltip shows `AT-104 · NO-GO · HI 61`, cursor pointer, keyboard-focusable (`tabindex=0`, `role=button`, `aria-label`) |
| Caption | under the radar: `FLEET RADAR · 8 CONTACTS` in `label` style |

> Blip positions must come from the same source as today. Only the drawing changes.

**Files:** `Hero.*`, `FleetRadar.*`, `StatusChip.*`.

---

## 6. Phase 4 — KPI Cards

**Time: ~0.5 day**

**Layout:** a 5-column grid with a 16px gap (responsive rules in §10).

**Card anatomy** (`.glass-tile`, padding 20px, min-height 132px):

```
┌──────────────────────────────┐
│ [icon 28px chip]   LABEL      │  ← 12px label, --text-2
│                                │
│ 58/60                          │  ← kpi number, status colour (or --text-1)
│ simulated test flights         │  ← 13px --text-3
│ 95% CI ≥ 88%                   │
└──────────────────────────────┘
```

| Card | Accent | Icon | Number colour |
|---|---|---|---|
| Total Aircraft | `--accent` | plane | `--text-1` |
| Go | `--go` | check-circle | `--go` |
| Caution | `--caution` | alert-triangle | `--caution` (at 0, use `--text-3` so it doesn't draw attention) |
| No-Go | `--nogo` | x-circle | `--nogo` |
| Faults Detected | `--accent-2` | target | `--text-1`, with the denominator `/60` in `--text-3` |

- **Icon chip:** 28px square, `--r-sm`, background is the accent at 12%, icon in the accent colour.
- **Top hairline:** a 1px gradient line along the top edge in the accent colour (`transparent → accent 50% → transparent`). This replaces the coloured wash inside each card.
- **Optional:** a thin 3px ratio bar at the bottom, e.g. Go 3/8 or Faults 58/60, computed from **existing** values only.
- **Count-up animation** on first load (600ms, `--ease-out`), using a small rAF helper with no library. Skip it when `prefers-reduced-motion` is set.

**Files:** `KpiCard.*`, `KpiGrid.*`.

---

## 7. Phase 5 — Aircraft Health Cards (priority section)

**Time: ~1.5–2 days**

### 7.1 Card anatomy

`.glass-module`, padding 20px, a vertical stack with a 16px gap:

```
┌─────────────────────────────────────────┐
│ AT-102                        [● NO-GO] │  header
│ Garuda 2 · ⏱ 59:59                       │  meta (mono duration)
├─────────────────────────────────────────┤
│  ╭───╮   HEALTH INDEX                    │
│  │ 3 │   critical  ▼                     │  ring + category
│  ╰───╯   (optional Δ if data exists)     │
├─────────────────────────────────────────┤
│  ▁▂▂▁▂▁▂▁▁▁▁                            │  trend (in .glass-well)
│  - - - - - - threshold - - - - - - -    │
├─────────────────────────────────────────┤
│ ◎ Cooling system degradation            │  fault
│   Alert at T+20:59                      │
├─────────────────────────────────────────┤
│ Open replay  →                           │  action (full-width footer)
└─────────────────────────────────────────┘
```

### 7.2 Component specs

| Part | Spec |
|---|---|
| **Header** | ID in `card-title`. Name and duration at 13px `--text-2`, duration in mono with a clock icon |
| **Status badge** | 24px tall, `--r-pill`, `label` style, status-tint background, 1px status border at 35%, a leading 6px dot. NO-GO dot pulses slowly |
| **Health ring** | SVG, 72px, stroke 6px, track `rgba(148,163,184,.12)`, arc in the status colour, round caps, a faint glow (`drop-shadow(0 0 6px statusColour@40%)`). Number centred at 22px/600 `tabular-nums`. Arc animates `stroke-dashoffset` from 0 to the value over 800ms on mount and on value change |
| **Category chip** | lower-case value from the data ("nominal", "critical"), status tint |
| **Trend chart** | 64–72px tall inside `.glass-well`. See §8 |
| **Fault row** | Healthy cards: `✓ All residuals within healthy bounds` in `--text-2`. Faulted cards: icon in the status colour, fault label at 14px/600 `--text-1`, alert time `T+20:59` in mono `--text-3` |
| **Action** | footer row with a `--line-1` top border. "Open replay →" at 13px/500 in `--accent`. The arrow moves 3px right on hover. The **whole card** stays clickable, as it is today |

### 7.3 State system (single source of truth)

Write one helper, e.g. `getStatusTheme(decision)`, that returns tokens. Every coloured part of the card reads from it, which keeps cards from showing mixed signals:

```js
// src/ui/statusTheme.js — presentation only; reads the existing decision field
export const STATUS_THEME = {
  GO:      { color: 'var(--go)',      tint: 'var(--go-a12)',      label: 'GO' },
  CAUTION: { color: 'var(--caution)', tint: 'var(--caution-a12)', label: 'CAUTION' },
  NOGO:    { color: 'var(--nogo)',    tint: 'var(--nogo-a12)',    label: 'NO-GO' },
};
export const getStatusTheme = (decision) =>
  STATUS_THEME[String(decision).toUpperCase().replace(/[^A-Z]/g, '')] ?? STATUS_THEME.CAUTION;
```

Apply it via a CSS custom property on the card root: `style={{ '--status': theme.color, '--status-tint': theme.tint }}`. All card CSS then uses `var(--status)`.

**Per-state treatment (subtle, no full-card gradients):**

| State | Border | Ambient | Extra |
|---|---|---|---|
| GO | `--line-2` | none | — |
| CAUTION | top 1px hairline in `--caution` | faint top-right radial `--caution` @ 6% | — |
| NO-GO | top 1px hairline in `--nogo` + left 2px bar | faint top-right radial `--nogo` @ 8% | badge dot pulse |

### 7.4 Interaction
- Hover: `translateY(-2px)`, border becomes `--line-3`, shadow goes from `--shadow-2` to `--shadow-3`, 240ms `--ease-out`.
- Focus-visible: 2px `--accent` ring. Enter or Space opens the replay (same handler as click).
- Selected aircraft, if selection state exists: 1px `--accent` border plus an accent glow.
- Pressed: `translateY(0) scale(.995)`.

### 7.5 Grid
`grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 20px;`, which gives 4 columns at 1440px. Cards stretch to equal height, with the footer pinned to the bottom (`margin-top: auto`).

Optional, only if trivial: a small toolbar above the grid with a filter (All / GO / NO-GO) and sort (ID / Health). It must use existing data client-side, and you can skip it to stay within scope.

**Files:** `AircraftCard.*`, `HealthRing.*`, `StatusBadge.*`, `TrendSparkline.*`, `statusTheme.js`.

---

## 8. Phase 6 — Charts & Visualizations

**Time: ~1 day**

Use the **existing chart library**. Change configuration and styling only, keeping data bindings, tooltips, zoom and brush.

| Property | Spec |
|---|---|
| Line | 1.75px stroke, `monotone` / `curveMonotoneX` smoothing, status colour |
| Area fill | vertical gradient: status colour 22% → 0% |
| Grid | horizontal only, 1px `rgba(148,163,184,.08)`, 3–4 lines max. No vertical grid on sparklines |
| Threshold line | dashed 1px `rgba(148,163,184,.35)`, `4 4` dash. Label it ("limit") on the large Twin Replay charts only |
| Axes | sparklines have none. Full charts: 11px mono `--text-3`, no axis line, ticks only |
| Last point | 3px dot in the status colour plus a 6px halo |
| Tooltip | `.glass-tile` style, 12px, mono values, colour swatch |
| Animation | draw-in over 600–800ms on mount. No re-animation on every data tick for live data |
| Sizing | wrap in a responsive container (`ResponsiveContainer` or ResizeObserver) |

**Shared chart theme:** create `src/ui/chartTheme.js` exporting colours, fonts and grid settings, then import it in every chart (fleet sparklines, Twin Replay, Fault Injection Lab, Model Validation) so they all match.

**Model Validation page** (confusion matrices, ROC, etc.): use the sequential cyan scale `#0D1425 → #38BDF8` for heatmaps. Keep categorical colours to accent, accent-2, go, caution and nogo.

---

## 9. Phase 7 — Motion & Micro-interactions

**Time: ~0.5 day** · CSS transitions and keyframes only, no animation library.

| Interaction | Implementation | Duration |
|---|---|---|
| Page transition | route outlet fades in plus `translateY(8px → 0)` | 240ms |
| Staggered entry | KPI and aircraft cards fade up with `animation-delay: calc(var(--i) * 40ms)` | 400ms |
| Nav indicator | sliding `transform` | 240ms |
| Card hover | lift + border + shadow | 240ms |
| Health ring | `stroke-dashoffset` transition | 800ms |
| Status change | badge and ring colours animate via `transition: color, background-color, border-color, stroke` | 300ms |
| Live pulse | twin-online dot and NO-GO badge dot, `@keyframes pulse` (scale and opacity of a ring) | 2–2.4s loop |
| Radar sweep | `rotate` keyframe | 6s linear loop |
| KPI count-up | rAF helper | 600ms |

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation-duration: .01ms !important; animation-iteration-count: 1 !important; transition-duration: .01ms !important; }
}
```

---

## 10. Phase 8 — Responsive Layout

**Time: ~0.5–1 day**

| Breakpoint | Sidebar | Hero | KPI grid | Aircraft grid |
|---|---|---|---|---|
| **≥1440** Desktop | 248px full | 2-col, radar 340px | 5 cols | 4 cols |
| **1200–1439** Laptop | 248px | 2-col, radar 280px | 5 cols (tighter padding) | 3 cols |
| **768–1199** Tablet | 72px icon rail, tooltips on hover | stacked, radar centred below the text at 260px | 3 + 2 (or 3 cols wrap) | 2 cols |
| **<768** Mobile | top bar + slide-in drawer (or bottom tab bar) | stacked, display size 32px, chips wrap, radar 220px | 2 cols, Total Aircraft full width; or horizontal scroll-snap row | 1 col |

Rules:
- Keep the hierarchy on small screens: status → KPIs → NO-GO aircraft. Don't hide data. Reflow it.
- Touch targets ≥ 44px. Radar blips get a larger invisible hit area on touch.
- Reduce blur to 8–10px on mobile for performance.
- Prefer `clamp()` for type: `font-size: clamp(32px, 4vw + 8px, 56px)`.

---

## 11. Rollout to Other Pages

Once the tokens and primitives exist, apply them to the other 5 routes with the same components. **Time: ~1–1.5 days**

| Page | Key treatment |
|---|---|
| Twin Replay | large charts on `.glass-stage`, playback controls as `.glass-tile` buttons, timeline scrubber in `--accent` |
| Fault Injection Lab | form controls (inputs, sliders, selects) restyled with the glass-inset background and accent focus ring. Inject buttons in `--caution` or `--nogo` tint |
| AI Copilot | chat bubbles: user in `--accent-a12`, assistant in `.glass-tile`. Input bar sticky at the bottom |
| Model Validation | metric tiles reuse `KpiCard`. Charts use `chartTheme` |
| How it Works | pipeline diagram (Physics twin → ML ensemble → Bayesian twin) as connected `.glass-tile` nodes with thin accent connectors |

Shared primitives to create or restyle: `Button` (primary / ghost / danger), `Input`, `Select`, `Tabs`, `Tooltip`, `Badge`, `Panel`.

---

## 12. Verification Checklist

### Functional (must all pass)
- [ ] All 6 nav routes load. The active indicator matches the route, including on refresh and deep link.
- [ ] Clicking any aircraft card opens the correct replay.
- [ ] "Open replay" link works, and so does keyboard Enter/Space on a focused card.
- [ ] Clicking each radar blip opens the correct replay.
- [ ] UTC clock ticks.
- [ ] KPI values match the API response (compare against the network tab).
- [ ] Each card's HI, category, decision, fault label and alert time match the API.
- [ ] Chart tooltips, hover and any zoom/brush still work.
- [ ] Backend disconnected → the status shows the disconnected state. (Test by stopping the backend.)
- [ ] Fault Injection Lab submits and shows its results as before.
- [ ] AI Copilot sends and receives messages.
- [ ] No new console errors or warnings. No changes in API calls (compare the network tab with the baseline).
- [ ] `git diff --stat` shows no changes in backend, API, model or prediction files.

### Visual / quality
- [ ] Text contrast ≥ 4.5:1 for body and ≥ 3:1 for large numbers, checked on the glass surfaces.
- [ ] Status is never conveyed by colour alone: badge text, icon shape and label always accompany it.
- [ ] The 4 breakpoints match §10. No horizontal scroll at 390px.
- [ ] `prefers-reduced-motion` turns off loops and count-ups.
- [ ] The backdrop-filter fallback looks acceptable in Firefox with blur disabled.
- [ ] Performance: Lighthouse score no worse than baseline. Scrolling stays at 60fps with 8+ cards (check DevTools → Rendering → FPS).
- [ ] Before/after screenshots captured and attached to the PR.

### Browsers
Chrome, Edge, Safari (macOS + iOS, needs the `-webkit-backdrop-filter` prefix), Firefox.

---

## 13. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| `backdrop-filter` cost with many cards | Blur only top-level surfaces, never nested elements. Reduce blur on mobile. Avoid animating blurred elements' size |
| Glass looks muddy over a busy background | Keep the ambient background low-contrast. Glass opacity ≥ 0.55 |
| Colour mismatch between ring, badge and status | Use the single `getStatusTheme` helper (§7.3) |
| Chart library limits styling | Override via the library's theme or props. If something is impossible, accept a near match rather than swapping libraries |
| Accidental logic change during refactor | Only change JSX structure and classNames. Keep props and handlers identical. Review the diff file by file |
| Font loading shifts layout | `font-display: swap`, or keep the existing font |

---

## 14. Suggested File Changes (React example)

```
src/
├─ styles/
│  ├─ tokens.css          NEW   design tokens
│  ├─ glass.css           NEW   elevation system + ambient bg
│  ├─ motion.css          NEW   keyframes, reduced-motion
│  └─ global.css          EDIT  import the above, remove old gradient bg
├─ ui/
│  ├─ statusTheme.js      NEW   presentation-only status → colour map
│  ├─ chartTheme.js       NEW   shared chart styling
│  └─ useCountUp.js       NEW   tiny rAF hook (no deps)
├─ components/
│  ├─ Sidebar/            EDIT  styles + sliding indicator
│  ├─ Hero/               EDIT  layout, chips
│  ├─ FleetRadar/         EDIT  SVG visuals only; keep click handlers
│  ├─ KpiCard/            EDIT
│  ├─ AircraftCard/       EDIT  new anatomy, same props
│  ├─ HealthRing/         EDIT/NEW
│  ├─ StatusBadge/        EDIT/NEW
│  └─ TrendSparkline/     EDIT  chart config only
└─ pages/*                EDIT  apply primitives (Phase 11)

NOT TOUCHED: api/, services/, models/, backend/, any prediction/twin logic
```

*If the project is plain HTML/CSS/JS, use the same structure with `styles/*.css` plus the matching JS modules, and keep the DOM IDs and event listeners unchanged.*

---

## 15. Timeline Summary

| Phase | Work | Est. |
|---|---|---|
| 0 | Discovery & baseline | 0.5 d |
| 1 | Tokens + glass system + background | 1 d |
| 2 | Sidebar | 0.5 d |
| 3 | Hero + radar | 1 d |
| 4 | KPI cards | 0.5 d |
| 5 | Aircraft health cards | 1.5–2 d |
| 6 | Charts | 1 d |
| 7 | Motion | 0.5 d |
| 8 | Responsive | 0.5–1 d |
| 11 | Other pages | 1–1.5 d |
| 12 | QA & fixes | 1 d |
| | **Total** | **≈ 9–11 working days** |

**Recommended commit order:** tokens → glass/background → sidebar → hero → KPI → aircraft cards → charts → motion → responsive → other pages → QA. Each step leaves the app working, so you can review screenshots and change direction after any of them.
