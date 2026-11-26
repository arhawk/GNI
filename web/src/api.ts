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

export type V1StatRow = {
  period_start: string
  period_end: string
  scope_type: 'GLOBAL' | 'COUNTRY' | 'BOARD' | 'TOPIC' | string
  scope_id: string
  label_zh?: string
  board_id?: string
  article_count: number
  positive_count: number
  neutral_count: number
  negative_count: number
  unclassified_count: number
  classified_count?: number
  positive_rate: number | null
  neutral_rate: number | null
  negative_rate: number | null
  stance_coverage_rate: number | null
  methodology_version?: string
  taxonomy_version?: string
  analysis_version?: string
  article_ids?: string[]
  generated_at?: string
}

export type V1StatsByScope = {
  global: V1StatRow | null
  countries: V1StatRow[]
  boards: V1StatRow[]
  topics: V1StatRow[]
}

export type ReportWindowSpec = {
  report_type: string
  period: string
  window_mode: 'calendar_day' | 'rolling_7d' | 'calendar_month' | 'rolling_30d' | string
  timezone: string
  period_start: string
  period_end: string
  prev_period_start: string
  prev_period_end: string
  effective_prev_start: string
  effective_prev_end: string
  is_partial_period: boolean
  elapsed_days: number
  total_days: number
  comparison_note: string
}

export type ReportQualityGateIssue = {
  code: string
  message: string
}

export type ReportQualityGate = {
  gate_version: string
  status: 'passed' | 'passed_with_warnings' | 'blocked'
  blocking_issues: ReportQualityGateIssue[]
  warnings: ReportQualityGateIssue[]
  metrics?: {
    article_count?: number
    stance_coverage_rate?: number | null
    is_partial_period?: boolean
  }
  checked_at?: string
}

export type ReportVisualizations = {
  trend_line?: {
    type: string
    title: string
    caption?: string
    series: Array<{ label: string; article_count: number; is_partial?: boolean }>
  }
  country_bar?: {
    type: string
    title: string
    caption?: string
    items: Array<{
      country_code: string
      country_name: string
      article_count: number
      positive_count: number
      neutral_count: number
      negative_count: number
      unclassified_count: number
      stance_coverage_rate?: number | null
    }>
  }
  topic_delta?: {
    type: string
    title: string
    caption?: string
    items: Array<{
      topic: string
      article_count: number
      prev_article_count: number
      delta: number
    }>
  }
  stance_stacked?: {
    type: string
    title: string
    caption?: string
    data: {
      article_count: number
      positive_count: number
      neutral_count: number
      negative_count: number
      unclassified_count: number
      positive_rate?: number | null
      neutral_rate?: number | null
      negative_rate?: number | null
      stance_coverage_rate?: number | null
    }
  }
  event_timeline?: {
    type: string
    title: string
    caption?: string
    items: Array<{
      event_id: string
      title: string
      event_time?: string | null
      article_count: number
      countries?: string[]
    }>
  }
}

export type CanonicalAssessment = {
  task_type: string
  task_version?: string
  report_type?: string
  period?: string
  evidence_hash?: string | null
  generated_at?: string | null
  model_version?: string | null
  prompt_version?: string | null
  schema_version?: string
  methodology_version?: string
  taxonomy_version?: string
  executive_summary: string
  key_findings: NarrativeFinding[]
  observations?: NarrativeFinding[]
  interpretations?: NarrativeFinding[]
  hypotheses?: NarrativeFinding[]
  evidence_refs?: EvidenceRef[]
  limitations: string[]
  watch_items?: OutlookSignalItem[]
  details?: {
    important_changes?: string[]
    main_drivers?: string[]
    event_interpretations?: EventInterpretation[]
    topic_deep_dives?: TopicTrendInterpretation[]
    topic_shifts?: TopicTrendInterpretation[]
    cross_country_comparisons?: CrossCountryInterpretation[]
    country_differences?: CrossCountryInterpretation[]
    stance_observations?: StanceInterpretationItem[]
    outlook_signals?: OutlookSignalItem[]
    follow_up_questions?: string[]
    [k: string]: unknown
  }
  status: string
  validation_result?: Record<string, unknown>
  metadata?: Record<string, unknown>
}

