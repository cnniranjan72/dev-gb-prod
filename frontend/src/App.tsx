import { useCallback, useEffect, useMemo, useState } from 'react'
import type { AccuracyResponse, HealthResponse, SnapshotManifestResponse, SummaryResponse, SeriesResponse, VintagesResponse } from './lib/api'
import { api, clearToken, getToken, onUnauthenticated, setToken } from './lib/api'
import { CutoffBar, Header, ProvenanceCard } from './components/Header'
import { ForecastChart } from './components/ForecastChart'
import { DailyTrend, ErrorHistogram, SummaryCards } from './components/AccuracyPanels'
import { HourBars, VintageExplorer } from './components/VintageExplorer'
import { LoginView, SessionBadge } from './components/LoginView'

const PERIOD_DATE_MIN = '2026-01-01'
const PERIOD_DATE_MAX = '2026-01-31'

const PRESETS = [
  { value: 'day_ahead_1030', label: 'Day-ahead decision (10:30 London D−1)' },
  { value: 'day_ahead_gate_0950', label: 'Auction gate close (09:50 GMT D−1)' },
  { value: 'intraday_auction_1730', label: 'Intraday auction close (17:30 London D−1)' },
  { value: 'custom', label: 'Custom instant (UTC)' },
]

export default function App() {
  const [token, setTokenState] = useState<string | null>(getToken())
  const [identity, setIdentity] = useState<{ email: string; role: string } | null>(null)

  useEffect(() => onUnauthenticated(() => setTokenState(getToken())), [])

  const handleLogin = useCallback(async (email: string, password: string) => {
    const response = await api.login(email, password)
    setToken(response.access_token)
    setTokenState(response.access_token)
    setIdentity({ email: response.email, role: response.role })
  }, [])

  const handleLogout = useCallback(() => {
    clearToken()
    setTokenState(null)
    setIdentity(null)
  }, [])

  if (!token) {
    return <LoginView onLogin={handleLogin} />
  }
  return <Dashboard identity={identity} onLogout={handleLogout} />
}

