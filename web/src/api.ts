const BASE = ''

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText}`)
  }
  return res.json() as Promise<T>
}

export type Overview = {
  meta: {
    days: number
    preset_days: number | null
    window_start: string
    window_end: string
    data_min: string | null
    data_max: string | null
    map_modes: string[]
    map_modes_note: string
    metric_definition_version?: string
    relevance_weight_version?: string
  }
  kpis: {
    total_articles_universe: number | null
    china_article_count: number | null
    weighted_article_volume: number | null
    monitoring_countries: number | null
    active_sources_registry: number | null
    china_reporting_countries: number | null
    china_reporting_sources: number | null
    country_count: number | null
    source_count: number | null
    major_events: number
    alerts: number
  }
  maps: {
    event_geography: MapPin[]
    reporting_source: ReportingPin[]
  }
  topics: Record<string, unknown> | { counts?: Record<string, number> }
  sentiment: Record<string, unknown> | { counts?: Record<string, number> }
  events: EventSummary[]
  anomalies: {
    note: string
    items: Array<{
      kind: string
      event_id: string
      title: string
      importance_score: number | null
      article_count: number
    }>
  }
}

export type MapPin = {
  event_id: string
  title: string
  location_type: string
  lat: number
  lon: number
  layer: string
}

export type ReportingPin = {
  country_id: string
  lat: number
  lon: number
  article_count: number
  layer: string
}

export type EventSummary = {
  id: string
  title: string
  summary: string | null
  event_type: string | null
  status: string
  importance_score: number | null
  window_start: string | null
  window_end: string | null
  has_physical_location: boolean
  article_count: number
  locations: Array<{
    location_type: string
    label: string | null
    country_id: string | null
    lat: number | null
    lon: number | null
  }>
}

export type EventDetail = {
  event: {
    id: string
    title: string
    summary: string | null
    event_type: string | null
    status: string
    importance_score: number | null
    window_start: string | null
    window_end: string | null
    has_physical_location: boolean
    schema_version: string
  }
  views: {
    where: {
      locations: Array<{
        location_type: string
        label: string | null
        country_id: string | null
        lat: number | null
        lon: number | null
        notes: string | null
      }>
      note: string | null
    }
    who_reports: {
      countries: Array<{
        country_id: string
        article_count: number
        media: Array<{
          source_id: string
          source_name: string
          article_count: number
          articles: Array<{
            article_id: string
            title: string | null
            url: string | null
            sentiment: string | null
            stance: string | null
            frame: string | null
            published_at: string | null
          }>
        }>
      }>
      reporting_map: ReportingPin[]
    }
    how_they_frame: {
      narratives: Array<{
        id: string
        label: string
        frame_id: string | null
        summary: string | null
        evidence: Array<{
          article_id: string
          quote: string | null
          title: string | null
        }>
      }>
    }
  }
  participants: Array<{
    participant_id: string
    participant_name: string | null
    role: string | null
  }>
  timeline: Array<{
    at: string
    kind: string
    article_id: string
    title: string | null
    country_id: string | null
  }>
}

export type OverviewQuery = {
  days?: number
  start?: string
  end?: string
}

export function fetchOverview(q: OverviewQuery = { days: 30 }) {
  const params = new URLSearchParams()
  if (q.start && q.end) {
    params.set('start', q.start)
    params.set('end', q.end)
  } else if (q.days != null) {
    params.set('days', String(q.days))
  }
  return get<Overview>(`/api/overview?${params.toString()}`)
}

export function fetchEvents(limit = 50) {
  return get<{ events: EventSummary[] }>(`/api/events?limit=${limit}`)
}

export function fetchEventDetail(id: string) {
  return get<EventDetail>(`/api/events/${id}`)
}
