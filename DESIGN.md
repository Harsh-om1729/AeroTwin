# AeroTwin design system: "Temper"

The dashboard's visual world. Tokens live at the top of `dashboard/src/index.css`.

**Idea.** The oxide colours heat leaves on an exhaust pipe (magenta, cobalt, amber, teal) on a deep plum ground.
Panels are real glass over that colour, and the colour reacts to the engine.

**Signature move.** `TwinViewer` sets `<html data-sky="GO|CAUTION|NO-GO">` from the advisor's decision. A matching
`.bg-sky` layer fades in over 900 ms, so the glass tints teal, amber or red. `Background.jsx` holds the layers.

## Colour jobs
- **Brand** (`--magenta`, `--ember`, `--brand`): primary action, logo, active nav, range fill.
- **State** (`--ok`, `--warn`, `--crit`): meaning only, never decoration. Always paired with a word or icon.
- **Data series** (`util.js`): OKLCH L 0.48-0.67, validated on surface `#241650`. Re-run the dataviz validator after
  any change. The fault set's closest pair is CVD dE 6.6, so fault charts must keep their labels.
- **Text**: `--text`, `--text-2`, `--text-3`. Worst measured contrast on glass is 4.7:1 over the brightest backdrop.
  Re-measure rendered pixels if glass opacity or blob colours change.

## Glass rules
- Only `.panel`, `.sidebar`, `.boot-card`, `.toast` and `.tt` blur. Inner surfaces use `--well`, a flat tint.
- Never animate `opacity`, or set `filter`/`mask`, on an ancestor of a glass panel: it breaks the blur. Animate the
  panel itself (`.page-anim .panel`).
- `--lit` tints a panel from behind (`.fleet-card.crit`, `.flagship`, KPI tiles).
- Fallbacks exist for `prefers-reduced-transparency` and for browsers without `backdrop-filter`.

## Type
Bricolage Grotesque (display, big figures), Onest (UI), JetBrains Mono (measurements only). All self-hosted through
`@fontsource-variable`, so the demo needs no internet. Sentence case, no tracked uppercase labels.

## Motion
Tokens: `--ease-out`, `--ease-in-out`, `--ease-drawer`. Use transform and opacity only.
- Chart data never animates. Hover motion is gated to pointer devices.
- Panels enter in 340 ms with a stagger capped at 245 ms. The nav indicator slides in 320 ms.
- Loops are reserved for state: NO-GO breathing, the replay chip, the radar, backend status. Plus the slow backdrop drift.
- `prefers-reduced-motion` removes travel and keeps the state colour changes.
