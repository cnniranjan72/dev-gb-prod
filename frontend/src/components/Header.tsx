import type { ReactNode } from 'react'
import type { HealthResponse, SnapshotManifestResponse, CutoffDescriptor } from '../lib/api'
import { Card } from './ui'

export function Header({ health, children }: { health: HealthResponse | null; children?: ReactNode }) {
  return (
    <header className="border-b border-ink-800 bg-ink-900/60 backdrop-blur">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-3.5">
        <div className="flex items-center gap-3">
          <div className="grid size-9 place-items-center rounded-lg bg-wind-700/40 text-lg">🌪️</div>
          <div>
            <h1 className="text-[15px] leading-tight font-semibold text-ink-200">
              WindLens <span className="text-ink-400">· UK wind forecast intelligence</span>
            </h1>
            <p className="text-[11px] text-ink-400">
              Elexon BMRS · FUELHH actual wind vs WINDFOR forecast vintages · January 2026
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 text-[11px]">
          <Chip label="Data mode" value={health?.data_mode ?? '…'} tone="brand" />
          <Chip label="Actuals" value={health ? health.actual_rows.toLocaleString('en-GB') : '…'} />
          <Chip label="Forecast rows" value={health ? health.forecast_rows.toLocaleString('en-GB') : '…'} />
          {children}
        </div>
      </div>
    </header>
  )
}

function Chip({ label, value, tone = 'neutral' }: { label: string; value: string; tone?: 'neutral' | 'brand' }) {
  return (
    <span
      className={`rounded-full border px-2.5 py-1 ${
        tone === 'brand' ? 'border-wind-700/60 bg-wind-700/20 text-wind-300' : 'border-ink-700 bg-ink-850 text-ink-400'
      }`}
    >
      <span className="text-ink-400">{label}</span> <span className="font-medium">{value}</span>
    </span>
  )
}

export function ProvenanceCard({ manifest, health }: { manifest: SnapshotManifestResponse | null; health: HealthResponse | null }) {
  if (!manifest) return null
  const range = manifest.period?.publication_window_utc
  return (
    <Card title="Data provenance" subtitle="Every number in this dashboard is traceable" className="h-full">
      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-2 text-xs">
        <dt className="text-ink-400">Snapshot mode</dt>
        <dd className="text-ink-200">{health?.data_mode === 'snapshot' ? 'Snapshot (reproducible)' : health?.data_mode}</dd>
        <dt className="text-ink-400">Retrieved</dt>
        <dd className="text-ink-200">{manifest.retrieved_at_utc?.slice(0, 10) ?? '—'}</dd>
        <dt className="text-ink-400">Delivery month</dt>
        <dd className="text-ink-200 font-mono">
          {manifest.period?.settlement_from} → {manifest.period?.settlement_to}
        </dd>
        {range && range.length === 2 && (
          <>
            <dt className="text-ink-400">Publication window</dt>
            <dd className="font-mono text-[10.5px] break-all text-ink-400">{range[0]} → {range[1]}</dd>
          </>
        )}
      </dl>
      <p className="mt-3 rounded-lg bg-ink-850 px-3 py-2 text-[11.5px] leading-relaxed text-ink-400">
        <span className="font-semibold text-actual-400">Transparency note:</span> WINDFOR is the system-operator forecast
        (national view, includes embedded wind) while FUELHH shows settlement-visible BM wind — in Jan-2026 backfills the
        forecast view ran ≈ +16% above settlement actuals. WindLens reports both datasets {' '}<em>as-published</em>, with
        no rescaling, and the hourly forecast is applied to both half-hours of its hour (hour-ending alignment).
      </p>
    </Card>
  )
}

export function CutoffBar({ cutoff }: { cutoff: CutoffDescriptor | null }) {
  if (!cutoff) return null
  return (
    <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[11.5px] text-ink-400">
      <span className="rounded bg-ink-850 px-2 py-1">
        Decision cutoff:{' '}
        <span className="text-ink-200 font-mono">
          {cutoff.mode === 'custom' ? 'custom' : cutoff.preset}
        </span>
      </span>
      <span className="font-mono text-ink-200">{formatIsoZ(cutoff.cutoff_utc)} UTC</span>
      <span>({londonClock(cutoff.cutoff_london)} London D−1)</span>
    </div>
  )
}

function formatIsoZ(iso: string): string {
  return iso.replace('+00:00', 'Z')
}

function londonClock(iso: string): string {
  return iso.slice(11, 16)
}
