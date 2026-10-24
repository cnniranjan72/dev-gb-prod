import type { AccuracyResponse, SummaryResponse } from '../lib/api'
import { formatMw, signed } from '../lib/format'
import { Card, ErrorNote, Loading, StatCard } from './ui'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

const OVER = 'oklch(0.7 0.15 300)'
const UNDER = 'oklch(0.68 0.17 20)'

export function SummaryCards({ summary }: { summary: SummaryResponse | null }) {
  if (!summary) return null
  const m = summary.metrics
  const c = summary.coverage
  const biasTone = m.mean_bias_mw === null ? 'neutral' : m.mean_bias_mw >= 0 ? 'negative' : 'positive'
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <StatCard
        label="MAE"
        value={m.mae_mw === null ? '—' : formatMw(m.mae_mw, 1)}
        hint={`${c.valid_pairs}/${c.expected_intervals} half-hour pairs`}
        tone="brand"
      />
      <StatCard label="RMSE" value={m.rmse_mw === null ? '—' : formatMw(m.rmse_mw, 1)} hint="quadratic penalty" />
      <StatCard
        label="Mean bias"
        value={signed(m.mean_bias_mw === null ? undefined : m.mean_bias_mw)}
        hint="forecast − actual (positive = over-forecast)"
        tone={biasTone}
      />
      <StatCard
        label="Coverage"
        value={`${c.intervals_with_selected_forecast}/${c.expected_intervals}`}
        hint={`${c.missing_actual_intervals} missing actual · ${c.missing_forecast_intervals} no eligible vintage`}
      />
    </div>
  )
}

export function DailyTrend({ accuracy, loading, error }: { accuracy: AccuracyResponse | null; loading: boolean; error: string | null }) {
  if (loading) return <Card title="What the cutoff rule does across the month"><Loading /></Card>
  if (error) return <Card title="What the cutoff rule does across the month"><ErrorNote message={error} /></Card>
  if (!accuracy) return null
  const data = accuracy.by_day.map((d) => ({
    day: d.delivery_date.slice(5),
    mae: d.metrics.mae_mw,
    bias: d.metrics.mean_bias_mw,
  }))
  return (
    <Card
      title="What the cutoff rule does across the month"
      subtitle="Daily MAE (bars) and signed bias (line) under the selected cutoff policy."
      accent={`Counts ${accuracy.overall.count.toLocaleString('en-GB')} half-hours`}
    >
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 4 }}>
            <CartesianGrid stroke="oklch(0.3 0.03 260)" strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="day" tick={{ fill: 'oklch(0.6 0.02 260)', fontSize: 9 }} tickLine={false} interval={1} />
            <YAxis tick={{ fill: 'oklch(0.6 0.02 260)', fontSize: 10 }} tickLine={false} tickFormatter={(v: number) => `${(v / 1000).toFixed(0)}k`} />
            <Tooltip
              cursor={{ fill: 'oklch(0.3 0.03 260 / 0.25)' }}
              contentStyle={{ background: 'oklch(0.18 0.03 260)', border: '1px solid oklch(0.34 0.03 260)', borderRadius: 8, fontSize: 12 }}
              formatter={(value) => [`${Number(value).toLocaleString('en-GB', { maximumFractionDigits: 1 })} MW`, 'Daily MAE'] as [string, string]}
            />
            <Bar dataKey="mae" fill="oklch(0.45 0.14 230)" radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Card>
  )
}

export function ErrorHistogram({ accuracy }: { accuracy: AccuracyResponse | null }) {
  if (!accuracy) return null
  const bins = accuracy.error_histogram.map((b) => ({
    label: b.lower_mw === 0 ? '0' : `${b.lower_mw / 1000}k`,
    ...b,
  }))
  const width = Math.max(...bins.map((b) => b.upper_mw - b.lower_mw), 500)
  const peak = Math.max(...bins.map((b) => b.count), 1)
  return (
    <Card
      title="Error distribution (fixed bins, zero-centred)"
      subtitle="500 MW bins symmetric around 0 — scale fixed by policy, not data, so periods stay comparable."
      accent={`${bins.length} bins`}
    >
      <div className="h-56">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={bins} margin={{ top: 8, right: 8, bottom: 0, left: 4 }} barCategoryGap={2}>
            <CartesianGrid stroke="oklch(0.3 0.03 260)" strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="label" tick={{ fill: 'oklch(0.6 0.02 260)', fontSize: 9 }} tickLine={false} interval={2} />
            <YAxis tick={{ fill: 'oklch(0.6 0.02 260)', fontSize: 10 }} tickLine={false} domain={[0, peak * 1.1]} />
            <Tooltip
              contentStyle={{ background: 'oklch(0.18 0.03 260)', border: '1px solid oklch(0.34 0.03 260)', borderRadius: 8, fontSize: 12 }}
              formatter={(value, _name, item) => {
                const b = item?.payload as { lower_mw?: number; upper_mw?: number } | undefined
                if (!b || b.lower_mw === undefined || b.upper_mw === undefined) return [String(value), 'half-hours'] as [string, string]
                return [
                  `${value} half-hours in [${b.lower_mw.toLocaleString('en-GB')}, ${b.upper_mw.toLocaleString('en-GB')}) MW`,
                  '',
                ] as [string, string]
              }}
            />
            <ReferenceLine x="0" stroke="oklch(0.62 0.02 260)" />
            <Bar dataKey="count" name="count" radius={[3, 3, 0, 0]}>
              {bins.map((b) => (
                <Cell key={b.label} fill={b.lower_mw >= 0 ? OVER : UNDER} fillOpacity={0.85} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-2 text-[11px] text-ink-400">
        Purple = over-forecast (error &gt; 0) · rose = under-forecast · bin width {width.toLocaleString('en-GB')} MW.
      </p>
    </Card>
  )
}
