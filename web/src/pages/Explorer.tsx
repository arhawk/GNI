import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { fetchArticles, type ArticlesPagePayload } from '../apiV2'
import { useEvidenceDrawer } from '../components/EvidenceContext'
import {
  EmptyState,
  ErrorState,
  fmtDateTime,
  LoadingState,
  SectionCard,
  StanceBadge,
} from '../components/StateBlocks'
import '../components/intel.css'

export function ExplorerPage() {
  const [params, setParams] = useSearchParams()
  const { openEvidence } = useEvidenceDrawer()
  const [q, setQ] = useState(params.get('q') || '')
  const [country, setCountry] = useState(params.get('country') || '')
  const [source, setSource] = useState(params.get('source') || '')
  const [topic, setTopic] = useState(params.get('topic') || '')
  const [sentiment, setSentiment] = useState(params.get('sentiment') || '')
  const [stance, setStance] = useState(params.get('stance') || '')
  const [page, setPage] = useState(Number(params.get('page') || '1') || 1)
  const [data, setData] = useState<ArticlesPagePayload | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchArticles({
      q: q || undefined,
      country: country || undefined,
      source: source || undefined,
      topic: topic || undefined,
      sentiment: sentiment || undefined,
      stance: stance || undefined,
      page,
      page_size: 20,
    })
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
  }, [q, country, source, topic, sentiment, stance, page])

  function resetFilters() {
    setQ('')
    setCountry('')
    setSource('')
    setTopic('')
    setSentiment('')
    setStance('')
    setPage(1)
    setParams({}, { replace: true })
  }

  return (
    <div className="intel-page">
      <div>
        <h1 style={{ margin: 0 }}>Evidence & Article Explorer（文章与原文证据浏览器）</h1>
        <p className="muted small" style={{ margin: '0.25rem 0 0' }}>
          严格按 published_at 倒序排列；支持按关键词、国家、媒体、议题、情感、对华立场多维筛选与原文证据定位。
        </p>
      </div>

      <SectionCard title="多维筛选">
        <div className="intel-filter-bar">
          <input
            type="search"
            placeholder="搜索标题或正文…"
            value={q}
            onChange={(e) => {
              setQ(e.target.value)
              setPage(1)
            }}
          />
          <select
            value={country}
            onChange={(e) => {
              setCountry(e.target.value)
              setPage(1)
            }}
          >
            <option value="">全部国家</option>
            {['US', 'RU', 'DE', 'IN', 'AU'].map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          <input
            type="text"
            placeholder="媒体名称 / ID"
            value={source}
            onChange={(e) => {
              setSource(e.target.value)
              setPage(1)
            }}
          />
          <input
            type="text"
            placeholder="议题 ID (如 trade_tariff)"
            value={topic}
            onChange={(e) => {
              setTopic(e.target.value)
              setPage(1)
            }}
          />
          <select
            value={sentiment}
            onChange={(e) => {
              setSentiment(e.target.value)
              setPage(1)
            }}
          >
            <option value="">全部情感</option>
            <option value="positive">positive</option>
            <option value="neutral">neutral</option>
            <option value="negative">negative</option>
            <option value="unknown">unknown</option>
          </select>
          <select
            value={stance}
            onChange={(e) => {
              setStance(e.target.value)
              setPage(1)
            }}
          >
            <option value="">全部对华立场</option>
            <option value="Positive">Positive</option>
            <option value="Neutral">Neutral</option>
            <option value="Negative">Negative</option>
            <option value="Unclassified">Unclassified</option>
          </select>
          <button type="button" className="intel-btn" onClick={resetFilters}>
            重置筛选
          </button>
        </div>
      </SectionCard>

      {loading && <LoadingState label="检索文章与证据中…" />}
      {error && <ErrorState error={error} />}
      {!loading && !error && data && data.items.length === 0 && (
        <EmptyState title="未找到匹配的文章" detail="请放宽筛选条件重试。" />
      )}

      {!loading && !error && data && data.items.length > 0 && (
        <SectionCard
          title={`匹配文章（共 ${data.pagination.total} 篇 · 第 ${data.pagination.page}/${data.pagination.total_pages} 页）`}
          right={
            <div className="intel-chip-row">
              <button
                type="button"
                className="intel-btn"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                上一页
              </button>
              <button
                type="button"
                className="intel-btn"
                disabled={page >= data.pagination.total_pages}
                onClick={() => setPage((p) => p + 1)}
              >
                下一页
              </button>
            </div>
          }
        >
          <table>
            <thead>
              <tr>
                <th>发布时间 (published_at)</th>
                <th>国家 / 信源</th>
                <th>标题与议题</th>
                <th>情感</th>
                <th>对华立场</th>
                <th>原文证据</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((a) => (
                <tr key={a.article_id}>
                  <td className="muted small">{fmtDateTime(a.published_at)}</td>
                  <td>
                    <strong>{a.source_country || '—'}</strong>
                    <div className="muted small">{a.source_name}</div>
                  </td>
                  <td>
                    <Link to={`/articles/${a.article_id}`}>
                      <strong>{a.title || a.article_id}</strong>
                    </Link>
                    {a.topics_v1.length > 0 && (
                      <div className="muted small">{a.topics_v1.join(' · ')}</div>
                    )}
                  </td>
                  <td>
                    <span className="intel-badge">{a.sentiment_label}</span>
                  </td>
                  <td>
                    <StanceBadge label={a.stance_label} />
                    {a.expression_owner === 'quoted_actor' && (
                      <div className="muted small">引述对象</div>
                    )}
                  </td>
                  <td>
                    <button
                      type="button"
                      className="intel-ev-btn"
                      onClick={() => openEvidence(a.article_id)}
                    >
                      证据 ({a.evidence_count})
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </SectionCard>
      )}
    </div>
  )
}
