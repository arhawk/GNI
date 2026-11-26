import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { fetchArticleDetail, type ArticleDetailPayload } from '../apiV2'
import {
  ErrorState,
  fmtDateTime,
  LoadingState,
  PartialDataBanner,
  SectionCard,
  StanceBadge,
} from '../components/StateBlocks'
import '../components/intel.css'

export function ArticleDetailPage() {
  const { id } = useParams<{ id: string }>()
  const [data, setData] = useState<ArticleDetailPayload | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!id) return
    setLoading(true)
    setError(null)
    fetchArticleDetail(id)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [id])

  if (loading) return <LoadingState label="加载文章详情与原文证据…" />
  if (error) return <ErrorState error={error} />
  if (!data) return null

  return (
    <div className="intel-page">
      <p className="crumb" style={{ margin: 0 }}>
        <Link to="/explorer">Evidence & Article Explorer</Link> / {data.article_id}
      </p>

      <SectionCard
        title={data.title || data.article_id}
        subtitle={`${data.source_country || '—'} · ${data.source_name} · 发布于 ${fmtDateTime(data.published_at)} (published_at)`}
        right={
          data.url ? (
            <a href={data.url} target="_blank" rel="noreferrer" className="intel-btn primary">
              查看原始链接 ↗
            </a>
          ) : undefined
        }
      >
        <div className="intel-chip-row">
          <span className="intel-badge">Article ID: {data.article_id}</span>
          <span className="intel-badge">情感: {data.sentiment_label}</span>
          <StanceBadge label={data.stance_label} />
          <span className="intel-badge">Target: {data.stance_target}</span>
          <span className="intel-badge">
            立场归属: {data.expression_owner === 'quoted_actor' ? '引述对象 (quoted_actor)' : data.expression_owner}
          </span>
          {data.analysis_schema_version && (
            <span className="intel-badge">分析版本: {data.analysis_schema_version}</span>
          )}
        </div>

        {data.topics_v1.length > 0 && (
          <div className="intel-chip-row" style={{ marginTop: '0.5rem' }}>
            {data.topics_v1.map((t) => (
              <Link key={t} to={`/topics?t=${encodeURIComponent(t)}`} className="intel-ev-btn">
                议题: {t}
              </Link>
            ))}
          </div>
        )}
      </SectionCard>

      {data.limitations.length > 0 && (
        <PartialDataBanner message={`数据来源与限制：${data.limitations.join(' ')}`} />
      )}

      <SectionCard title={`Evidence Segments（可追溯原文证据片段 · ${data.evidence_segments.length}）`}>
        {data.evidence_segments.length === 0 ? (
          <p className="muted small">该文章暂无结构化原文证据偏移记录。</p>
        ) : (
          data.evidence_segments.map((ev) => (
            <div key={ev.evidence_id} className="intel-card" style={{ marginBottom: '0.6rem' }}>
              <div className="muted small">
                {ev.evidence_id} · 任务：{ev.analysis_task} · 核验：
                {ev.validated ? '已核验偏移' : '摘录匹配'}
                {ev.start_offset != null && ev.end_offset != null
                  ? ` · Offset [${ev.start_offset}, ${ev.end_offset})`
                  : ''}
              </div>
              <p style={{ margin: '0.35rem 0 0' }}>
                <mark className="intel-highlight">{ev.text_span}</mark>
              </p>
            </div>
          ))
        )}
      </SectionCard>

      <div className="intel-grid-2">
        <SectionCard title="关联事件 (Related Events)">
          {data.related_events.length === 0 ? (
            <p className="muted small">暂未关联事件</p>
          ) : (
            <ul className="event-list">
              {data.related_events.map((e) => (
                <li key={e.event_id}>
                  <Link to={`/events/${e.event_id}`}>{e.title}</Link>
                  <span className="meta">
                    {e.event_time ? fmtDateTime(e.event_time) : '时间未知'}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </SectionCard>

        <SectionCard title="关联叙事 (Related Narratives)">
          {data.related_narratives.length === 0 ? (
            <p className="muted small">暂无关联叙事</p>
          ) : (
            <ul className="event-list">
              {data.related_narratives.map((n, i) => (
                <li key={i}>
                  <strong>{n.name || n.label}</strong>
                  {n.frame && <span className="meta">{n.frame}</span>}
                </li>
              ))}
            </ul>
          )}
        </SectionCard>
      </div>

      <SectionCard
        title="系统保存的合法文本摘录 (Relevant Content)"
        subtitle={`数据来源：${data.data_source} · 总字符数 ${data.content_length}`}
      >
        {data.content_excerpt ? (
          <div className="intel-excerpt">{data.content_excerpt}</div>
        ) : (
          <p className="muted small">无正文摘录。</p>
        )}
      </SectionCard>
    </div>
  )
}
