import { useEffect, useRef, useState } from 'react'
import type { AttitudePin, MapPin, ReportingPin } from '../api'

export type MapMode = 'event_geography' | 'country_china_attitude' | 'reporting_source'

type Props = {
  mode: MapMode
  eventPins: MapPin[]
  attitudePins?: AttitudePin[]
  /** EventDetail Who-reports layer only (not Overview primary) */
  reportingPins?: ReportingPin[]
  onEventClick?: (eventId: string) => void
  onCountryClick?: (countryId: string) => void
}

const STYLE = {
  version: 8 as const,
  sources: {
    osm: {
      type: 'raster' as const,
      tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
      tileSize: 256,
      attribution: '© OpenStreetMap',
    },
  },
  layers: [{ id: 'osm', type: 'raster' as const, source: 'osm' }],
}

const ATTITUDE_COLOR: Record<string, string> = {
  positive: '#2f6f4e',
  neutral: '#8a7a4b',
  negative: '#8b3a3a',
  unknown: '#6b6b6b',
  none: '#c4c4c4',
}

/** Lazy MapLibre — keeps initial shell paint independent of the map bundle. */
export function DualMap({
  mode,
  eventPins,
  attitudePins = [],
  reportingPins = [],
  onEventClick,
  onCountryClick,
}: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const mapRef = useRef<import('maplibre-gl').Map | null>(null)
  const markersRef = useRef<import('maplibre-gl').Marker[]>([])
  const [mapError, setMapError] = useState<string | null>(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const maplibregl = await import('maplibre-gl')
        await import('maplibre-gl/dist/maplibre-gl.css')
        if (cancelled || !containerRef.current || mapRef.current) return
        const map = new maplibregl.Map({
          container: containerRef.current,
          style: STYLE,
          center: [20, 20],
          zoom: 1.4,
        })
        map.addControl(new maplibregl.NavigationControl(), 'top-right')
        mapRef.current = map
        setReady(true)
      } catch (e) {
        setMapError(e instanceof Error ? e.message : String(e))
      }
    })()
    return () => {
      cancelled = true
      markersRef.current.forEach((m) => m.remove())
      markersRef.current = []
      mapRef.current?.remove()
      mapRef.current = null
    }
  }, [])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready) return
    let cancelled = false
    ;(async () => {
      const maplibregl = await import('maplibre-gl')
      if (cancelled) return
      markersRef.current.forEach((m) => m.remove())
      markersRef.current = []

      if (mode === 'event_geography') {
        for (const p of eventPins) {
          const el = document.createElement('div')
          el.className = 'map-pin event'
          el.title = `${p.title} (${p.location_type})`
          el.style.cursor = 'pointer'
          el.addEventListener('click', (ev) => {
            ev.stopPropagation()
            onEventClick?.(p.event_id)
          })
          const marker = new maplibregl.Marker({ element: el })
            .setLngLat([p.lon, p.lat])
            .setPopup(
              new maplibregl.Popup({ offset: 12 }).setText(
                `${p.title} · ${p.location_type}${
                  p.article_count != null ? ` · ${p.article_count} articles` : ''
                }`,
              ),
            )
            .addTo(map)
          markersRef.current.push(marker)
        }
      } else if (mode === 'country_china_attitude') {
        for (const p of attitudePins) {
          if (p.lat == null || p.lon == null) continue
          const el = document.createElement('div')
          const label = p.label || 'none'
          el.className = `map-pin attitude ${label}${p.clickable ? ' clickable' : ' muted'}`
          el.style.background = ATTITUDE_COLOR[label] || ATTITUDE_COLOR.none
          const total =
            (p.counts?.positive || 0) +
            (p.counts?.neutral || 0) +
            (p.counts?.negative || 0) +
            (p.counts?.unknown || 0)
          const size = p.clickable ? 14 + Math.min(22, Math.sqrt(total) * 3) : 10
          el.style.width = `${size}px`
          el.style.height = `${size}px`
          el.title = p.clickable
            ? `${p.country_id}: ${label} (${total} articles)`
            : `${p.country_id}: no sample`
          if (p.clickable) {
            el.style.cursor = 'pointer'
            el.addEventListener('click', (ev) => {
              ev.stopPropagation()
              onCountryClick?.(p.country_id)
            })
          }
          const marker = new maplibregl.Marker({ element: el })
            .setLngLat([p.lon, p.lat])
            .setPopup(
              new maplibregl.Popup({ offset: 12 }).setText(
                p.clickable
                  ? `${p.country_id} attitude (sample): ${label} — +${p.counts.positive}/~${p.counts.neutral}/−${p.counts.negative}`
                  : `${p.country_id}: no monitored sample`,
              ),
            )
            .addTo(map)
          markersRef.current.push(marker)
        }
      } else {
        for (const p of reportingPins) {
          const el = document.createElement('div')
          el.className = 'map-pin report'
          const size = 10 + Math.min(28, Math.sqrt(p.article_count) * 4)
          el.style.width = `${size}px`
          el.style.height = `${size}px`
          el.title = `${p.country_id}: ${p.article_count} articles`
          const marker = new maplibregl.Marker({ element: el })
            .setLngLat([p.lon, p.lat])
            .setPopup(
              new maplibregl.Popup({ offset: 12 }).setText(
                `Reporting source ${p.country_id}: ${p.article_count} articles`,
              ),
            )
            .addTo(map)
          markersRef.current.push(marker)
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [mode, eventPins, attitudePins, reportingPins, ready, onEventClick, onCountryClick])

  return (
    <div className="dual-map">
      <div ref={containerRef} className="dual-map-canvas" />
      {mapError && <p className="map-empty">Map failed: {mapError}</p>}
      {!mapError && mode === 'event_geography' && eventPins.length === 0 && (
        <p className="map-empty">
          No EVENT_LOCATION pins — events without verified physical coordinates are listed
          below, not forced onto the map.
        </p>
      )}
      {!mapError && mode === 'country_china_attitude' && attitudePins.every((p) => !p.clickable) && (
        <p className="map-empty">
          No China-attitude samples yet — run analyze + events rebuild.
        </p>
      )}
    </div>
  )
}
