import { useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchArticleTrace, type EvidenceRef, type TraceArticle } from '../../api'
import { EvidenceTraceTable } from '../tables'
import './narrative.css'

function metricHref(refId: string): string | null {
  if (!refId.startsWith('metric:')) return null
  const parts = refId.split(':')
  const scopeType = parts[1]
  const scopeId = parts[2]
  if (scopeType === 'COUNTRY' && scopeId) return `/countries?c=${encodeURIComponent(scopeId)}`
  if (scopeType === 'TOPIC' || scopeType === 'BOARD') return '/trends'
  return null
}

function shortRefLabel(ref: EvidenceRef): string {
  if (ref.label && ref.label !== ref.ref_id) return ref.label.slice(0, 36)
  if (ref.type === 'metric') return ref.ref_id.replace(/^metric:/, '')
  return ref.ref_id.slice(0, 12)
}

export function EvidenceChips({ refs }: { refs?: EvidenceRef[] }) {
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [articles, setArticles] = useState<TraceArticle[]>([])

  if (!refs || refs.length === 0) return null

  const articleIds = Array.from(
    new Set(refs.filter((r) => r.type === 'article' && r.ref_id).map((r) => r.ref_id)),
  )

  async function toggleArticleTrace() {
    if (open) {
      setOpen(false)
      return
    }
    setOpen(true)
    if (articles.length > 0 || articleIds.length === 0) return
    setLoading(true)
    setError(null)
    try {
      const res = await fetchArticleTrace(articleIds, 20)
      setArticles(res.articles || [])
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <div className="gni-ev-chips">
        {refs.map((ref, idx) => {
          const key = `${ref.type}:${ref.ref_id}:${idx}`
          if (ref.type === 'event') {
            return (
              <Link key={key} to={`/events/${ref.ref_id}`} className="gni-ev-chip">
                <span className="gni-ev-chip-kind">事件</span>
                <span>{shortRefLabel(ref)}</span>
              </Link>
            )
          }
          if (ref.type === 'alert') {
            return (
              <Link key={key} to="/alerts" className="gni-ev-chip">
                <span className="gni-ev-chip-kind">预警</span>
                <span>{shortRefLabel(ref)}</span>
              </Link>
            )
          }
          if (ref.type === 'metric') {
            const href = metricHref(ref.ref_id)
            return href ? (
              <Link key={key} to={href} className="gni-ev-chip">
                <span className="gni-ev-chip-kind">统计</span>
                <span>{shortRefLabel(ref)}</span>
              </Link>
            ) : (
              <span key={key} className="gni-ev-chip">
                <span className="gni-ev-chip-kind">统计</span>
                <span>{shortRefLabel(ref)}</span>
              </span>
            )
          }
          // article ref — opens trace drawer (or direct link)
          return (
            <button
              key={key}
              type="button"
              className="gni-ev-chip"
              onClick={toggleArticleTrace}
              title={`点击查看文章溯源证据 (${ref.ref_id})`}
            >
              <span className="gni-ev-chip-kind">文章</span>
              <span>{shortRefLabel(ref)}</span>
            </button>
          )
        })}
        {articleIds.length > 0 && (
          <button type="button" className="gni-ev-chip" onClick={toggleArticleTrace}>
            <span>{open ? '收起原文证据' : `下钻 ${articleIds.length} 篇原文证据`}</span>
          </button>
        )}
      </div>

      {open && articleIds.length > 0 && (
        <div className="gni-drawer">
          <div className="gni-drawer-head">
            <span>关联代表文章与原文立场证据（{articleIds.length} 篇）</span>
            <button type="button" className="linkish" onClick={() => setOpen(false)}>
              收起
            </button>
          </div>
          <EvidenceTraceTable articles={articles} loading={loading} error={error} />
        </div>
      )}
    </div>
  )
}
