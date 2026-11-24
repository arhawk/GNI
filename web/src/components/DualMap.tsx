import { useEffect, useRef, useState } from 'react'
import type { MapPin, ReportingPin } from '../api'

export type MapMode = 'event_geography' | 'reporting_source'

type Props = {
  mode: MapMode
  eventPins: MapPin[]
  reportingPins: ReportingPin[]
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

/** Lazy MapLibre — keeps initial shell paint independent of the map bundle. */
export function DualMap({ mode, eventPins, reportingPins }: Props) {
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
          const marker = new maplibregl.Marker({ element: el })
            .setLngLat([p.lon, p.lat])
            .setPopup(
              new maplibregl.Popup({ offset: 12 }).setText(`${p.title} · ${p.location_type}`),
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
  }, [mode, eventPins, reportingPins, ready])

  return (
    <div className="dual-map">
      <div ref={containerRef} className="dual-map-canvas" />
      {mapError && <p className="map-empty">Map failed: {mapError}</p>}
      {!mapError && mode === 'event_geography' && eventPins.length === 0 && (
        <p className="map-empty">
          No EVENT_LOCATION pins — proto-events without verified physical coordinates are listed
          below, not forced onto the map.
        </p>
      )}
    </div>
  )
}
