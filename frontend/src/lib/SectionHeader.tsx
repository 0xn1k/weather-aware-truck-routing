export function SectionHeader({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-3">
      <h2
        className="m-0 whitespace-nowrap text-[12.5px] font-semibold uppercase tracking-[0.14em]"
        style={{ color: "var(--muted)" }}
      >
        {children}
      </h2>
      <span aria-hidden="true" className="h-px flex-1" style={{ background: "var(--line)" }} />
    </div>
  );
}
