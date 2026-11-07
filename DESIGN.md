# AeroTwin design system: Glassmorphism 2.0 in ice silver, deep aubergine and marigold

Source of truth for the dashboard's look, built from `AeroTwin_Glassmorphism_Implementation_Plan.md`.
- Tokens: `dashboard/src/styles/tokens.css`
- Glass levels and the ambient canvas: `glass.css`
- Motion: `motion.css`
- Everything else: `dashboard/src/index.css`

## Palette
| Role | Token | Value |
|---|---|---|
| Deep aubergine canvas | `--bg-0`, `--bg-1` | `#170A1F`, `#22102E`; plum and marigold light sources behind the glass |
| Frosted aubergine glass | `--glass-1`, `--glass-2`, `--glass-tile` | 34-44% alpha aubergine, plus the ice-silver `--sheen` |
| Ice silver | `--accent-2`, `--line-*`, text | `#D6E0EA` details; edges `rgba(226,234,242,.10/.18/.30)`; text `#F4F6F9`, `#D2CCDA`, `#C0B8CC` |
| Marigold | `--accent` | `#F6A623`: primary action, active nav, links, scrubber, radar sweep, single-series data |
| State | `--go`, `--caution`, `--nogo` | `#2DD4A7`, `#FACC15`, `#FF8FA0` |

- Caution is a clear yellow so it is never mistaken for the marigold accent.
- NO-GO and tertiary text were lightened until they measured 4.5:1 or better on the brightest glass. The worst case is NO-GO at 4.63:1.

## Surfaces
| Level | Class | Used by |
|---|---|---|
| L0 canvas | `body` + `.app-ambient` | dark `--bg-0`, two faint light sources, masked 48px grid |
| L1 rail | `.glass-rail` | sidebar |
| L2 stage | `.glass-stage` | Fleet hero, the large Twin Replay charts, boot card |
| L3 tile | `.glass-tile` (also `.panel.kpi`) | KPI cards |
| L4 module | `.glass-module`, `.panel` | aircraft cards, page panels |
| Inset | `.glass-well` | sparklines, radar scope, inner wells. Never blurs |

- Only top-level surfaces blur.
- Never put `opacity`, `filter` or `mask` on an ancestor of a glass surface, because it switches the blur off. Animate the surface itself.

## Status colour
`ui/statusTheme.js` maps the `decision` field to `--status` and `--status-tint`. The ring, badge, chip, hairline, sparkline and glow on an aircraft card all read from it. GO, CAUTION and NO-GO are the only state colours (`--go`, `--caution`, `--nogo`) and always appear with a text label.

## Deviations from the plan, with reasons
- **The palette replaces the plan's navy, cyan and violet**, at the owner's request.
- **Chart series keep the validated palettes in `util.js`** instead of reusing go, caution and nogo. Status colours stay reserved for state. Re-run the dataviz validator against surface `#2e1a3c` after any change. The model and fault sets have a CVD dE of 7.1, so their charts must keep legends.
- **The aircraft grid uses explicit 4/3/2/1 breakpoints.** The plan's `minmax(300px, 1fr)` gives only 3 columns at 1440px.
- **The page entrance is transform-only on the route outlet.** Each surface fades in itself, so the blur never drops out.
- **Phone navigation is a bottom tab bar**, one of the plan's two options.
- **Fonts are the faces the project already self-hosts** (Onest, Bricolage Grotesque, JetBrains Mono), as plan §2 allows.
- **A faint state light behind the glass on Twin Replay** (`html[data-sky]`) was kept from the previous design.

## Charts
Shared values are in `ui/chartTheme.js`. Global Recharts overrides in `index.css` give every chart horizontal grid lines only, no axis lines and mono 11px ticks. Heatmaps use the sequential aubergine-to-marigold scale `heatScale()`. Misdiagnoses in the confusion matrix also carry a NO-GO outline.

## Motion
- Ease: `--ease-out`.
- Durations: `--t-fast` 150 ms, `--t-base` 240 ms, `--t-slow` 600 ms.
- Entrances: cards fade up with a 40 ms stagger.
- Nav: the indicator slides between items.
- Loops: radar sweep 6 s; pulses only on live status and NO-GO.
- `prefers-reduced-motion` stops loops and count-ups.

## Simple and Detailed views
- A **Simple / Detailed** switch sits at the top of every page (`ui/viewMode.jsx`, state in `ui/viewContext.js`). Simple is the default, and the choice is remembered per browser.
- **Simple** is for beginners:
  - plain page names and instructions, and plain wording for the replay's sensors, events and toasts
  - a "how to read this page" guide on the Fleet page
  - a 4-step story and a glossary on How it works
  - four plain results, one chart and an honest-limits box on the accuracy page
- Advisor reasons and fault names are translated by `ui/plain.js`, which keys off the exact backend strings. Anything it doesn't recognise is shown unchanged.
- **Detailed** shows the full engineering dashboard, unchanged.
- Rule: Simple view may hide detail, but never changes a number or hides a limitation. The "simulated data" caveat and the real-flight result (AUC 0.51) appear in both views.
