import type { ReactNode } from 'react'

export function Card({
  title,
  subtitle,
  accent,
  children,
  className = '',
}: {
  title?: string
  subtitle?: string
  accent?: string
  children: ReactNode
  className?: string
}) {
  return (
    <section
      className={`rounded-xl border border-ink-800 bg-ink-900/80 shadow-lg shadow-black/30 ${className}`}
    >
      {(title || accent) && (
        <header className="flex items-baseline justify-between gap-2 border-b border-ink-800 px-4 pt-3.5 pb-3">
          <div>
            {title && <h2 className="text-sm font-semibold tracking-wide text-ink-200">{title}</h2>}
            {subtitle && <p className="mt-0.5 text-[11px] leading-snug text-ink-400">{subtitle}</p>}
          </div>
          {accent && <span className="text-[11px] text-ink-400">{accent}</span>}
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  )
}

export function StatCard({
  label,
  value,
  hint,
  tone = 'neutral',
}: {
  label: string
  value: string
  hint?: string
  tone?: 'neutral' | 'positive' | 'negative' | 'brand'
}) {
  const toneClass = {
    neutral: 'text-ink-200',
    brand: 'text-wind-300',
    positive: 'text-actual-400',
    negative: 'text-underrose-400',
  }[tone]
  return (
    <div className="rounded-xl border border-ink-800 bg-ink-900/80 px-4 py-3 shadow-lg shadow-black/30">
      <p className="text-[11px] font-medium tracking-wide text-ink-400 uppercase">{label}</p>
      <p className={`mt-1 text-2xl leading-none font-semibold tabular-nums ${toneClass}`}>{value}</p>
      {hint && <p className="mt-1.5 text-[11px] text-ink-400">{hint}</p>}
    </div>
  )
}

export function Loading({ label = 'Loading' }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-3 py-14 text-sm text-ink-400">
      <span className="inline-block size-4 animate-spin rounded-full border-2 border-ink-700 border-t-wind-300" />
      {label}…
    </div>
  )
}

export function ErrorNote({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-start gap-2 rounded-lg border border-underrose-400/40 bg-underrose-400/10 px-4 py-3 text-sm text-underrose-400">
      <span>{message}</span>
      {onRetry && (
        <button
          onClick={onRetry}
          className="rounded-md border border-underrose-400/40 px-2 py-1 text-xs hover:bg-underrose-400/20"
        >
          Retry
        </button>
      )}
    </div>
  )
}
