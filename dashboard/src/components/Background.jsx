// Fixed colour field behind the glass: four temper-coloured blobs on slow,
// transform-only drift, plus one layer per advisor decision. TwinViewer sets
// <html data-sky="GO|CAUTION|NO-GO"> and the matching layer fades in, so the
// glass itself changes colour with the engine's state.
export default function Background() {
  return (
    <div className="bg-fx" aria-hidden="true">
      <div className="bg-blob b1" />
      <div className="bg-blob b2" />
      <div className="bg-blob b3" />
      <div className="bg-blob b4" />
      <div className="bg-sky sky-go" />
      <div className="bg-sky sky-caution" />
      <div className="bg-sky sky-nogo" />
      <div className="bg-grain" />
    </div>
  );
}
