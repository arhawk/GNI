import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchEvidenceLookup, type EvidenceLookupPayload } from '../apiV2'
import { fmtDateTime, StanceBadge } from './StateBlocks'
import './intel.css'

function HighlightedExcerpt({
  text,
  startOffset,
  endOffset,
  span,
}: {
  text: string
  startOffset?: number | null
  endOffset?: number | null
  span?: string | null
}) {
  if (!text) {
    return <p className="muted small">系统未保存原文正文，仅展示已核验的证据片段。</p>
  }
  if (
    typeof startOffset === 'number' &&
    typeof endOffset === 'number' &&
    startOffset >= 0 &&
    endOffset > startOffset &&
    endOffset <= text.length
  ) {
    return (
      <div className="intel-excerpt">
        {text.slice(0, startOffset)}
        <mark className="intel-highlight">{text.slice(startOffset, endOffset)}</mark>
        {text.slice(endOffset)}
      </div>
    )
  }
  if (span && text.includes(span)) {
    const idx = text.indexOf(span)
    return (
      <div className="intel-excerpt">
        {text.slice(0, idx)}
        <mark className="intel-highlight">{span}</mark>
        {text.slice(idx + span.length)}
      </div>
    )
  }
  return <div className="intel-excerpt">{text}</div>
}

export function EvidenceDrawer({
  evidenceId,
  onClose,
}: {
  evidenceId: string
  onClose: () => void
}) {
  const [data, setData] = useState<EvidenceLookupPayload | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchEvidenceLookup(evidenceId)
      .then((res) => {
        if (!cancelled) setData(res)
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [evidenceId])

  const art = data?.article
  const ev = data?.evidence

  return (
    <div className="intel-drawer-backdrop" onClick={onClose} role="dialog" aria-label="证据追溯抽屉">
      <div className="intel-drawer-panel" onClick={(e) => e.stopPropagation()}>
        <div className="intel-header-row">
          <div>
            <strong>原文证据追溯</strong>
            <div className="muted small">Ref: {evidenceId}</div>
          </div>
          <button type="button" className="intel-btn" onClick={onClose}>
            关闭
          </button>
        </div>

        {loading && <p className="muted">定位原文与证据偏移中…</p>}
        {error && <p className="error">无法定位证据：{error}</p>}

        {art && (
          <>
            <div className="intel-card">
              <h3 style={{ marginBottom: '0.35rem' }}>{art.title || art.article_id}</h3>
              <div className="muted small">
                {art.source_country || '—'} · {art.source_name} · 发布于 {fmtDateTime(art.published_at)} (published_at)
              </div>
              <div className="intel-chip-row">
                <span className="intel-badge">情感: {art.sentiment_label}</span>
                <StanceBadge label={art.stance_label} />
                <span className="intel-badge">
                  立场归属: {art.expression_owner === 'quoted_actor' ? '引述对象 (quoted_actor)' : art.expression_owner}
                </span>
                {art.article_version_id && (
                  <span className="intel-badge">版本: {art.article_version_id.slice(0, 8)}</span>
                )}
              </div>
              <div className="intel-chip-row" style={{ marginTop: '0.55rem' }}>
                <Link to={`/articles/${art.article_id}`} className="intel-btn primary" onClick={onClose}>
                  打开完整文章页
                </Link>
                {art.url && (
                  <a href={art.url} target="_blank" rel="noreferrer" className="intel-btn">
                    访问原文链接 ↗
                  </a>
                )}
              </div>
            </div>

            {ev && (
              <div className="intel-card">
                <h4>定位证据片段 ({ev.evidence_id})</h4>
                <p style={{ margin: '0.3rem 0' }}>
                  <mark className="intel-highlight">{ev.text_span}</mark>
                </p>
                <div className="muted small">
                  任务: {ev.analysis_task} · 核验: {ev.validated ? '已核验偏移' : '摘录匹配'}
                  {ev.start_offset != null && ev.end_offset != null
                    ? ` · Offset [${ev.start_offset}, ${ev.end_offset})`
                    : ''}
                </div>
              </div>
            )}

            <div>
              <h4>原文上下文（高亮证据片段）</h4>
              <HighlightedExcerpt
                text={art.content_excerpt}
                startOffset={ev?.start_offset}
                endOffset={ev?.end_offset}
                span={ev?.text_span}
              />
            </div>

            {art.limitations.length > 0 && (
              <div className="intel-banner intel-banner-warn">
                <strong>数据来源与限制：</strong> {art.limitations.join(' ')}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
