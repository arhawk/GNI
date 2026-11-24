import { useRef, type PointerEvent } from 'react'
import { useTimeWindow } from '../TimeWindowContext'
import {
  PRESETS,
  clampWindow,
  formatUtc,
  translateWindow,
  windowFromPreset,
} from '../timeWindow'

export function TimeFilter() {
  const { window, setWindow, dataMinMs, dataMaxMs } = useTimeWindow()
  const dragRef = useRef<{ mode: 'start' | 'end' | 'span'; originX: number; origin: typeof window } | null>(
    null,
  )
  const trackRef = useRef<HTMLDivElement | null>(null)

  const span = Math.max(1, dataMaxMs - dataMinMs)
  const leftPct = ((window.startMs - dataMinMs) / span) * 100
  const rightPct = ((window.endMs - dataMinMs) / span) * 100
  const widthPct = Math.max(0.5, rightPct - leftPct)

  function msFromClientX(clientX: number) {
    const el = trackRef.current
    if (!el) return dataMinMs
    const rect = el.getBoundingClientRect()
    const t = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width))
    return dataMinMs + t * span
  }

  function onPointerDown(mode: 'start' | 'end' | 'span', e: PointerEvent) {
    e.preventDefault()
    ;(e.target as HTMLElement).setPointerCapture?.(e.pointerId)
    dragRef.current = { mode, originX: e.clientX, origin: { ...window } }
  }

  function onPointerMove(e: PointerEvent) {
    const drag = dragRef.current
    if (!drag) return
    if (drag.mode === 'span') {
      const delta = msFromClientX(e.clientX) - msFromClientX(drag.originX)
      setWindow(translateWindow(drag.origin, delta, dataMinMs, dataMaxMs))
      return
    }
    const at = msFromClientX(e.clientX)
    if (drag.mode === 'start') {
      setWindow(clampWindow(at, drag.origin.endMs, dataMinMs, dataMaxMs))
    } else {
      setWindow(clampWindow(drag.origin.startMs, at, dataMinMs, dataMaxMs))
    }
  }

  function onPointerUp() {
    dragRef.current = null
  }

  return (
    <div className="time-filter">
      <div className="time-filter-row">
        <span className="time-filter-label">Time window</span>
        <div className="seg time-presets" role="group" aria-label="Time presets">
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
      <div
        className="time-track"
        ref={trackRef}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
      >
        <div className="time-track-rail" />
        <div
          className="time-track-span"
          style={{ left: `${leftPct}%`, width: `${widthPct}%` }}
          onPointerDown={(e) => onPointerDown('span', e)}
          title="Drag to move window"
        />
        <button
          type="button"
          className="time-thumb"
          style={{ left: `${leftPct}%` }}
          aria-label="Window start"
          onPointerDown={(e) => onPointerDown('start', e)}
        />
        <button
          type="button"
          className="time-thumb"
          style={{ left: `${rightPct}%` }}
          aria-label="Window end"
          onPointerDown={(e) => onPointerDown('end', e)}
        />
      </div>
    </div>
  )
}
