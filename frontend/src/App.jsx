/**
 * Root layout and state owner: holds the trip request, the selected route
 * and the heatmap hour, and lays out the sidebar beside the map.
 */
import { useState, useMemo } from 'react'
import { useMutation } from '@tanstack/react-query'
import { planTrip } from './lib/api'
import TripForm from './components/TripForm'
import RouteCard from './components/RouteCard'
import MapView from './components/MapView'
import TimeSlider from './components/TimeSlider'
import { fmtDuration, fmtUTC } from './lib/risk'

export default function App() {
  const [selectedRouteId, setSelectedRouteId] = useState(null)
  const [heatHour, setHeatHour] = useState(0)
  const [heatVisible, setHeatVisible] = useState(true)

  const mutation = useMutation({
    mutationFn: planTrip,
    onSuccess: (data) => {
      setSelectedRouteId(data.recommended_route_id ?? data.routes?.[0]?.id ?? null)
      setHeatHour(0)
    },
  })

  const data = mutation.data
  const routes = data?.routes ?? []
  const recommended = useMemo(
    () => data?.routes?.find((r) => r.id === data?.recommended_route_id),
    [data],
  )

  return (
    <div className="flex h-screen w-screen overflow-hidden">
      <aside className="w-[380px] shrink-0 overflow-y-auto border-r border-slate-800 bg-slate-900 p-4">
        <header className="mb-4">
          <h1 className="text-lg font-bold text-slate-100">Weather-Aware Truck Routing</h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Safest route by forecast weather, load weight &amp; travel time.
          </p>
        </header>

        <TripForm onSubmit={mutation.mutate} isPending={mutation.isPending} />

        {mutation.isError && (
          <div className="mt-4 rounded-lg border border-red-800 bg-red-950/60 px-3 py-2 text-xs text-red-300">
            {mutation.error.message}
          </div>
        )}

        {mutation.isPending && (
          <div className="mt-4 text-xs text-slate-400">
            Building routes, sampling forecasts at each checkpoint…
          </div>
        )}

        {data?.simulated && (
          <div className="mt-4 rounded-lg border border-amber-700/60 bg-amber-950/40 px-3 py-2 text-xs text-amber-300">
            <span className="font-semibold">Simulated weather.</span> These results use
            a synthetic storm, not the live forecast.
          </div>
        )}

        {recommended && (
          <div className="mt-4 rounded-xl border border-emerald-700/50 bg-emerald-950/30 p-3">
            <div className="text-[10px] font-bold uppercase tracking-wide text-emerald-400">
              Recommended
            </div>
            <div className="text-sm font-semibold text-slate-100 mt-0.5">
              Route {recommended.id + 1} · {recommended.distance_miles} mi ·{' '}
              {fmtDuration(recommended.duration_hours)}
            </div>
            <div className="text-xs text-slate-400 mt-1">
              Arrives{' '}
              {fmtUTC(recommended.checkpoints?.[recommended.checkpoints.length - 1]?.eta)}{' '}
              UTC · {recommended.summary.severe_miles} severe mi ·{' '}
              {recommended.summary.high_miles} high mi
            </div>
          </div>
        )}

        {routes.length > 0 && (
          <div className="mt-4 space-y-2">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Route options ({routes.length})
            </h2>
            {[...routes]
              .sort((a, b) => (a.rank ?? 99) - (b.rank ?? 99))
              .map((route) => (
                <RouteCard
                  key={route.id}
                  route={route}
                  selected={route.id === selectedRouteId}
                  onSelect={setSelectedRouteId}
                />
              ))}
            <p className="text-[10px] leading-relaxed text-slate-500 pt-1">
              Ranked by fewest no-travel miles, then severe, then high, then average
              risk, then travel time. Click a route to show its checkpoints.
            </p>
          </div>
        )}

        {!data && !mutation.isPending && (
          <div className="mt-6 text-xs text-slate-500 leading-relaxed">
            Enter a trip to generate three route options. Weather is sampled at every
            checkpoint using the truck&apos;s estimated arrival time there.
          </div>
        )}
      </aside>

      <main className="relative flex-1">
        <MapView
          data={data}
          selectedRouteId={selectedRouteId}
          onSelectRoute={setSelectedRouteId}
          heatVisible={heatVisible}
          heatHour={heatHour}
        />
        {data?.heatmap?.hours?.length > 0 && (
          <TimeSlider
            hour={heatHour}
            setHour={setHeatHour}
            hours={data.heatmap.hours}
            heatVisible={heatVisible}
            setHeatVisible={setHeatVisible}
          />
        )}
      </main>
    </div>
  )
}