export type AssessmentsMeta = {
  status: 'rule_only' | 'completed' | 'partial' | 'needs_review' | 'failed' | string
  engine?: string
  orchestrator_version?: string
  profile_version?: string
  report_type?: string
  period?: string
  evidence_hash?: string
  stale?: boolean
  task_statuses: Record<
    string,
    {
      title_zh?: string
      prompt_version?: string
      model_version?: string | null
      status: string
      stale?: boolean
      cached?: boolean
      error_message?: string | null
      validation?: Record<string, unknown> | null
      generated_at?: string | null
    }
  >
  meta: {
    completed_tasks: number
    failed_tasks: number
    needs_review_tasks: number
    total_tasks: number
    model_versions: string[]
    prompt_versions: Record<string, string>
  }
}

export type DailyReport = {
  report_type: string
  schema_version?: string
  methodology_version?: string
  taxonomy_version?: string
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
  window_spec?: ReportWindowSpec
  quality_gate?: ReportQualityGate
  visualizations?: ReportVisualizations
  report_package?: import('./apiV2').ReportPackage
  assessments?: Record<string, CanonicalAssessment>
  assessments_meta?: AssessmentsMeta
  narratives?: {
    executive?: string
    risk?: string
    coverage?: string
    tone?: string
    signals?: string
    quality?: string
  }
  sections: {
    v1_stats?: V1StatsByScope
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
      judgment_text?: string
      confidence?: 'high' | 'medium' | 'low' | 'unavailable' | string
      risk_banner?: {
        has_high_risk: boolean
        high_risk_event_count: number
        text: string
      }
    }
    overview_stats?: {
      connected_countries?: string[]
      media_type_counts?: Record<string, number>
      media_type_counts_zh?: Record<string, number>
      ingest?: Record<string, number>
      crawl_summary?: Record<string, number>
      sentiment_tech?: {
        score_mean?: number | null
        score_mean_yesterday?: number | null
        vs_yesterday_delta?: number | null
        n_scored?: number
        note?: string
      }
      narrative_split?: {
        official_topics_top?: Array<{ label: string; count: number; share: number }>
        media_topics_top?: Array<{ label: string; count: number; share: number }>
        note?: string
      }
      sentiment_by_media_type?: Record<string, Record<string, number>>
    }
    major_events: Array<{
      event_id: string
      title: string
      importance_score?: number | null
      china_signal_score?: number | null
      list_tier?: string
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
      sentiment_label?: string
      primary_country?: string | null
      source_bucket?: string
      source_bucket_zh?: string
      narrative_labels?: string[]
      risk_level?: string
      sectors?: Array<{ id: string; label: string }>
      sector_ids?: string[]
      anomaly?: { flagged: boolean; reasons: string[] }
      timeline?: Array<Record<string, unknown>>
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
    secondary_events?: Array<{
      event_id: string
      title: string
      china_signal_score?: number | null
      risk_level?: string
      href?: string
    }>
    orphan_headlines?: Array<{
      article_id: string
      title: string
      country_id?: string | null
      risk_level?: string
      sectors?: Array<{ id: string; label: string }>
    }>
    anomalies?: Array<Record<string, unknown>>
    ops?: {
      follow_ups?: Array<{
        event_id?: string
        title?: string
        action?: string
        href?: string
      }>
      crawl_status?: Array<{
        source_id: string
        name?: string
        country_id?: string | null
        status: string
        success_count?: number
        failure_count?: number
        last_error?: string | null
      }>
      note?: string
    }
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
      taxonomy_confidence?: string
      note?: string
    }
    tone: {
      note?: string
      min_n?: number
      overall_sentiment_counts: Record<string, number>
      overall_stance_counts: Record<string, number>
      by_country: Array<{
        country_id: string
        n: number
        status?: 'ok' | 'unavailable' | 'no_sample' | string
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
  methodology_version?: string
  taxonomy_version?: string
  period: string
  period_start?: string
  period_end?: string
  generated_at: string
  disclaimer: string
  generator?: string
  article_count?: number
  sections: Record<string, unknown>
  narratives?: Record<string, string>
  assessments?: Record<string, CanonicalAssessment>
  assessments_meta?: AssessmentsMeta
  validation?: { ok: boolean; checks?: Array<{ name: string; ok: boolean }>; errors?: string[] }
  window_spec?: ReportWindowSpec
  quality_gate?: ReportQualityGate
  visualizations?: ReportVisualizations
  report_package?: import('./apiV2').ReportPackage
}

export type EvidenceRef = {
  type: 'metric' | 'article' | 'event' | 'alert' | string
  ref_id: string
  label?: string
  url?: string | null
}

export type NarrativeFinding = {
  title: string
  conclusion: string
  classification: 'Fact' | 'Inference' | 'Hypothesis' | string
  evidence_refs: EvidenceRef[]
  reasoning?: string
  confidence: 'high' | 'medium' | 'low' | string
  limitations?: string[]
  needs_review?: boolean
  validation_notes?: string[]
}

export type EventInterpretation = {
  event_id: string
  title: string
  background?: string
  what_happened?: string
  event_actual_changes?: string
  coverage_attention_changes?: string
  country_followup_timing?: string
  country_differences?: string
  media_viewpoints?: string[]
  current_status?: string
  why_it_matters?: string
  what_to_monitor?: string[]
  evidence_refs?: EvidenceRef[]
  confidence?: string
  limitations?: string[]
  needs_review?: boolean
}

export type TopicTrendInterpretation = {
  topic_id: string
  topic_label?: string
  attention_change?: string
  stance_change?: string
  topic_structure_change?: string
  drivers?: string[]
  persistence?: 'short_term' | 'ongoing' | 'insufficient_history' | string
  evidence_refs?: EvidenceRef[]
  confidence?: string
  limitations?: string[]
  needs_review?: boolean
}

export type CountryFrameEntry = {
  country_id: string
  main_frame?: string
  unique_angle?: string
  sample_note?: string
  evidence_refs?: EvidenceRef[]
}

export type CrossCountryInterpretation = {
  subject_type?: string
  subject_id?: string
  subject_label?: string
  common_focus?: string
  country_frames?: CountryFrameEntry[]
  major_differences?: string
  emerging_or_shifting?: string
  insufficient_sample_countries?: string[]
  evidence_refs?: EvidenceRef[]
  confidence?: string
  needs_review?: boolean
}

export type StanceInterpretationItem = {
  scope_type?: string
  scope_id?: string
  scope_label?: string
  rate_vs_count_note?: string
  drivers?: string[]
  coverage_limitation?: string
  evidence_refs?: EvidenceRef[]
  confidence?: string
  needs_review?: boolean
}

export type OutlookSignalItem = {
  signal: string
  evidence_refs?: EvidenceRef[]
  reasoning?: string
  confidence?: string
  what_to_monitor?: string[]
  potential_trigger?: string
  uncertainty?: string
  needs_review?: boolean
}

export function analyzeReport<T = DailyReport | PeriodReport>(
  reportType: 'daily' | 'weekly' | 'monthly',
  params?: {
    period?: string
    tasks?: string[]
    force?: boolean
    profile?: 'core' | 'full'
    save_snapshot?: boolean
  },
) {
  return post<T>(`/api/reports/${reportType}/analyze`, {
    period: params?.period ?? null,
    tasks: params?.tasks ?? null,
    force: Boolean(params?.force),
    profile: params?.profile ?? null,
    save_snapshot: Boolean(params?.save_snapshot),
  })
}

export type ReportCalendarDay = {
  date: string
  total_articles: number
  china_articles: number
}

export type ReportCalendarResponse = {
  month: string
  timezone: string
  days: ReportCalendarDay[]
}

export function fetchReportCalendar(month?: string) {
  const q = month ? `month=${encodeURIComponent(month)}` : ''
  return get<ReportCalendarResponse>(`/api/reports/calendar${q ? `?${q}` : ''}`)
}

export function fetchWeeklyReport(end?: string) {
  const q = end ? `end=${encodeURIComponent(end)}` : ''
  return get<PeriodReport>(`/api/reports/weekly${q ? `?${q}` : ''}`)
}

export function fetchMonthlyReport(opts?: string | { month?: string; end?: string }) {
  const params = new URLSearchParams()
  if (typeof opts === 'string' && opts) {
    params.set('month', opts)
  } else if (opts && typeof opts === 'object') {
    if (opts.end) params.set('end', opts.end)
    else if (opts.month) params.set('month', opts.month)
  }
  const q = params.toString()
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

export type TraceArticle = {
  article_id: string
  published_at: string | null
  source_country: string | null
  source_id: string
  source_name: string
  title: string | null
  url: string | null
  stance_label: 'Positive' | 'Neutral' | 'Negative' | 'Unclassified' | string
  stance_confidence: number | null
  stance_evidence: Array<{
    quote?: string
    span_text?: string
    start_offset?: number | null
    end_offset?: number | null
  }>
  topics_v1: string[]
}

export async function fetchArticleTrace(articleIds: string[], limit = 30) {
  const res = await fetch('/api/articles/trace', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ article_ids: articleIds.slice(0, limit), limit }),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}: /api/articles/trace`)
  return (await res.json()) as { articles: TraceArticle[] }
}

export * from './apiV2'
