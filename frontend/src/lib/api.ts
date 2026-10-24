export interface HealthResponse {
  status: string
  version: string
  data_mode: string
  dataset_start_utc: string | null
  dataset_end_utc: string | null
  actual_rows: number
  forecast_rows: number
}

export interface CutoffDescriptor {
  mode: string
  preset: string | null
  cutoff_utc: string
  cutoff_london: string
}

export interface MetricSummary {
  count: number
  mae_mw: number | null
  rmse_mw: number | null
  mean_bias_mw: number | null
}

export interface CoverageResponse {
  expected_intervals: number
  intervals_with_actual: number
  intervals_with_selected_forecast: number
  valid_pairs: number
  missing_actual_intervals: number
  missing_forecast_intervals: number
}

export interface SummaryResponse {
  delivery_date: string
  cutoff: CutoffDescriptor
  metrics: MetricSummary
  coverage: CoverageResponse
}

export interface SeriesPoint {
  interval_start_utc: string
  interval_start_london: string
  settlement_date: string
  settlement_period: number
  actual_mw: number | null
  forecast_mw: number | null
  forecast_publish_time_utc: string | null
  forecast_publish_time_london: string | null
  available: boolean
  error_mw: number | null
}

export interface SeriesResponse {
  delivery_date: string
  cutoff: CutoffDescriptor
  points: SeriesPoint[]
}

export interface VintageRecord {
  publish_time_utc: string
  publish_time_london: string
  forecast_mw: number | null
  lead_hours: number
  eligible: boolean
  excluded_reason: string | null
  selected: boolean
}

export interface VintagesResponse {
  settlement_date: string
  settlement_period: number
  interval_start_utc: string
  hour_end_label_utc: string
  cutoff: CutoffDescriptor
  selected_forecast_mw: number | null
  available: boolean
  vintages: VintageRecord[]
}

export interface DailyErrorRow {
  delivery_date: string
  cutoff_utc: string
  metrics: MetricSummary
}

export interface HourOfDayRow {
  london_hour: number
  count: number
  mae_mw: number | null
  rmse_mw: number | null
  mean_bias_mw: number | null
}

export interface HistogramBin {
  lower_mw: number
  upper_mw: number
  count: number
}

export interface AccuracyResponse {
  period_start_date: string
  period_end_date: string
  cutoff: CutoffDescriptor
  overall: MetricSummary
  by_day: DailyErrorRow[]
  by_london_hour: HourOfDayRow[]
  error_histogram: HistogramBin[]
}

export interface SnapshotManifestResponse {
  source: string
  retrieved_at_utc: string | null
  period: { settlement_from: string; settlement_to: string; publication_window_utc?: string[] }
  counts: Record<string, number>
  processing: string[]
  alignment_convention: string
  cutoff_assumption: { default_preset: string; presets?: string[]; rationale?: string }
  notes: string[]
}

export interface ApiError {
  detail?: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  expires_in: number
  email: string
  role: string
}

export interface UserOut {
  email: string
  role: string
}

const TOKEN_KEY = 'windlens.jwt'
const UNAUTH_EVENT = 'windlens:unauthenticated'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

export function onUnauthenticated(handler: () => void): () => void {
  const listener = () => handler()
  window.addEventListener(UNAUTH_EVENT, listener)
  return () => window.removeEventListener(UNAUTH_EVENT, listener)
}

const BASE = ((import.meta.env.VITE_WINDLENS_API_BASE as string | undefined)?.trim() || '/api').replace(/\/$/, '')

const UNAUTHORIZED_PREFIXES = new Set([401])

async function parseError(response: Response): Promise<string> {
  if (UNAUTHORIZED_PREFIXES.has(response.status) && getToken()) clearToken()
  let detail = `${response.status} ${response.statusText}`
  try {
    const body = (await response.json()) as ApiError
    if (body.detail) detail = typeof body.detail === 'string' ? body.detail : detail
  } catch {
    /* keep generic detail */
  }
  return detail
}

async function request<T>(path: string, params: Record<string, string | undefined> = {}): Promise<T> {
  const url = new URL(BASE + path, window.location.origin)
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '') url.searchParams.set(key, value)
  }
  const token = getToken()
  const response = await fetch(url.toString(), {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (!response.ok) {
    if (response.status === 401 && getToken()) window.dispatchEvent(new Event(UNAUTH_EVENT))
    throw new Error(await parseError(response))
  }
  return (await response.json()) as T
}

async function authPost<T>(path: string, body: unknown, method = 'POST'): Promise<T> {
  const token = getToken()
  const response = await fetch(BASE + path, {
    method,
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    if (response.status === 401 && getToken()) window.dispatchEvent(new Event(UNAUTH_EVENT))
    throw new Error(await parseError(response))
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export const api = {
  login: (email: string, password: string) =>
    authPost<LoginResponse>('/auth/login', { email, password }),
  me: () => request<UserOut>('/auth/me'),
  health: () => request<HealthResponse>('/health'),
  metadata: () => request<SnapshotManifestResponse>('/metadata'),
  summary: (date: string, cutoffPreset?: string, cutoffIso?: string) =>
    request<SummaryResponse>('/summary', { date, preset: cutoffPreset, cutoff: cutoffIso }),
  series: (date: string, cutoffPreset?: string, cutoffIso?: string) =>
    request<SeriesResponse>('/series', { date, preset: cutoffPreset, cutoff: cutoffIso }),
  vintages: (date: string, period: number, cutoffPreset?: string, cutoffIso?: string) =>
    request<VintagesResponse>('/vintages', { date, period: String(period), preset: cutoffPreset, cutoff: cutoffIso }),
  accuracy: (cutoffPreset?: string, cutoffIso?: string) =>
    request<AccuracyResponse>('/accuracy', { preset: cutoffPreset, cutoff: cutoffIso }),
}
