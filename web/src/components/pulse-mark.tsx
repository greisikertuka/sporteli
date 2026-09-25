export function PulseMark({ className = "" }: { className?: string }) {
  return (
    <span className={`pulse-mark ${className}`} aria-hidden="true">
      <svg viewBox="0 0 36 36" fill="none">
        <path
          d="M9 24V12h5V8h8v4h5v12M14 12v5m8-5v5M9 12V9m18 3V9M6 28h24"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <path
          className="pulse-trace"
          d="M7 22h7l2-4 4 8 2-4h7"
          stroke="currentColor"
          strokeWidth="1.7"
          strokeLinecap="round"
          strokeLinejoin="round"
          pathLength="1"
        />
      </svg>
    </span>
  );
}
