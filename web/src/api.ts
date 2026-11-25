const BASE = ''

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText}`)
  }
  return res.json() as Promise<T>
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
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
    country_china_attitude: AttitudePin[]
    reporting_source?: ReportingPin[]
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
  article_count?: number | null
  importance?: number | null
  layer: string
}

export type AttitudePin = {
  country_id: string
  label: string
  counts: {
    positive: number
    neutral: number
    negative: number
    unknown: number
  }
  clickable: boolean
  lat?: number
  lon?: number
  layer: string
}

export type ReportingPin = {
  country_id: string
  lat: number
  lon: number
  article_count: number
  layer: string
}

export type CountryAttitudeDetail = {
  country_id: string
  window: string
  label: string
  counts: {
    positive: number
    neutral: number
    negative: number
    unknown: number
  }
  clickable: boolean
  disclaimer: string
  articles: Array<{
    article_id: string
    title: string | null
    url: string | null
    source_id: string
    source_name: string
    sentiment: string | null
    published_at: string | null
  }>
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
  event_time?: string | null
  sort_time?: string | null
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

export type DailyReport = {
  report_type: string
  schema_version?: string
  period: string
  period_start?: string
  period_end?: string
  timezone?: string
  generated_at: string
  country_scope: string[]
  target_scope: string
  disclaimer: string
  generator?: string
  article_count?: number
  event_count?: number
  connected?: {
    countries: number
    active_sources: number
    country_ids: string[]
  }
  validation?: { ok: boolean; checks?: Array<{ name: string; ok: boolean }>; errors?: string[] }
  narratives?: {
    executive?: string
    coverage?: string
    tone?: string
    signals?: string
    quality?: string
  }
  sections: {
    summary: {
      kpis: {
        china_articles: number
        reporting_countries: number
        reporting_sources: number
        new_events: number
        major_events: number
        day_articles: number
        stories?: number
        articles_analyzed?: number
        sources_cited?: number
      }
      comparisons?: {
        vs_yesterday?: { china_articles: number; delta: number }
        vs_7d_avg?: { china_articles: number; delta: number }
      }
      top_changes: Array<{
        title: string
        summary: string
        kind: string
        href?: string
        evidence?: Record<string, unknown>
      }>
      overview_text: string
    }
    major_events: Array<{
      event_id: string
      title: string
      importance_score?: number | null
      event_type?: string | null
      event_time?: string | null
      first_seen_at?: string | null
      status?: string | null
      overview_text?: string
      href?: string
      core?: Record<string, string | null | undefined>
      coverage?: {
        article_count: number
        country_count: number
        source_count: number
        countries?: string[]
      }
      sentiment_counts?: {
        positive: number
        neutral: number
        negative: number
      }
      sentiment_shares?: {
        positive: number
        neutral: number
        negative: number
      }
      sentiment_n?: number
      sentiment_skipped_government?: number
      by_country_views?: Array<{
        country_id: string
        article_count: number
        dominant_sentiment?: string | null
        dominant_stance?: string | null
        frame?: string | null
        href?: string
      }>
      follow_ups?: string[]
      evidence: Array<{
        article_id: string
        title: string | null
        country_id: string | null
        source_id?: string | null
        url?: string | null
        sentiment?: string | null
        stance?: string | null
        published_at?: string | null
      }>
    }>
    coverage: {
      by_country: Array<{
        country_id: string
        article_count: number
        weighted_volume?: number
        source_count?: number
        href?: string
      }>
      by_source?: Array<{
        source_id: string
        name: string
        country_id: string | null
        article_count: number
      }>
      topics_top: Array<{ label: string; count: number; share: number }>
      frames_top: Array<{ label: string; count: number; share: number }>
      note?: string
    }
    tone: {
      note?: string
      overall_sentiment_counts: Record<string, number>
      overall_stance_counts: Record<string, number>
      by_country: Array<{
        country_id: string
        n: number
        sentiment_counts: Record<string, number>
        stance_counts: Record<string, number>
        summary_text: string
        href?: string
      }>
    }
    signals: Array<{
      id?: string
      subcategory?: string
      severity?: string
      title: string
      summary?: string
      status?: string
      href?: string
      evidence?: Record<string, unknown>
    }>
    quality: {
      missing_analysis: number
      countries_without_sample: string[]
      notes: string[]
      source_health_summary?: Record<string, unknown>
      source_health?: Array<Record<string, unknown>>
    }
  }
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
    actor_key?: string | null
    action_key?: string | null
    object_key?: string | null
    event_time?: string | null
    fingerprint_hash?: string | null
  }
  metrics?: {
    article_count: number
    source_count: number | null
    country_count: number | null
    sentiment_shares: Record<string, number> | null
    stance_shares: Record<string, number> | null
    by_country: Record<string, unknown> | null
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

export function fetchCountryChinaAttitude(countryId: string, window = '30d') {
  return get<CountryAttitudeDetail>(
    `/api/countries/${encodeURIComponent(countryId)}/china-attitude?window=${encodeURIComponent(window)}`,
  )
}

export function fetchDailyReport(date?: string) {
  const params = new URLSearchParams()
  if (date) params.set('date', date)
  const q = params.toString()
  return get<DailyReport>(`/api/reports/daily${q ? `?${q}` : ''}`)
}

export type PeriodReport = {
  report_type: string
  schema_version?: string
  period: string
  period_start?: string
  period_end?: string
  generated_at: string
  disclaimer: string
  article_count?: number
  sections: Record<string, unknown>
  narratives?: Record<string, string>
}

export function fetchWeeklyReport(end?: string) {
  const q = end ? `end=${encodeURIComponent(end)}` : ''
  return get<PeriodReport>(`/api/reports/weekly${q ? `?${q}` : ''}`)
}

export function fetchMonthlyReport(month?: string) {
  const q = month ? `month=${encodeURIComponent(month)}` : ''
  return get<PeriodReport>(`/api/reports/monthly${q ? `?${q}` : ''}`)
}

export type SearchHit = {
  kind: 'event' | 'article' | 'country' | 'source'
  id: string
  title: string
  subtitle?: string | null
  url?: string | null
  href?: string | null
  match?: string
}

export function fetchSearch(q: string, limit = 20) {
  const params = new URLSearchParams({ q, limit: String(limit) })
  return get<{ query: string; results: SearchHit[] }>(`/api/search?${params.toString()}`)
}

export type TrendsPayload = {
  days: number
  country_id: string | null
  china_article_count: number
  volume_series: Array<{ date: string; china_articles: number }>
  sentiment_series: Array<{
    date: string
    positive: number
    neutral: number
    negative: number
    unknown: number
  }>
  topics_top: Array<{ label: string; count: number; share: number }>
  note?: string
}

export function fetchTrends(days = 30, country?: string) {
  const params = new URLSearchParams({ days: String(days) })
  if (country) params.set('country', country)
  return get<TrendsPayload>(`/api/trends?${params.toString()}`)
}

export type CountryListItem = {
  country_id: string
  name: string
  source_count: number
  active_sources: number
  china_article_count: number
}

export function fetchCountries() {
  return get<{ countries: CountryListItem[] }>('/api/countries')
}

export type CountryDetail = {
  country_id: string
  name: string
  disclaimer: string
  media: Array<{
    source_id: string
    name: string
    active_status: string
    china_article_count: number
    language: string | null
    source_bucket?: string
    feed_scope?: string | null
  }>
  china_article_count: number
  sentiment_counts: Record<string, number>
  government_sentiment_counts?: Record<string, number>
  stance_counts: Record<string, number>
  topics_top: Array<{ label: string; count: number }>
  frames_top: Array<{ label: string; count: number }>
  recent_articles: Array<{
    article_id: string
    title: string | null
    url: string | null
    source_id: string
    sentiment: string | null
    published_at: string | null
  }>
}

export function fetchCountryDetail(id: string) {
  return get<CountryDetail>(`/api/countries/${encodeURIComponent(id)}`)
}

export type AlertItem = {
  id: string
  category: 'intelligence' | 'system'
  subcategory: string
  severity: string
  status?: string
  title: string
  summary: string
  detected_at: string
  evidence: Record<string, unknown>
}

export function fetchAlerts(params?: { window_start?: string; window_end?: string }) {
  const q = new URLSearchParams()
  if (params?.window_start) q.set('window_start', params.window_start)
  if (params?.window_end) q.set('window_end', params.window_end)
  const qs = q.toString()
  return get<{
    disclaimer: string
    intelligence: AlertItem[]
    system: AlertItem[]
    counts: { intelligence: number; system: number; high: number }
  }>(`/api/alerts${qs ? `?${qs}` : ''}`)
}

export function runAlerts() {
  return post<{ ok: boolean; created?: number; updated?: number }>('/api/alerts/run')
}

export function acknowledgeAlert(id: string) {
  return post<{ id: string; status: string }>(`/api/alerts/${id}/acknowledge`)
}

export function resolveAlert(id: string) {
  return post<{ id: string; status: string }>(`/api/alerts/${id}/resolve`)
}

export function closeAlert(id: string) {
  return post<{ id: string; status: string }>(`/api/alerts/${id}/close`)
}

export function fetchSystemStatus() {
  return get<{
    totals: Record<string, number>
    source_health: Array<Record<string, unknown>>
    notes: string[]
  }>('/api/system/status')
}