function Dashboard({ identity, onLogout }: { identity: { email: string; role: string } | null; onLogout: () => void }) {
  const [date, setDate] = useState('2026-01-15')
  const [preset, setPreset] = useState('day_ahead_1030')
  const [customCutoff, setCustomCutoff] = useState('')
  const [period, setPeriod] = useState(1)

  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [manifest, setManifest] = useState<SnapshotManifestResponse | null>(null)
  const [summary, setSummary] = useState<SummaryResponse | null>(null)
  const [series, setSeries] = useState<SeriesResponse | null>(null)
  const [accuracy, setAccuracy] = useState<AccuracyResponse | null>(null)
  const [vintages, setVintages] = useState<VintagesResponse | null>(null)

  const [mainLoading, setMainLoading] = useState(true)
  const [mainError, setMainError] = useState<string | null>(null)
  const [vintageLoading, setVintageLoading] = useState(true)
  const [vintageError, setVintagesError] = useState<string | null>(null)

  const customCutoffTrimmed = useMemo(() => customCutoff.trim(), [customCutoff])
  const applyingCustom = preset === 'custom' && customCutoffTrimmed !== ''

  const loadMain = useCallback(async () => {
    setMainLoading(true)
    setMainError(null)
    try {
      const presetArg = applyingCustom ? 'custom' : preset
      const cutoffArg = applyingCustom ? customCutoffTrimmed : undefined
      const [h, m, s, sr, acc] = await Promise.all([
        api.health(),
        api.metadata(),
        api.summary(date, presetArg, cutoffArg),
        api.series(date, presetArg, cutoffArg),
        api.accuracy(presetArg, cutoffArg),
      ])
      setHealth(h)
      setManifest(m)
      setSummary(s)
      setSeries(sr)
      setAccuracy(acc)
    } catch (err) {
      setMainError(err instanceof Error ? err.message : String(err))
    } finally {
      setMainLoading(false)
    }
  }, [date, preset, applyingCustom, customCutoffTrimmed])

  const loadVintages = useCallback(async () => {
    setVintageLoading(true)
    setVintagesError(null)
    try {
      const presetArg = applyingCustom ? 'custom' : preset
      const cutoffArg = applyingCustom ? customCutoffTrimmed : undefined
      const result = await api.vintages(date, period, presetArg, cutoffArg)
      setVintages(result)
    } catch (err) {
      setVintagesError(err instanceof Error ? err.message : String(err))
    } finally {
      setVintageLoading(false)
    }
  }, [date, period, preset, applyingCustom, customCutoffTrimmed])

  useEffect(() => {
    void loadMain()
  }, [loadMain])
  useEffect(() => {
    void loadVintages()
  }, [loadVintages])

  const pickPeriodFromHour = (hour: number) => {
    // London hour h covers D+1 midnight-crossing days too; January is GMT so London hour
    // equals UTC hour: first period = 2h+1, second = 2h+2 (except hour 0 which we clamp to 1/2).
    setPeriod(hour === 0 ? 1 : 2 * hour + 1)
  }

  return (
    <div className="min-h-dvh">
      <Header health={health}>
        <SessionBadge identity={identity} onLogout={onLogout} />
      </Header>

      <main className="mx-auto max-w-7xl space-y-4 px-4 py-4">
        {/* Controls */}
        <div className="flex flex-wrap items-center gap-3 rounded-xl border border-ink-800 bg-ink-900/80 px-4 py-3 shadow-lg shadow-black/30">
          <label className="text-xs text-ink-400">
            Delivery date (settlement, Europe/London)
            <input
              type="date"
              min={PERIOD_DATE_MIN}
              max={PERIOD_DATE_MAX}
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="ml-3 rounded-md border border-ink-700 bg-ink-850 px-2 py-1 text-sm text-ink-200"
            />
          </label>
          <label className="text-xs text-ink-400">
            Procurement cutoff
            <select
              value={preset}
              onChange={(e) => setPreset(e.target.value)}
              className="ml-3 rounded-md border border-ink-700 bg-ink-850 px-2 py-1 text-sm text-ink-200"
            >
              {PRESETS.map((p) => (
                <option key={p.value} value={p.value}>
                  {p.label}
                </option>
              ))}
            </select>
          </label>
          {preset === 'custom' && (
            <label className="text-xs text-ink-400">
              Custom ISO-UTC instant
              <input
                value={customCutoff}
                onChange={(e) => setCustomCutoff(e.target.value)}
                placeholder="2026-01-14T09:50:00Z"
                className="ml-2 w-56 rounded-md border border-ink-700 bg-ink-850 px-2 py-1 font-mono text-sm text-ink-200 placeholder:text-ink-700"
              />
            </label>
          )}
          <div className="min-w-64 grow basis-64">
            {summary && <CutoffBar cutoff={summary.cutoff} />}
          </div>
        </div>

        {mainError && (
          <div className="rounded-xl border border-underrose-400/40 bg-underrose-400/10 px-4 py-3 text-sm text-underrose-400">
            {mainError}{' '}
            <button onClick={() => void loadMain()} className="ml-2 underline hover:no-underline">
              retry
            </button>
          </div>
        )}

        <SummaryCards summary={summary} />

        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
          <div className="space-y-4">
            <ForecastChart
              series={series}
              loading={mainLoading}
              error={mainError}
              onRetry={() => void loadMain()}
            />
            <DailyTrend accuracy={accuracy} loading={mainLoading} error={mainError} />
            <div className="grid gap-4 md:grid-cols-2">
              <ErrorHistogram accuracy={accuracy} />
              <HourBars byHour={accuracy?.by_london_hour ?? []} onPick={pickPeriodFromHour} />
            </div>
          </div>
          <div className="space-y-4">
            <ProvenanceCard manifest={manifest} health={health} />
          </div>
        </div>

        <VintageExplorer
          selection={vintages}
          period={period}
          onPeriodChange={setPeriod}
          loading={vintageLoading}
          error={vintageError}
        />
      </main>

      <footer className="mx-auto max-w-7xl px-4 pt-2 pb-8 text-[11px] text-ink-400">
        Sources: Elexon BMRS v1 (`/datasets/FUELHH`, `/datasets/WINDFOR`) · Actuals rows in settlement terminology are
        Europe/London · Forecast hours are hour-ending labelled · No rescaling of the two published views · {' '}
        <a className="underline hover:no-underline" href="/docs" onClick={(e) => e.preventDefault()} title="docs available in repo">
          docs/DATA_INVESTIGATION.md
        </a>
      </footer>
    </div>
  )
}
