/**
 * Unified Phase 7 Intelligence API Client & TypeScript Contracts.
 * Consumes decoupled FastAPI domain routers without recalculating formal statistics in the UI.
 */

const BASE = ''

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) {
    let detail = res.statusText
    try {
      const err = (await res.json()) as { detail?: string }
      if (err?.detail) detail = err.detail
    } catch {
      // ignore non-JSON error body
    }
    throw new Error(`${res.status} ${detail}`)
  }
  return res.json() as Promise<T>
}

async function postJson<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const err = (await res.json()) as { detail?: string }
      if (err?.detail) detail = err.detail
    } catch {
      // ignore
    }
    throw new Error(`${res.status} ${detail}`)
  }
  return res.json() as Promise<T>
}

export type GenericEvidenceRef = {
  type?: 'article' | 'event' | 'metric' | 'alert' | 'evidence' | string
  ref_id?: string
  article_id?: string
  evidence_id?: string
  label?: string
  quote?: string
  source_name?: string
  source_country?: string
  published_at?: string | null
}

export type AssessmentFinding = {
  title?: string
  statement?: string
  summary?: string
  classification?: 'Fact' | 'Inference' | 'Hypothesis' | 'Outlook' | string
  confidence?: string
  evidence_refs?: GenericEvidenceRef[]
  [key: string]: unknown
}

export type AssessmentResult = {
  task_type: string
  executive_summary: string
  key_findings: AssessmentFinding[]
  observations: AssessmentFinding[]
  interpretations: AssessmentFinding[]
  hypotheses: AssessmentFinding[]
  evidence_refs: GenericEvidenceRef[]
  supporting_metrics: Array<Record<string, unknown>>
  counter_evidence: Array<Record<string, unknown>>
  confidence: 'high' | 'medium' | 'low' | string
  confidence_note?: string
  limitations: string[]
  watch_items: Array<Record<string, unknown> | string>
  details?: Record<string, unknown>
  status: string
  validation_result?: Record<string, unknown>
  metadata?: Record<string, unknown>
}

export type ReportSection = {
  section_id: string
  title: string
  source_kind: 'llm_assessment' | 'deterministic_metrics' | 'hybrid' | string
  summary: string
  findings: AssessmentFinding[]
  evidence_refs: GenericEvidenceRef[]
  metrics: Array<Record<string, unknown>>
  visualizations: Array<Record<string, unknown>>
  limitations: string[]
  assessment_task_types: string[]
  status: string
}

export type ReportPackage = {
  report_id: string
  report_type: 'daily' | 'weekly' | 'monthly' | string
  period?: Record<string, unknown>
  period_start?: string | null
  period_end?: string | null
  generated_at?: string | null
  metric_snapshot_refs: string[]
  assessment_refs: Array<Record<string, unknown>>
  assessment_results: AssessmentResult[]
  sections: ReportSection[]
  evidence_refs: GenericEvidenceRef[]
  methodology?: Record<string, unknown>
  coverage?: Record<string, unknown>
  limitations: string[]
  generation_status: string
  validation_status: string
  validation_notes: string[]
  generation_metadata?: Record<string, unknown>
}

export type ReportListItem = {
  id: string
  report_type: string
  period: string
  schema_version: string | null
  created_at: string | null
  report_id: string
  generation_status: string | null
  validation_status: string | null
  article_count: number | null
}

export type StanceSummary = {
  target: string
  positive_count: number
  neutral_count: number
  negative_count: number
  unclassified_count: number
  classified_count: number
  positive_rate: number | null
  neutral_rate: number | null
  negative_rate: number | null
  stance_coverage_rate?: number | null
  denominator_note?: string
}

