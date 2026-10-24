import type { VintagesResponse } from '../lib/api'
import { formatMw, periodRange } from '../lib/format'
import { Card, ErrorNote, Loading } from './ui'
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

export function HourBars({ byHour, onPick }: {
  byHour: { london_hour: number; count: number; mae_mw: number | null }[]
  onPick: (hour: number) => void
}) {
  if (!byHour.length) return null
  return (
    <Card
      title="Accuracy by hour of day (London)"
      subtitle="Click a bar to explore that hour's settlement periods."
      accent={`${byHour.reduce((a, r) => a + r.count, 0).toLocaleString('en-GB')} half-hours`}
    >
      <div className="h-52">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={byHour}
            margin={{ top: 8, right: 8, bottom: 0, left: 4 }}
            onClick={(state: unknown) => {
              const idx = (state as { activeTooltipIndex?: number | string })?.activeTooltipIndex
              if (idx !== null && idx !== undefined) onPick(Number(byHour[Number(idx)]?.london_hour ?? Number(idx)))
            }}
          >
            <CartesianGrid stroke="oklch(0.3 0.03 260)" strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="london_hour" tick={{ fill: 'oklch(0.6 0.02 260)', fontSize: 9 }} tickLine={false} tickFormatter={(h: number) => `${String(h).padStart(2, '0')}`} interval={1} />
            <YAxis tick={{ fill: 'oklch(0.6 0.02 260)', fontSize: 10 }} tickLine={false} tickFormatter={(v: number) => `${(Number(v) / 1000).toFixed(0)}k`} />
            <Tooltip
              cursor={{ fill: 'oklch(0.3 0.03 260 / 0.25)' }}
              contentStyle={{ background: 'oklch(0.18 0.03 260)', border: '1px solid oklch(0.34 0.03 260)', borderRadius: 8, fontSize: 12 }}
              formatter={(value) => [`${Number(value).toLocaleString('en-GB', { maximumFractionDigits: 1 })} MW`, 'Hour MAE'] as [string, string]}
              labelFormatter={(h) => `${String(Number(h)).padStart(2, '0')}:00–${String(Number(h) + 1).padStart(2, '0')}:00 London`}
            />
            <Bar dataKey="mae_mw" fill="oklch(0.5 0.13 190)" radius={[3, 3, 0, 0]} className="cursor-pointer" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Card>
  )
}

export function VintageExplorer({
  selection,
  period,
  onPeriodChange,
  loading,
  error,
}: {
  selection: VintagesResponse | null
  period: number
  onPeriodChange: (period: number) => void
  loading: boolean
  error: string | null
}) {
  if (error) return <Card title="Historical vintage explorer"><ErrorNote message={error} /></Card>
  if (loading) return <Card title="Historical vintage explorer"><Loading /></Card>
  if (!selection) return null
  const vintages = [...selection.vintages].reverse() // newest published first

  return (
    <Card
      title="Historical vintage explorer"
      subtitle="Every WINDFOR publication for the chosen half-hour — the shading shows what a trader could have known at cutoff."
      accent={`Period ${selection.settlement_period} · ${periodRange(selection.settlement_period)} · ${selection.settlement_date}`}
    >
      <div className="flex flex-wrap items-center gap-3">
        <label className="text-xs text-ink-400">
          Settlement period
          <input
            type="range"
            min={1}
            max={48}
            value={period}
            onChange={(e) => onPeriodChange(Number(e.target.value))}
            className="ml-3 w-56 accent-wind-500 align-middle"
          />
          <span className="ml-2 w-28 font-mono text-ink-200">{String(period).padStart(2, '0')} · {periodRange(period)}</span>
        </label>
        <div className="text-[11px] text-ink-400">
          cutoff <span className="font-mono text-ink-200">{selection.cutoff.cutoff_utc}</span>
          {selection.cutoff.preset && <span className="ml-1">({selection.cutoff.preset})</span>}
        </div>
      </div>

      <div className="mt-3 grid gap-3 md:grid-cols-[auto_1fr]">
        <div className="min-w-[280px]">
          <div className="text-center">
            <p className="text-[11px] tracking-wide text-ink-400 uppercase">Selected vintage</p>
            <p className="mt-1 text-3xl font-semibold tabular-nums text-wind-300">
              {selection.selected_forecast_mw === null ? 'Unavailable' : formatMw(selection.selected_forecast_mw)}
            </p>
            <p className="mt-0.5 text-[11px] text-ink-400">
              {selection.available
                ? `latest publication at/before the cutoff`
                : `no forecast existed historically at this cutoff — displayed as missing, never substituted`}
            </p>
          </div>
        </div>
        <div className="max-h-72 overflow-y-auto rounded-lg border border-ink-800">
          <table className="w-full text-[11.5px]">
            <thead className="sticky top-0 bg-ink-850 text-ink-400">
              <tr>
                <th className="px-3 py-1.5 text-left font-medium">Published (UTC)</th>
                <th className="px-3 py-1.5 text-right font-medium">Forecast MW</th>
                <th className="px-3 py-1.5 text-right font-medium">Lead</th>
                <th className="px-3 py-1.5 text-right font-medium">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-800/60">
              {vintages.map((v) => (
                <tr
                  key={v.publish_time_utc}
                  className={v.selected ? 'bg-wind-700/25' : v.eligible ? '' : 'bg-underrose-400/10'}
                >
                  <td className="px-3 py-1.5 font-mono">{v.publish_time_utc.replace('T', ' ').replace('Z', '')}</td>
                  <td className="px-3 py-1.5 text-right tabular-nums">{v.forecast_mw === null ? '—' : v.forecast_mw.toLocaleString('en-GB')}</td>
                  <td className={`px-3 py-1.5 text-right tabular-nums ${v.lead_hours >= 0 ? '' : 'text-ink-400'}`}>
                    {v.lead_hours >= 0 ? v.lead_hours.toFixed(1) : '—'} h
                  </td>
                  <td className="px-3 py-1.5 text-right">
                    {v.selected ? (
                      <span className="rounded-full bg-wind-500/30 px-2 py-0.5 font-medium text-wind-300">selected</span>
                    ) : v.eligible ? (
                      <span className="text-ink-400">known at cutoff</span>
                    ) : (
                      <span className="font-medium text-underrose-400">after cutoff (excluded)</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      <p className="mt-2 text-[11px] text-ink-400">
        Rule: winner = latest publication at/before the decision cutoff. Negative leads mean the vintage was published
        <em> after</em> delivery already began (same-day updates) and are only eligible for later cutoffs.
      </p>
    </Card>
  )
}
