import { getStatusTheme, statusVars } from '../ui/statusTheme';

export default function StatusBadge({ decision }) {
  const th = getStatusTheme(decision);
  return (
    <span className="badge status-badge" style={statusVars(th)}>
      <span className={`dot ${th.key === 'NOGO' ? 'pulse' : ''}`} />{th.label}
    </span>
  );
}
