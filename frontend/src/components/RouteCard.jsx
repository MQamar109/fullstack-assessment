import { riskColor, fmtDuration, ROUTE_COLORS } from '../lib/risk'

function Stat({ label, value, color }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wide text-slate-500">{label}</div>
      <div className="text-sm font-semibold" style={color ? { color } : undefined}>
        {value}
      </div>
    </div>
  )
}

export default function RouteCard({ route, selected, onSelect }) {
  const s = route.summary
  const color = ROUTE_COLORS[route.id % ROUTE_COLORS.length]

  return (
    <button
      type="button"
      onClick={() => onSelect(route.id)}
      className={`w-full text-left rounded-xl border p-3 transition-colors ${
        selected
          ? 'border-sky-500 bg-slate-800'
          : 'border-slate-700 bg-slate-800/50 hover:bg-slate-800'
      }`}
    >
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: color }} />
          <span className="text-sm font-semibold text-slate-200">
            Route {route.id + 1}
          </span>
          {route.recommended && (
            <span className="rounded-full bg-emerald-600/20 text-emerald-400 text-[10px] font-bold px-2 py-0.5 border border-emerald-600/40">
              RECOMMENDED
            </span>
          )}
        </div>
        <span
          className="text-[10px] font-bold px-2 py-0.5 rounded-full border"
          style={{
            color: riskColor(s.overall_risk),
            borderColor: riskColor(s.overall_risk),
          }}
        >
          {s.overall_risk}
        </span>
      </div>

      <div className="grid grid-cols-3 gap-2 mb-2">
        <Stat label="Distance" value={`${route.distance_miles} mi`} />
        <Stat label="Travel" value={fmtDuration(route.duration_hours)} />
        <Stat label="Avg risk" value={s.avg_risk_score.toFixed(2)} />
      </div>

      <div className="grid grid-cols-3 gap-2">
        <Stat
          label="No-travel"
          value={`${s.no_travel_miles} mi`}
          color={s.no_travel_miles > 0 ? riskColor('No Travel') : undefined}
        />
        <Stat
          label="Severe"
          value={`${s.severe_miles} mi`}
          color={s.severe_miles > 0 ? riskColor('Severe') : undefined}
        />
        <Stat
          label="High"
          value={`${s.high_miles} mi`}
          color={s.high_miles > 0 ? riskColor('High') : undefined}
        />
      </div>
    </button>
  )
}
