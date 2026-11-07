// Fixed ambient canvas (plan §3): dark base, low-opacity light sources and a
// faint masked grid. On Twin Replay a faint light in the advisor's state colour
// fades in (TwinViewer sets <html data-sky>).
export default function Background() {
  return (
    <div className="app-ambient" aria-hidden="true">
      <div className="ambient-state ambient-go" />
      <div className="ambient-state ambient-caution" />
      <div className="ambient-state ambient-nogo" />
    </div>
  );
}
