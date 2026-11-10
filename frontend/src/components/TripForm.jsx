import { useState } from 'react'

function defaultDeparture() {
  // Next full hour, formatted for <input type="datetime-local"> in UTC.
  const d = new Date()
  d.setUTCMinutes(0, 0, 0)
  d.setUTCHours(d.getUTCHours() + 1)
  return d.toISOString().slice(0, 16)
}

const INTERVALS = [10, 25, 50]

export default function TripForm({ onSubmit, isPending }) {
  const [values, setValues] = useState({
    origin: 'Dallas, TX',
    destination: 'Oklahoma City, OK',
    departure_time: defaultDeparture(),
    load_weight: 35000,
    interval_miles: 25,
  })
  const [simulate, setSimulate] = useState(false)

  const set = (key) => (e) => {
    const v = e.target.value
    setValues((prev) => ({ ...prev, [key]: v }))
  }

  const submit = (e) => {
    e.preventDefault()
    onSubmit({
      ...values,
      load_weight: Number(values.load_weight),
      interval_miles: Number(values.interval_miles),
      simulate: simulate ? 'storm' : '',
    })
  }

  return (
    <form onSubmit={submit} className="space-y-3">
      <div>
        <label className="block text-xs font-medium text-slate-400 mb-1">Origin</label>
        <input
          required
          value={values.origin}
          onChange={set('origin')}
          placeholder="City, State"
          className="w-full rounded-lg bg-slate-800 border border-slate-700 px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500"
        />
      </div>

      <div>
        <label className="block text-xs font-medium text-slate-400 mb-1">Destination</label>
        <input
          required
          value={values.destination}
          onChange={set('destination')}
          placeholder="City, State"
          className="w-full rounded-lg bg-slate-800 border border-slate-700 px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500"
        />
      </div>

      <div>
        <label className="block text-xs font-medium text-slate-400 mb-1">
          Departure <span className="text-slate-500">(UTC)</span>
        </label>
        <input
          required
          type="datetime-local"
          value={values.departure_time}
          onChange={set('departure_time')}
          className="w-full rounded-lg bg-slate-800 border border-slate-700 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-sky-500"
        />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs font-medium text-slate-400 mb-1">Load (lb)</label>
          <input
            required
            type="number"
            min="0"
            max="200000"
            step="500"
            value={values.load_weight}
            onChange={set('load_weight')}
            className="w-full rounded-lg bg-slate-800 border border-slate-700 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-sky-500"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-400 mb-1">Sample every</label>
          <select
            value={values.interval_miles}
            onChange={set('interval_miles')}
            className="w-full rounded-lg bg-slate-800 border border-slate-700 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-sky-500"
          >
            {INTERVALS.map((i) => (
              <option key={i} value={i}>
                {i} miles
              </option>
            ))}
          </select>
        </div>
      </div>

      <label className="flex items-start gap-2 rounded-lg border border-slate-700 bg-slate-800/40 px-3 py-2 cursor-pointer select-none">
        <input
          type="checkbox"
          checked={simulate}
          onChange={(e) => setSimulate(e.target.checked)}
          className="mt-0.5 accent-amber-500"
        />
        <span className="text-xs text-slate-300">
          <span className="font-semibold text-amber-400">Simulate storm</span>{' '}
          <span className="text-slate-500">(demo)</span>
          <span className="block text-[10px] text-slate-500 mt-0.5">
            Replaces the live forecast with a synthetic moving storm to show the
            risk rules in action.
          </span>
        </span>
      </label>

      <button
        type="submit"
        disabled={isPending}
        className="w-full rounded-lg bg-sky-600 hover:bg-sky-500 disabled:bg-slate-700 disabled:text-slate-400 px-4 py-2.5 text-sm font-semibold text-white transition-colors"
      >
        {isPending ? 'Analyzing routes…' : 'Find safest route'}
      </button>
    </form>
  )
}
