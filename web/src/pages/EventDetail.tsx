import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { fetchEventDetail, type EventDetail } from '../api'
import type { AssessmentResult, EvidenceSegment } from '../apiV2'
import { DualMap } from '../components/DualMap'
import { useEvidenceDrawer } from '../components/EvidenceContext'
import {
  ClassificationBadge,
  ErrorState,
  fmtDateTime,
  LoadingState,
  SampleSizeBadge,
  SectionCard,
} from '../components/StateBlocks'
import '../components/intel.css'

type EnrichedEventDetail = EventDetail & {
  event_timeline?: Array<{
    event_time: string | null
    time_status: 'known' | 'unknown'
    label: string
    kind: string
    note?: string | null
  }>
  coverage_timeline?: Array<{
    published_at: string | null
    kind: string
    article_id: string
    title: string | null
    country_id: string | null
  }>
  cross_country_interpretation?: Array<{
    country_id: string
    article_count: number
    media_count: number
    sentiment_counts: Record<string, number>
    stance_counts: Record<string, number>
    top_frames: string[]
    sample_warning: boolean
    representative_articles: Array<{
      article_id: string
      title: string | null
      source_name: string
      published_at: string | null
      stance: string | null
      sentiment: string | null
    }>
  }>
  evidence_segments?: EvidenceSegment[]
  event_assessment?: AssessmentResult | null
}

type ViewTab = 'overview' | 'timeline' | 'coverage' | 'cross_country' | 'assessment' | 'evidence'

