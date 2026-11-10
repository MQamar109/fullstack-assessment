import { fmtUTC } from '../lib/risk'
import { RISK_LEVELS, RISK_COLORS } from '../lib/risk'

export default function TimeSlider({
  hour,
  setHour,
  hours,
  heatVisible,
  setHeatVisible,
}) {
  const current = hours?.[hour]
  const max = Math.max((hours?.length ?? 1) - 1, 0)

  return (
    <div className="absolute bottom-4 left-4 right-4 z-[1000] rounded-xl border border-slate-700 bg-slate-900/90 backdrop-blur px-4 py-3 shadow-xl">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <label className="flex items-center gap-2 text-xs font-medium text-slate-300 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={heatVisible}
            onChange={(e) => setHeatVisible(e.target.checked)}
            className="accent-sky-500"
          />
          Weather heatmap
        </label>

        <div className="flex items-center gap-2 text-xs text-slate-400">
          <span className="font-semibold text-slate-200">+{hour}h</span>
          <span>{current ? `${fmtUTC(current.time)} UTC` : '—'}</span>
        </div>

        <div className="flex items-center gap-3 ml-auto">
          {RISK_LEVELS.map((lvl) => (
            <span key={lvl} className="flex items-center gap-1 text-[10px] text-slate-400">
              <span
                className="h-2.5 w-2.5 rounded-sm"
                style={{ backgroundColor: RISK_COLORS[lvl] }}
              />
              {lvl}
            </span>
          ))}
        </div>
      </div>

      <input
        type="range"
        min={0}
        max={max}
        step={1}
        value={hour}
        onChange={(e) => setHour(Number(e.target.value))}
        disabled={!heatVisible || max === 0}
        className="mt-2 w-full disabled:opacity-40"
      />
      <div className="flex justify-between text-[10px] text-slate-500">
        <span>now</span>
        <span>+24h</span>
        <span>+{max}h</span>
      </div>
    </div>
  )
}
