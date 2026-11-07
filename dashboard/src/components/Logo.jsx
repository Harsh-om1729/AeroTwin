import { useId } from 'react';

// AeroTwin mark: the three-blade propeller of a Rotax 912-class installation,
// filled with a cyan-to-violet gradient.
export default function Logo() {
  const id = useId();
  return (
    <svg viewBox="0 0 32 32" aria-hidden="true">
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#f6a623" />
          <stop offset="1" stopColor="#d6e0ea" />
        </linearGradient>
      </defs>
      <g fill={`url(#${id})`}>
        {[0, 120, 240].map((a) => (
          <path key={a} transform={`rotate(${a} 16 16)`} d="M16 15C13.2 11.6 13.2 5.4 16.6 2.2 19.2 5.6 19.2 11.8 17.4 15.4Z" />
        ))}
        <circle cx="16" cy="16" r="3.4" />
      </g>
    </svg>
  );
}