export function EventDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { openEvidence } = useEvidenceDrawer()
  const [data, setData] = useState<EnrichedEventDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [tab, setTab] = useState<ViewTab>('overview')

  useEffect(() => {
    if (!id) return
    setError(null)
    fetchEventDetail(id)
      .then((res) => setData(res as EnrichedEventDetail))
      .catch((e: Error) => setError(e.message))
  }, [id])

  if (error) return <ErrorState error={error} />
  if (!data) return <LoadingState label="加载事件深度分析…" />

  const e = data.event
  const where = data.views.where
  const who = data.views.who_reports
  const how = data.views.how_they_frame
  const cross = data.cross_country_interpretation || []
  const evTimeline = data.event_timeline || []
  const covTimeline = data.coverage_timeline || []
  const evSegs = data.evidence_segments || []
  const assess = data.event_assessment

  return (
    <div className="intel-page">
      <p className="crumb" style={{ margin: 0 }}>
        <Link to="/events">Events</Link> / {e.id}
      </p>

      {/* A. Event Overview */}
      <SectionCard
        title={e.title}
        subtitle={e.summary || undefined}
        right={<span className="intel-badge">{e.status}</span>}
      >
        <div className="intel-chip-row">
          <span className="intel-badge">Event ID: {e.id}</span>
          <span className="intel-badge">类型: {e.event_type ?? '—'}</span>
          <span className="intel-badge">
            事件时间 (event_time): {e.event_time ? fmtDateTime(e.event_time) : '时间未知'}
          </span>
          <span className="intel-badge">重要度: {e.importance_score ?? '—'}</span>
          <span className="intel-badge">文章数: {data.metrics?.article_count ?? 0}</span>
          <span className="intel-badge">涉及国家: {who.countries.map((c) => c.country_id).join(', ') || '—'}</span>
        </div>
        {data.participants.length > 0 && (
          <p className="muted small" style={{ marginTop: '0.5rem' }}>
            主要参与方 (Main Actors)：
            {data.participants.map((p) => p.participant_name || p.participant_id).join('、')}
          </p>
        )}
      </SectionCard>

      <div className="seg" role="tablist">
        {(
          [
            ['overview', '地理与叙事'],
            ['timeline', 'B · 事件时间线 (event_time)'],
            ['coverage', 'C · 媒体报道'],
            ['cross_country', 'D · 跨国报道差异'],
            ['assessment', 'E · 事件研判'],
            ['evidence', `F · 证据片段 (${evSegs.length})`],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={tab === key}
            className={tab === key ? 'active' : ''}
            onClick={() => setTab(key)}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === 'overview' && (
        <div className="intel-grid-2">
          <SectionCard title="事件地理 (Where)">
            {where.note && <p className="callout">{where.note}</p>}
            {where.locations.length === 0 ? (
              <p className="muted small">无明确物理发生地（政策/声明类事件不以报道国替代发生地）。</p>
            ) : (
              <ul>
                {where.locations.map((loc, i) => (
                  <li key={i}>
                    <strong>{loc.location_type}</strong> — {loc.label ?? loc.country_id ?? '—'}
                  </li>
                ))}
              </ul>
            )}
            <DualMap
              mode="event_geography"
              eventPins={where.locations
                .filter((l) => l.lat != null && l.lon != null)
                .map((l) => ({
                  event_id: e.id,
                  title: e.title,
                  location_type: l.location_type,
                  lat: l.lat as number,
                  lon: l.lon as number,
                  layer: 'event_geography',
                }))}
            />
          </SectionCard>

          <SectionCard title="叙事框架 (How they frame)">
            {how.narratives.length === 0 ? (
              <p className="muted small">暂无关联叙事簇。</p>
            ) : (
              how.narratives.map((n) => (
                <div key={n.id} className="intel-card" style={{ marginBottom: '0.6rem' }}>
                  <strong>{n.label}</strong>{' '}
                  {n.frame_id && <span className="intel-badge">{n.frame_id}</span>}
                  {n.summary && <p className="small">{n.summary}</p>}
                  <div className="intel-chip-row">
                    {n.evidence.slice(0, 3).map((ev, i) => (
                      <button
                        key={i}
                        type="button"
                        className="intel-ev-btn"
                        onClick={() => openEvidence(ev.article_id)}
                      >
                        证据: {(ev.title || ev.article_id).slice(0, 24)}
                      </button>
                    ))}
                  </div>
                </div>
              ))
            )}
          </SectionCard>
        </div>
      )}

      {tab === 'timeline' && (
        <SectionCard
          title="B · Event Evolution（严格使用 event_time）"
          subtitle="event_time 未知时明确标示「时间未知」，绝不以文章 published_at 替代事件发生时间。"
        >
          <ul className="event-list">
            {evTimeline.map((item, i) => (
              <li key={i}>
                <strong>
                  {item.event_time ? fmtDateTime(item.event_time) : '时间未知 (event_time=null)'}
                </strong>{' '}
                — {item.label}
                {item.note && <div className="muted small">{item.note}</div>}
              </li>
            ))}
          </ul>
          <h4 style={{ marginTop: '1rem' }}>媒体报道发布序列（published_at，独立于事件发生时间）</h4>
          <ul className="event-list">
            {covTimeline.map((item, i) => (
              <li key={i}>
                <span className="muted small">{fmtDateTime(item.published_at)}</span> ·{' '}
                <strong>{item.country_id || '—'}</strong> ·{' '}
                <button
                  type="button"
                  className="linkish"
                  onClick={() => openEvidence(item.article_id)}
                >
                  {item.title || item.article_id}
                </button>
              </li>
            ))}
          </ul>
        </SectionCard>
      )}

      {tab === 'coverage' && (
        <SectionCard
          title="C · Media Coverage（国家 → 媒体 → 代表文章）"
          subtitle="信源所属国不等同于政府官方立场"
        >
          <DualMap mode="reporting_source" eventPins={[]} reportingPins={who.reporting_map} />
          {who.countries.map((c) => (
            <div key={c.country_id} className="intel-card" style={{ marginTop: '0.75rem' }}>
              <h4>
                {c.country_id} <span className="muted small">({c.article_count} 篇)</span>
              </h4>
              {c.media.map((m) => (
                <div key={m.source_id} style={{ marginBottom: '0.5rem' }}>
                  <strong>{m.source_name}</strong>{' '}
                  <span className="muted small">({m.article_count})</span>
                  <ul className="event-list">
                    {m.articles.map((a) => (
                      <li key={a.article_id}>
                        <button
                          type="button"
                          className="linkish"
                          onClick={() => openEvidence(a.article_id)}
                        >
                          {a.title || a.article_id}
                        </button>
                        <span className="meta">
                          {fmtDateTime(a.published_at)} · 情感 {a.sentiment || '—'} · 立场 {a.stance || '—'}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          ))}
        </SectionCard>
      )}

      {tab === 'cross_country' && (
        <SectionCard
          title="D · Cross-country Interpretation（跨国报道差异）"
          subtitle="对比各国媒体报道量、叙事框架、情感与对华立场差异"
        >
          {cross.length === 0 ? (
            <p className="muted small">暂无跨国对比样本。</p>
          ) : (
            <div className="intel-grid-2">
              {cross.map((c) => (
                <div key={c.country_id} className="intel-card">
                  <div className="intel-header-row">
                    <h4>{c.country_id}</h4>
                    <SampleSizeBadge count={c.article_count} threshold={3} />
                  </div>
                  <div className="muted small">
                    {c.article_count} 篇文章 · {c.media_count} 家媒体
                  </div>
                  <p className="small">
                    <strong>主要框架：</strong> {c.top_frames.join('、') || '—'}
                  </p>
                  <p className="small">
                    <strong>情感分布：</strong> {JSON.stringify(c.sentiment_counts)}
                  </p>
                  <p className="small">
                    <strong>对华立场：</strong> {JSON.stringify(c.stance_counts)}
                  </p>
                  <div className="intel-chip-row">
                    {c.representative_articles.map((a) => (
                      <button
                        key={a.article_id}
                        type="button"
                        className="intel-ev-btn"
                        onClick={() => openEvidence(a.article_id)}
                      >
                        {(a.title || a.article_id).slice(0, 24)}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </SectionCard>
      )}

      {tab === 'assessment' && (
        <SectionCard title="E · Event Assessment（事件深度研判）">
          {!assess ? (
            <p className="muted small">
              当前尚未生成 `event_analysis` 研判结果；可在报告中心运行 V2 研判后自动展示。
            </p>
          ) : (
            <>
              <div className="intel-banner" style={{ marginBottom: '0.75rem' }}>
                {assess.executive_summary}
              </div>
              {assess.key_findings.map((f, idx) => (
                <div key={idx} className="intel-finding-item">
                  <div className="intel-header-row">
                    <strong>{f.title || `研判要点 ${idx + 1}`}</strong>
                    <ClassificationBadge kind={f.classification} />
                  </div>
                  <p className="small">{f.statement || f.summary}</p>
                </div>
              ))}
            </>
          )}
        </SectionCard>
      )}

      {tab === 'evidence' && (
        <SectionCard title="F · Supporting Evidence Segments（可追溯原文证据）">
          {evSegs.length === 0 ? (
            <p className="muted small">暂无文章级已核验原文证据片段。</p>
          ) : (
            evSegs.map((ev) => (
              <div key={ev.evidence_id} className="intel-card" style={{ marginBottom: '0.6rem' }}>
                <div className="intel-header-row">
                  <span className="muted small">
                    {ev.source_country || '—'} · {ev.source_name} · {fmtDateTime(ev.published_at)}
                  </span>
                  <button
                    type="button"
                    className="intel-ev-btn"
                    onClick={() => openEvidence(ev.evidence_id)}
                  >
                    在原文中定位 →
                  </button>
                </div>
                <p style={{ margin: '0.4rem 0 0' }}>
                  <mark className="intel-highlight">{ev.text_span}</mark>
                </p>
              </div>
            ))
          )}
        </SectionCard>
      )}
    </div>
  )
}