export type DashboardPayload = {
  meta: {
    period: string
    period_start?: string
    period_end?: string
    timezone?: string
    generated_at: string
    methodology_version: string
    taxonomy_version: string
    core_kpi: string
    report_id?: string
    generation_status?: string
    validation_status?: string
  }
  executive_overview: {
    article_count: number
    vs_yesterday?: { china_articles: number; delta: number } | null
    vs_7d_avg?: { china_articles: number; delta: number } | null
    reporting_countries: number
    reporting_sources: number
    connected_countries?: number
    active_sources?: number
    stance_coverage_rate: number | null
    stance_distribution: StanceSummary
  }
  executive_assessment: {
    status: string
    overall_situation: string
    key_findings: AssessmentFinding[]
    observations: AssessmentFinding[]
    interpretations: AssessmentFinding[]
    most_important_changes: Array<{ title: string; summary: string; kind?: string; href?: string }>
    watch_items: Array<Record<string, unknown> | string>
    evidence_refs: GenericEvidenceRef[]
    limitations: string[]
  }
  global_attention: {
    volume_trend: Array<{ date: string; china_articles: number }>
    countries: Array<{
      scope_id: string
      article_count: number
      positive_rate: number | null
      neutral_rate: number | null
      negative_rate: number | null
      unclassified_count: number
      stance_coverage_rate: number | null
    }>
    boards: Array<{
      scope_id: string
      label_zh?: string
      article_count: number
      positive_rate: number | null
      neutral_rate: number | null
      negative_rate: number | null
      stance_coverage_rate: number | null
    }>
    topics: Array<{
      scope_id: string
      label_zh?: string
      board_id?: string
      article_count: number
      positive_rate: number | null
      neutral_rate: number | null
      negative_rate: number | null
      stance_coverage_rate: number | null
    }>
    topic_overlap_note: string
  }
  key_developments: Array<{
    event_id: string
    title: string
    event_type: string | null
    event_time: string | null
    status: string | null
    importance_score: number | null
    overview_text?: string
    countries: string[]
    country_count: number
    source_count: number
    article_count: number
    representative_articles: Array<{
      article_id: string
      title: string | null
      country_id?: string | null
      source_id?: string | null
      published_at?: string | null
      stance?: string | null
    }>
  }>
  emerging_signals: {
    observed_facts: Array<Record<string, unknown>>
    analytical_inferences: Array<Record<string, unknown>>
  }
  daily_report_entry: {
    report_id?: string
    period: string
    generation_status?: string
    validation_status?: string
    chapter_count: number
    href: string
  }
  limitations: string[]
}

export type ArticleSummaryItem = {
  article_id: string
  title: string | null
  url: string | null
  source_id: string
  source_name: string
  source_country: string | null
  published_at: string | null
  language: string | null
  china_relevance_level: string | null
  sentiment_label: string
  stance_label: string
  stance_target: string
  stance_confidence: number | null
  expression_owner: string
  topics_v1: string[]
  narratives: Array<{ label: string; frame?: string | null; claim?: string }>
  event_ids: string[]
  evidence_count: number
  evidence_preview: EvidenceSegment[]
  analysis_schema_version: string | null
}

export type EvidenceSegment = {
  evidence_id: string
  article_id: string
  article_version_id: string | null
  text_span: string
  start_offset: number | null
  end_offset: number | null
  validated: boolean
  source_field: string
  analysis_task: string
  expression_owner: string
  source_name: string
  source_country: string | null
  published_at: string | null
}

export type ArticleDetailPayload = ArticleSummaryItem & {
  canonical_url: string | null
  content_excerpt: string
  content_length: number
  article_version_id: string | null
  evidence_segments: EvidenceSegment[]
  article_intelligence: Record<string, unknown> | null
  related_events: Array<{
    event_id: string
    title: string
    event_type: string | null
    event_time: string | null
  }>
  related_narratives: Array<{
    narrative_id?: string
    name?: string
    label?: string
    frame?: string | null
  }>
  data_source: string
  limitations: string[]
}

export type EvidenceLookupPayload = {
  resolved_by: string
  evidence_id: string
  article_id: string
  evidence: EvidenceSegment | null
  all_evidence_segments: EvidenceSegment[]
  article: ArticleDetailPayload
}

export type TopicsOverviewPayload = {
  meta: {
    period_start: string
    period_end: string
    days: number
    methodology_version: string
    taxonomy_version: string
    global_unique_article_count: number
    overlap_note: string
  }
  boards: Array<{
    scope_id: string
    label_zh?: string
    article_count: number
    positive_count: number
    neutral_count: number
    negative_count: number
    unclassified_count: number
    positive_rate: number | null
    neutral_rate: number | null
    negative_rate: number | null
    stance_coverage_rate: number | null
  }>
  topics: Array<{
    topic_id: string
    scope_id: string
    board_id?: string
    label_zh?: string
    article_count: number
    share_of_global: number
    prev_article_count: number
    delta: number
    positive_count: number
    neutral_count: number
    negative_count: number
    unclassified_count: number
    positive_rate: number | null
    neutral_rate: number | null
    negative_rate: number | null
    stance_coverage_rate: number | null
    change_signal?: Record<string, unknown> | null
  }>
  taxonomy_boards: Array<{ board_id: string; label_zh: string; topic_ids: string[] }>
}

