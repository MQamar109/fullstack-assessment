/**
 * HTTP client for the planning API. Posts a trip to the backend and
 * flattens DRF validation errors into a single readable message.
 */
const BASE = (import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000').replace(/\/$/, '')

export async function planTrip(payload) {
  const res = await fetch(`${BASE}/api/plan/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })

  let data = null
  try {
    data = await res.json()
  } catch {
    data = null
  }

  if (!res.ok) {
    const detail =
      data?.error ||
      (data && typeof data === 'object'
        ? Object.entries(data)
            .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : v}`)
            .join(' · ')
        : null)
    throw new Error(detail || `Request failed (${res.status})`)
  }
  return data
}

export { BASE as API_BASE }
