// AeroTwin mark: the three-blade propeller of a Rotax 912-class installation.
export default function Logo() {
  return (
    <svg viewBox="0 0 32 32" fill="currentColor" aria-hidden="true">
      {[0, 120, 240].map((a) => (
        <path key={a} transform={`rotate(${a} 16 16)`} d="M16 15C13.2 11.6 13.2 5.4 16.6 2.2 19.2 5.6 19.2 11.8 17.4 15.4Z" />
      ))}
      <circle cx="16" cy="16" r="3.4" />
    </svg>
  );
}