export type TopicDetailPayload = {
  topic: {
    topic_id: string
    board_id: string
    label_zh: string
    article_count?: number
    positive_count?: number
    neutral_count?: number
    negative_count?: number
    unclassified_count?: number
    positive_rate?: number | null
    neutral_rate?: number | null
    negative_rate?: number | null
    stance_coverage_rate?: number | null
  }
  meta: {
    period_start: string
    period_end: string
    days: number
    overlap_note: string
  }
  trend: Array<{ date: string; article_count: number }>
  by_country: Array<{ country_id: string; article_count: number }>
  top_sources: Array<{ source_name: string; article_count: number }>
  top_narratives: Array<{ label: string; article_count: number }>
  related_events: Array<{
    event_id: string
    title: string
    event_type: string | null
    event_time: string | null
    topic_article_count: number
  }>
  articles: ArticleSummaryItem[]
  topic_assessment: AssessmentResult | null
}

export type CountryComparePayload = {
  meta: {
    period_start: string
    period_end: string
    days: number
    methodology_version: string
    taxonomy_version: string
    attribution_note: string
    stance_note: string
  }
  countries: Array<{
    country_id: string
    country_name: string
    article_count: number
    prev_article_count: number
    delta: number
    reporting_sources: number
    total_registered_sources: number
    small_sample_warning: boolean
    sample_note: string | null
    sentiment_counts: Record<string, number>
    stance: StanceSummary
    topics_top: Array<{ topic_id: string; article_count: number }>
    narratives_top: Array<{ label: string; article_count: number }>
    top_events: Array<{ event_id: string; title: string; article_count: number }>
    representative_articles: ArticleSummaryItem[]
  }>
  country_comparison_assessment: AssessmentResult | null
}

export type NarrativeItem = {
  narrative_id: string
  name: string
  core_claim: string
  main_frame: string | null
  trend_status: string
  related_topics: string[]
  related_countries: string[]
  article_count: number
  article_ids: string[]
  first_seen: string | null
  last_seen: string | null
  supporting_evidence: Array<{
    article_id: string
    title: string | null
    quote: string | null
    source_country: string | null
    published_at: string | null
  }>
  counter_evidence: Array<{
    article_id: string
    title: string | null
    quote: string | null
    source_country: string | null
    published_at: string | null
  }>
  source: string
}

export type NarrativesPayload = {
  meta: {
    period_start: string
    period_end: string
    days: number
    total: number
    non_coordination_note: string
  }
  narratives: NarrativeItem[]
  narrative_assessment: AssessmentResult | null
}

export type NarrativeDetailPayload = {
  meta: NarrativesPayload['meta']
  narrative: NarrativeItem
  articles: ArticleSummaryItem[]
}

export type SentimentStancePayload = {
  meta: {
    period_start: string
    period_end: string
    days: number
    methodology_version: string
    taxonomy_version: string
    stance_target: string
    rules: string[]
  }
  sentiment: {
    overall_counts: Record<string, number>
    by_country: Array<{ country_id: string; counts: Record<string, number>; total: number }>
    by_source: Array<{ source_name: string; counts: Record<string, number>; total: number }>
  }
  stance: {
    target: string
    global: Record<string, unknown>
    by_country: Array<Record<string, unknown>>
    by_source: Array<Record<string, unknown>>
    by_topic: Array<Record<string, unknown>>
    expression_owner_counts: Record<string, number>
  }
  history: Array<{
    date: string
    article_count: number
    sentiment_positive: number
    sentiment_neutral: number
    sentiment_negative: number
    sentiment_unknown: number
    stance_positive: number
    stance_neutral: number
    stance_negative: number
    stance_unclassified: number
  }>
  representative_articles: ArticleSummaryItem[]
  assessment: AssessmentResult | null
}

export type OutlookPayload = {
  meta: {
    period: string
    status: string
    disclaimer: string
  }
  executive_summary: string
  observations: AssessmentFinding[]
  interpretations: AssessmentFinding[]
  hypotheses: AssessmentFinding[]
  watchlist: Array<{
    id: string
    observation_object: string
    current_evidence: string
    possible_development: string
    trigger_condition: string
    alternative_scenario: string
    uncertainty: string
    classification: string
    related_events: string[]
    related_topics: string[]
    evidence_refs: GenericEvidenceRef[]
  }>
  evidence_refs: GenericEvidenceRef[]
  limitations: string[]
}

