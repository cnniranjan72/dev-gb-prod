import type { SeriesResponse } from '../lib/api'
import { londonTimeLabel, signed } from '../lib/format'
import { Card, ErrorNote, Loading } from './ui'
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

export function ForecastChart({ series, loading, error, onRetry }: {
  series: SeriesResponse | null
  loading: boolean
  error: string | null
  onRetry: () => void
}) {
  if (loading) return <Card title="Day-ahead view"><Loading /></Card>
  if (error) return <Card title="Day-ahead view"><ErrorNote message={error} onRetry={onRetry} /></Card>
  if (!series) return null

  const data = series.points.map((p) => ({
    time: londonTimeLabel(p.interval_start_london),
    period: p.settlement_period,
    actual: p.actual_mw,
    forecast: p.forecast_mw,
    error: p.error_mw,
    publish: p.forecast_publish_time_utc,
  }))

  const allValues = data.flatMap((d) => [d.actual, d.forecast]).filter((v): v is number => v !== null)
  const domainMin = allValues.length ? Math.floor(Math.min(...allValues) * 1.05) : 0
  const domainMax = allValues.length ? Math.ceil(Math.max(...allValues) * 1.05) : 1

  return (
    <Card
      title="Actual vs selected day-ahead forecast (MW)"
      subtitle="Forecast = vintage published on/before the decision cutoff D−1; hourly MW spans both half-hours of its hour."
      accent={`Delivery ${series.delivery_date} · London local time`}
    >
      <div className="h-80">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 4 }}>
            <defs>
              <linearGradient id="actualFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="oklch(0.62 0.15 220)" stopOpacity={0.35} />
                <stop offset="100%" stopColor="oklch(0.62 0.15 220)" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="oklch(0.3 0.03 260)" strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="time" tick={{ fill: 'oklch(0.6 0.02 260)', fontSize: 10 }} tickLine={false} interval={5} />
            <YAxis
              tick={{ fill: 'oklch(0.6 0.02 260)', fontSize: 10 }}
              tickLine={false}
              domain={[domainMin, domainMax]}
              tickFormatter={(v: number) => `${(v / 1000).toFixed(0)}k`}
            />
            <Tooltip
              contentStyle={{ background: 'oklch(0.18 0.03 260)', border: '1px solid oklch(0.34 0.03 260)', borderRadius: 8, fontSize: 12 }}
              labelStyle={{ color: 'oklch(0.82 0.02 260)' }}
              formatter={(value, name) => {
                if (value === null || value === undefined) return ['—', String(name)]
                return [
                  `${Number(value).toLocaleString('en-GB')} MW${
                    name === 'error' && Number(value) !== 0 ? ` (${signed(Number(value))})` : ''
                  }`,
                  name === 'actual' ? 'Actual (FUELHH)' : name === 'forecast' ? 'Selected WINDFOR vintage' : 'Error (forecast − actual)',
                ] as [string, string]
              }}
              labelFormatter={(label) => `London ${label}`}
            />
            <Legend
              formatter={(value: string) => {
                const legendLabel: Record<string, string> = {
                  actual: 'Actual (FUELHH)',
                  forecast: 'Selected WINDFOR vintage',
                  error: 'Error (forecast − actual)',
                }
                return <span style={{ color: 'oklch(0.6 0.02 260)' }}>{legendLabel[value] ?? value}</span>
              }}
            />
            <ReferenceLine y={0} stroke="oklch(0.45 0.03 260)" />
            <Area type="linear" dataKey="actual" stroke="oklch(0.78 0.14 160)" strokeWidth={2} fill="url(#actualFill)" connectNulls={false} dot={false} name="actual" />
            <Line type="linear" dataKey="forecast" stroke="oklch(0.8 0.13 210)" strokeWidth={2} strokeDasharray="6 4" connectNulls={false} dot={false} name="forecast" />
            <Line type="linear" dataKey="error" stroke="oklch(0.7 0.15 300)" strokeWidth={1} strokeDasharray="2 3" connectNulls={false} dot={false} name="error" />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-2 text-[11px] text-ink-400">
        Gaps in the actual line mean the half-hour had no value in FUELHH — shown as missing, never as zero.
        Dotted purple: signed error <span className="font-mono">forecast − actual</span> (positive ⇒ over-forecast).
      </p>
    </Card>
  )
}
