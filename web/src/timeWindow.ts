export const PRESETS = [
  { days: 1, label: '近1天' },
  { days: 7, label: '近1周' },
  { days: 14, label: '近2周' },
  { days: 30, label: '近1个月' },
  { days: 90, label: '近3个月' },
] as const

export type TimeWindow = {
  startMs: number
  endMs: number
  presetDays: number | null
}

const DAY_MS = 86_400_000

export function nowUtcMs() {
  return Date.now()
}

export function windowFromPreset(days: number, endMs = nowUtcMs()): TimeWindow {
  return {
    endMs,
    startMs: endMs - days * DAY_MS,
    presetDays: days,
  }
}

export function defaultWindow(): TimeWindow {
  return windowFromPreset(30)
}

export function formatUtc(ms: number) {
  return new Date(ms).toISOString().slice(0, 16).replace('T', ' ') + 'Z'
}

export function clampWindow(
  startMs: number,
  endMs: number,
  dataMinMs: number,
  dataMaxMs: number,
): TimeWindow {
  const minSpan = DAY_MS
  const maxSpan = 366 * DAY_MS
  let s = Math.max(dataMinMs, Math.min(startMs, dataMaxMs - minSpan))
  let e = Math.min(dataMaxMs, Math.max(endMs, dataMinMs + minSpan))
  if (e - s < minSpan) e = s + minSpan
  if (e - s > maxSpan) s = e - maxSpan
  if (s < dataMinMs) {
    s = dataMinMs
    e = Math.min(dataMaxMs, s + Math.min(e - s, maxSpan))
  }
  if (e > dataMaxMs) {
    e = dataMaxMs
    s = Math.max(dataMinMs, e - Math.min(e - s, maxSpan))
  }
  return { startMs: s, endMs: e, presetDays: null }
}

/** Move the whole window by delta while staying inside data extents. */
export function translateWindow(
  win: TimeWindow,
  deltaMs: number,
  dataMinMs: number,
  dataMaxMs: number,
): TimeWindow {
  const span = win.endMs - win.startMs
  let s = win.startMs + deltaMs
  let e = win.endMs + deltaMs
  if (s < dataMinMs) {
    s = dataMinMs
    e = s + span
  }
  if (e > dataMaxMs) {
    e = dataMaxMs
    s = e - span
  }
  return { startMs: s, endMs: e, presetDays: null }
}