export type ArticlesPagePayload = {
  items: ArticleSummaryItem[]
  pagination: {
    page: number
    page_size: number
    total: number
    total_pages: number
  }
  sort: string
}

export function fetchDashboard(date?: string, trendDays = 14) {
  const qs = new URLSearchParams()
  if (date) qs.set('date', date)
  qs.set('trend_days', String(trendDays))
  return getJson<DashboardPayload>(`/api/dashboard?${qs.toString()}`)
}

export function fetchReportsList(reportType?: string, limit = 30) {
  const qs = new URLSearchParams({ limit: String(limit) })
  if (reportType) qs.set('report_type', reportType)
  return getJson<{ reports: ReportListItem[]; total: number }>(`/api/reports/list?${qs.toString()}`)
}

export function fetchDailyReportPackage(date?: string, fromSnapshot = false) {
  const qs = new URLSearchParams()
  if (date) qs.set('date', date)
  if (fromSnapshot) qs.set('from_snapshot', 'true')
  const q = qs.toString()
  return getJson<{ report_package: ReportPackage; period: string; schema_version: string }>(
    `/api/reports/daily/package${q ? `?${q}` : ''}`,
  )
}

export async function fetchDailyReportMarkdown(date?: string): Promise<string> {
  const qs = new URLSearchParams({ format: 'markdown' })
  if (date) qs.set('date', date)
  const res = await fetch(`${BASE}/api/reports/daily/package?${qs.toString()}`)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.text()
}

export function fetchAssessments(reportType = 'daily', period?: string) {
  const qs = new URLSearchParams({ report_type: reportType })
  if (period) qs.set('period', period)
  return getJson<{
    report_type: string
    period: string | null
    tasks: Array<{
      task_type: string
      title_zh: string
      prompt_version: string
      status: string
      result: AssessmentResult | null
    }>
    completed_count: number
    total_tasks: number
  }>(`/api/assessments?${qs.toString()}`)
}

export function runAssessmentTaskApi(taskType: string, opts: { period?: string; force?: boolean } = {}) {
  return postJson<{ task_type: string; period: string; status: string; result: AssessmentResult }>(
    `/api/assessments/${encodeURIComponent(taskType)}/run`,
    opts,
  )
}

export function fetchTopics(days = 30) {
  return getJson<TopicsOverviewPayload>(`/api/topics?days=${days}`)
}

export function fetchTopicDetail(topicId: string, days = 30) {
  return getJson<TopicDetailPayload>(`/api/topics/${encodeURIComponent(topicId)}?days=${days}`)
}

export function fetchCountriesCompare(countries: string[], days = 30) {
  const qs = new URLSearchParams({ countries: countries.join(','), days: String(days) })
  return getJson<CountryComparePayload>(`/api/countries/compare?${qs.toString()}`)
}

export function fetchNarratives(days = 30) {
  return getJson<NarrativesPayload>(`/api/narratives?days=${days}`)
}

export function fetchNarrativeDetail(narrativeId: string, days = 30) {
  return getJson<NarrativeDetailPayload>(
    `/api/narratives/${encodeURIComponent(narrativeId)}?days=${days}`,
  )
}

export function fetchSentimentStance(days = 30) {
  return getJson<SentimentStancePayload>(`/api/sentiment-stance?days=${days}`)
}

export function fetchOutlook(date?: string) {
  const q = date ? `?date=${encodeURIComponent(date)}` : ''
  return getJson<OutlookPayload>(`/api/outlook${q}`)
}

export function fetchArticles(params: {
  start?: string
  end?: string
  country?: string
  source?: string
  topic?: string
  event_id?: string
  narrative?: string
  sentiment?: string
  stance?: string
  q?: string
  page?: number
  page_size?: number
}) {
  const qs = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && String(v).trim() !== '') {
      qs.set(k, String(v))
    }
  })
  return getJson<ArticlesPagePayload>(`/api/articles?${qs.toString()}`)
}

export function fetchArticleDetail(articleId: string) {
  return getJson<ArticleDetailPayload>(`/api/articles/${encodeURIComponent(articleId)}`)
}

export function fetchEvidenceLookup(evidenceId: string) {
  return getJson<EvidenceLookupPayload>(`/api/evidence/${encodeURIComponent(evidenceId)}`)
}
