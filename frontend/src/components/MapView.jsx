import { useEffect, useMemo } from 'react'
import {
  MapContainer,
  TileLayer,
  Polyline,
  CircleMarker,
  Popup,
  Tooltip,
  useMap,
} from 'react-leaflet'
import HeatLayer from './HeatLayer'
import { riskColor, ROUTE_COLORS, fmtUTC } from '../lib/risk'

function FitBounds({ routes }) {
  const map = useMap()
  useEffect(() => {
    if (!routes?.length) return
    const pts = routes.flatMap((r) => r.geometry)
    if (!pts.length) return
    map.fitBounds(pts, { padding: [40, 40] })
  }, [map, routes])
  return null
}

function CheckpointMarker({ cp, routeId }) {
  const color = riskColor(cp.risk.level)
  return (
    <CircleMarker
      center={[cp.lat, cp.lng]}
      radius={5}
      pathOptions={{
        color: '#0f172a',
        weight: 1,
        fillColor: color,
        fillOpacity: 1,
      }}
    >
      <Popup>
        <div className="space-y-1">
          <div className="font-semibold text-slate-100">
            Route {routeId + 1} · mile {cp.distance_miles}
          </div>
          <div>
            <span className="text-slate-400">ETA:</span> {fmtUTC(cp.eta)} UTC
          </div>
          <div>
            <span className="text-slate-400">Risk:</span>{' '}
            <span style={{ color, fontWeight: 700 }}>{cp.risk.level}</span>
          </div>
          <div className="text-slate-300">
            Wind {cp.weather.wind_mph ?? '—'} mph · Rain {cp.weather.rain_in ?? '—'} in/hr ·
            Snow {cp.weather.snow_in ?? '—'} in/hr
          </div>
          {cp.weather.temp_f != null && (
            <div className="text-slate-400">Temp {cp.weather.temp_f}°F</div>
          )}
          <ul className="mt-1 text-slate-400 list-disc pl-4">
            {cp.risk.reasons.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        </div>
      </Popup>
    </CircleMarker>
  )
}

function Endpoint({ point, label, color }) {
  if (!point) return null
  return (
    <CircleMarker
      center={[point.lat, point.lng]}
      radius={7}
      pathOptions={{ color: '#f8fafc', weight: 2, fillColor: color, fillOpacity: 1 }}
    >
      <Tooltip direction="top" offset={[0, -8]}>
        <span className="font-semibold">{label}:</span> {point.label}
      </Tooltip>
    </CircleMarker>
  )
}

export default function MapView({
  data,
  selectedRouteId,
  onSelectRoute,
  heatVisible,
  heatHour,
}) {
  const routes = data?.routes ?? []

  const heat = useMemo(() => {
    const hm = data?.heatmap
    if (!hm) return { points: [], intensity: [] }
    const hour = hm.hours?.[heatHour] ?? hm.hours?.[0]
    return { points: hm.points ?? [], intensity: hour?.intensity ?? [] }
  }, [data, heatHour])

  const selected = routes.find((r) => r.id === selectedRouteId)

  return (
    <MapContainer
      center={[39.5, -98.35]}
      zoom={4}
      className="h-full w-full"
      preferCanvas
      scrollWheelZoom
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        maxZoom={19}
      />

      <HeatLayer points={heat.points} intensity={heat.intensity} visible={heatVisible} />

      {/* Draw unselected routes first so the selected one sits on top. */}
      {routes
        .filter((r) => r.id !== selectedRouteId)
        .map((r) => (
          <Polyline
            key={r.id}
            positions={r.geometry}
            pathOptions={{
              color: ROUTE_COLORS[r.id % ROUTE_COLORS.length],
              weight: 3,
              opacity: 0.5,
            }}
            eventHandlers={{ click: () => onSelectRoute(r.id) }}
          />
        ))}

      {selected && (
        <Polyline
          positions={selected.geometry}
          pathOptions={{
            color: ROUTE_COLORS[selected.id % ROUTE_COLORS.length],
            weight: 6,
            opacity: 0.95,
          }}
        />
      )}

      {/* Checkpoints for the selected route only — keeps the map readable. */}
      {selected?.checkpoints.map((cp, i) => (
        <CheckpointMarker key={`${selected.id}-${i}`} cp={cp} routeId={selected.id} />
      ))}

      <Endpoint point={data?.origin} label="Origin" color="#22c55e" />
      <Endpoint point={data?.destination} label="Destination" color="#ef4444" />

      <FitBounds routes={routes} />
    </MapContainer>
  )
}
