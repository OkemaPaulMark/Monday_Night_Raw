export function ErrorBanner({ message }) {
  if (!message) return null
  return <div className="error-banner">{message}</div>
}

export function LoadingState({ label = 'Loading…' }) {
  return <p className="text-[var(--color-muted)] py-6">{label}</p>
}

export function StatTile({ label, value }) {
  return (
    <div className="stat-tile">
      <div className="value">{value ?? '—'}</div>
      <div className="label">{label}</div>
    </div>
  )
}

export function SectionTitle({ children, action }) {
  return (
    <div className="mb-3 flex items-center justify-between gap-3">
      <h2 className="display text-3xl leading-none">{children}</h2>
      {action}
    </div>
  )
}

export function EmptyState({ children }) {
  return <p className="text-[var(--color-muted)] text-sm py-4">{children}</p>
}
