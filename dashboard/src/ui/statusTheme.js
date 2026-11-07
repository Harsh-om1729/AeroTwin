// Presentation only: maps the existing `decision` field to colour tokens, so a
// card's ring, badge, chip, hairline and glow always agree (plan §7.3).
export const STATUS_THEME = {
  GO: { key: 'GO', color: 'var(--go)', tint: 'var(--go-a12)', label: 'GO' },
  CAUTION: { key: 'CAUTION', color: 'var(--caution)', tint: 'var(--caution-a12)', label: 'CAUTION' },
  NOGO: { key: 'NOGO', color: 'var(--nogo)', tint: 'var(--nogo-a12)', label: 'NO-GO' },
};

export const getStatusTheme = (decision) =>
  STATUS_THEME[String(decision).toUpperCase().replace(/[^A-Z]/g, '')] ?? STATUS_THEME.CAUTION;

export const statusVars = (theme) => ({ '--status': theme.color, '--status-tint': theme.tint });
