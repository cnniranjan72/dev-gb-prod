export function formatMw(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—'
  return `${value.toLocaleString('en-GB', { minimumFractionDigits: digits, maximumFractionDigits: digits })} MW`
}

export function formatMwShort(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—'
  return `${(value / 1000).toFixed(1)} GWh`
}

export function utcTimeLabel(iso: string | null): string {
  if (!iso) return '—'
  const time = iso.slice(11, 16)
  return time.endsWith('Z') ? time.slice(0, 5) : time
}

export function londonTimeLabel(iso: string | null): string {
  if (!iso) return '—'
  return iso.slice(11, 16)
}

export function signed(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—'
  const sign = value > 0 ? '+' : value < 0 ? '−' : ''
  return sign + Math.abs(value).toLocaleString('en-GB', { maximumFractionDigits: 1 })
}

export function leadLabel(hours: number): string {
  const sign = hours >= 0 ? '+' : '−'
  return `${sign}${Math.abs(hours).toFixed(1)} h to delivery`
}

export function periodRange(period: number): string {
  const start = (period - 1) * 30
  const end = start + 30
  const hhmm = (minutes: number): string => {
    const h = Math.floor(minutes / 60) % 24
    const m = minutes % 60
    return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`
  }
  return `${hhmm(start)}–${hhmm(end)}`
}
