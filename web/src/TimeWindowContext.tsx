import {
  createContext,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { defaultWindow, type TimeWindow } from './timeWindow'

type Ctx = {
  window: TimeWindow
  setWindow: (w: TimeWindow) => void
  /** Extents from last overview meta; fallback = last year → now */
  dataMinMs: number
  dataMaxMs: number
  setDataExtent: (minMs: number | null, maxMs: number | null) => void
}

const TimeWindowContext = createContext<Ctx | null>(null)

export function TimeWindowProvider({ children }: { children: ReactNode }) {
  const [window, setWindow] = useState<TimeWindow>(() => defaultWindow())
  const [extent, setExtent] = useState<{ min: number; max: number }>(() => {
    const max = Date.now()
    return { min: max - 365 * 86_400_000, max }
  })

  const value = useMemo<Ctx>(
    () => ({
      window,
      setWindow,
      dataMinMs: extent.min,
      dataMaxMs: extent.max,
      setDataExtent: (minMs, maxMs) => {
        const max = maxMs ?? Date.now()
        const min = minMs ?? max - 365 * 86_400_000
        setExtent({ min: Math.min(min, max), max: Math.max(min, max) })
      },
    }),
    [window, extent],
  )

  return (
    <TimeWindowContext.Provider value={value}>{children}</TimeWindowContext.Provider>
  )
}

export function useTimeWindow() {
  const ctx = useContext(TimeWindowContext)
  if (!ctx) throw new Error('useTimeWindow requires TimeWindowProvider')
  return ctx
}
