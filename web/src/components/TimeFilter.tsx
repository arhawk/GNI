import { useLocation } from 'react-router-dom'
import { useTimeWindow } from '../TimeWindowContext'
import { PRESETS, formatUtc, windowFromPreset } from '../timeWindow'

export function TimeFilter() {
  const { pathname } = useLocation()
  const { window, setWindow } = useTimeWindow()

  if (pathname.startsWith('/reports')) {
    return null
  }

  return (
    <div className="time-filter time-filter-compact">
      <div className="time-filter-row">
        <span className="time-filter-label">统计窗口</span>
        <div className="seg time-presets" role="group" aria-label="统计窗口预设">
          {PRESETS.map((p) => (
            <button
              key={p.days}
              type="button"
              className={window.presetDays === p.days ? 'active' : ''}
              onClick={() => setWindow(windowFromPreset(p.days))}
            >
              {p.label}
            </button>
          ))}
        </div>
        <span className="time-filter-range muted small">
          {formatUtc(window.startMs)} → {formatUtc(window.endMs)}
        </span>
      </div>
    </div>
  )
}
