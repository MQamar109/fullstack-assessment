/**
 * Shared presentation constants and formatters: the risk level palette,
 * route colours, and UTC time and duration formatting.
 */
export const RISK_LEVELS = ['Low', 'Moderate', 'High', 'Severe', 'No Travel']

export const RISK_COLORS = {
  Low: '#16a34a',
  Moderate: '#f59e0b',
  High: '#ea580c',
  Severe: '#dc2626',
  'No Travel': '#7f1d1d',
}

export const ROUTE_COLORS = ['#38bdf8', '#a855f7', '#f472b6']

export const HEAT_GRADIENT = {
  0.0: '#16a34a',
  0.25: '#f59e0b',
  0.5: '#ea580c',
  0.75: '#dc2626',
  1.0: '#7f1d1d',
}

export function riskColor(level) {
  return RISK_COLORS[level] || '#64748b'
}

export function fmtUTC(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString('en-US', {
    timeZone: 'UTC',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

export function fmtDuration(hours) {
  if (hours == null) return '—'
  const h = Math.floor(hours)
  const m = Math.round((hours - h) * 60)
  return `${h}h ${String(m).padStart(2, '0')}m`
}
