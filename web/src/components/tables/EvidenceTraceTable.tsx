import type { TraceArticle } from '../../api'
import './tables.css'

function stanceBadge(label: string) {
  if (label === 'Positive') return { text: '正面 Positive', cls: 'gni-pill-pos' }
  if (label === 'Neutral') return { text: '中性 Neutral', cls: 'gni-pill-neu' }
  if (label === 'Negative') return { text: '负面 Negative', cls: 'gni-pill-neg' }
  return { text: 'Unclassified', cls: 'gni-pill-warn' }
}

function fmtPublished(iso: string | null) {
  if (!iso) return '—'
  return iso.replace('T', ' ').slice(0, 16)
}

export function EvidenceTraceTable({
  articles,
  loading,
  error,
}: {
  articles: TraceArticle[]
  loading?: boolean
  error?: string | null
}) {
  if (loading) return <p className="muted small">加载溯源文章与原文证据…</p>
  if (error) return <p className="error small">溯源加载失败: {error}</p>
  if (!articles.length) return <p className="muted small">暂无可溯源文章</p>

  return (
    <div className="gni-table-wrap">
      <table className="gni-table">
        <thead>
          <tr>
            <th>发布时间 (published_at)</th>
            <th>国家 / 信源</th>
            <th>标题与原文立场证据 (stance_evidence)</th>
            <th className="gni-num">对华立场</th>
          </tr>
        </thead>
        <tbody>
          {articles.map((a) => {
            const badge = stanceBadge(a.stance_label)
            const quote = a.stance_evidence?.[0]?.quote || a.stance_evidence?.[0]?.span_text
            return (
              <tr key={a.article_id}>
                <td className="gni-mono muted">{fmtPublished(a.published_at)}</td>
                <td>
                  <strong>{a.source_country || '—'}</strong>
                  <div className="muted small">{a.source_name}</div>
                </td>
                <td>
                  {a.url ? (
                    <a href={a.url} target="_blank" rel="noreferrer">
                      <strong>{a.title || a.article_id}</strong>
                    </a>
                  ) : (
                    <strong>{a.title || a.article_id}</strong>
                  )}
                  {quote && <div className="gni-quote">{quote}</div>}
                </td>
                <td className="gni-num">
                  <span className={`gni-pill ${badge.cls}`}>{badge.text}</span>
                  {typeof a.stance_confidence === 'number' && (
                    <div className="muted small">置信 {a.stance_confidence.toFixed(2)}</div>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
