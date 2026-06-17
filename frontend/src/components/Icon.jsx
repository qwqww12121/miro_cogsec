const PATHS = {
  shield: (
    <path
      d="M12 3l8 3v6c0 4.5-3.2 8.4-8 9-4.8-.6-8-4.5-8-9V6l8-3z"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  ),
  wave: (
    <path
      d="M3 12c2.5-3 4.5-3 7 0s4.5 3 7 0M3 7c2.5-3 4.5-3 7 0s4.5 3 7 0M3 17c2.5-3 4.5-3 7 0s4.5 3 7 0"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  ),
  network: (
    <g strokeLinecap="round" strokeLinejoin="round">
      <circle cx="6" cy="6" r="2.4" />
      <circle cx="18" cy="6" r="2.4" />
      <circle cx="6" cy="18" r="2.4" />
      <circle cx="18" cy="18" r="2.4" />
      <circle cx="12" cy="12" r="2.4" />
      <path d="M7.6 7.6L10.4 10.4M16.4 7.6L13.6 10.4M7.6 16.4L10.4 13.6M16.4 16.4L13.6 13.6" />
    </g>
  ),
  'arrow-right': (
    <path d="M5 12h14M13 6l6 6-6 6" strokeLinecap="round" strokeLinejoin="round" />
  ),
  spark: (
    <path
      d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5L18 18M6 18l2.5-2.5M15.5 8.5L18 6"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  ),
  chart: (
    <path d="M3 20h18M6 16V9M11 16V5M16 16v-7M21 16v-3" strokeLinecap="round" strokeLinejoin="round" />
  ),
  alert: (
    <g strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 9v4M12 17h.01" />
      <path d="M10.3 4.3L2.7 17.1A2 2 0 0 0 4.4 20h15.2a2 2 0 0 0 1.7-2.9L13.7 4.3a2 2 0 0 0-3.4 0z" />
    </g>
  ),
  check: <path d="M5 12.5L10 17.5L19 7.5" strokeLinecap="round" strokeLinejoin="round" />,
}

export default function Icon({ name, className = 'w-5 h-5' }) {
  const inner = PATHS[name]
  if (!inner) return null
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      className={className}
    >
      {inner}
    </svg>
  )
}
