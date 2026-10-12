/** The teardrop pin glyph used for both the map's start/end markers
 * (StartEndMarkers.tsx) and the "finding routes" loading animation
 * (PlanningProgress.tsx) — same shape and colour language (A = ink,
 * B = accent) so a viewer already recognises it by the time the real map
 * markers show up. */
export function RoutePin({
  label,
  fill,
  ink,
  title,
  size = 30,
}: {
  label: string;
  fill: string;
  ink: string;
  title: string;
  size?: number;
}) {
  return (
    <div title={title} className="flex flex-col items-center">
      <svg width={size} height={(size * 38) / 30} viewBox="0 0 24 32" aria-label={title}>
        <path
          d="M12 1C6.48 1 2 5.48 2 11c0 7 9 19 9.3 19.4a0.9 0.9 0 0 0 1.4 0C13 30 22 18 22 11c0-5.52-4.48-10-10-10z"
          fill={fill}
          stroke="var(--surface)"
          strokeWidth="1.5"
        />
        <circle cx="12" cy="11" r="6.5" fill={fill} stroke="var(--surface)" strokeWidth="1" />
        <text x="12" y="14.5" textAnchor="middle" fontSize="9" fontWeight="700" fill={ink}>
          {label}
        </text>
      </svg>
    </div>
  );
}
