import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchSentimentStance, type SentimentStancePayload } from '../apiV2'
import { useEvidenceDrawer } from '../components/EvidenceContext'
import {
  EmptyState,
  ErrorState,
  fmtDateTime,
  fmtPct,
  LoadingState,
  PartialDataBanner,
  SampleSizeBadge,
  SectionCard,
  StanceBadge,
  StanceBar,
} from '../components/StateBlocks'
import '../components/intel.css'

export function SentimentStancePage() {
  const { openEvidence } = useEvidenceDrawer()
  const [days, setDays] = useState(30)
  const [data, setData] = useState<SentimentStancePayload | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchSentimentStance(days)
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
  }, [days])

  if (loading) return <LoadingState label="加载情感与对华立场独立分析…" />
  if (error) return <ErrorState error={error} />
  if (!data) return <EmptyState title="暂无情感与立场数据" />

  const g = data.stance.global as {
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

  return (
    <div className="intel-page">
      <div className="intel-header-row">
        <div>
          <h1 style={{ margin: 0 }}>Sentiment & Stance Analysis（情感与对华立场独立分析）</h1>
          <p className="muted small" style={{ margin: '0.25rem 0 0' }}>
            窗口 {fmtDateTime(data.meta.period_start)} → {fmtDateTime(data.meta.period_end)} UTC ·
            Stance Target: <strong>{data.meta.stance_target}</strong>
          </p>
        </div>
        <div className="intel-filter-bar">
          <select value={days} onChange={(e) => setDays(Number(e.target.value))}>
            <option value={7}>近 7 天</option>
            <option value={14}>近 14 天</option>
            <option value={30}>近 30 天</option>
            <option value={90}>近 90 天</option>
          </select>
        </div>
      </div>

      <PartialDataBanner message={data.meta.rules.join(' ')} />

      {data.assessment && (
        <div className="intel-banner">
          <strong>情感与立场研判摘要 ({data.assessment.status})：</strong>{' '}
          {data.assessment.executive_summary}
        </div>
      )}

      {/* Side-by-side strict separation */}
      <div className="intel-grid-2">
        <SectionCard
          title="1 · China Stance（对中国大陆立场 · target=china_mainland）"
          subtitle="Unclassified 保留在文章总量中，但不进入正中负比例分母"
        >
          <div className="intel-kpi-row" style={{ marginBottom: '0.75rem' }}>
            <div className="intel-kpi-card">
              <div className="intel-kpi-label">文章总量</div>
              <div className="intel-kpi-value">{g.article_count ?? 0}</div>
            </div>
            <div className="intel-kpi-card primary">
              <div className="intel-kpi-label">Stance Coverage Rate</div>
              <div className="intel-kpi-value">{fmtPct(g.stance_coverage_rate)}</div>
            </div>
            <div className="intel-kpi-card">
              <div className="intel-kpi-label">Unclassified</div>
              <div className="intel-kpi-value">{g.unclassified_count ?? 0}</div>
            </div>
          </div>

          <StanceBar
            positiveRate={g.positive_rate}
            neutralRate={g.neutral_rate}
            negativeRate={g.negative_rate}
          />
          <p className="muted small" style={{ marginTop: '0.4rem' }}>
            Positive: {g.positive_count ?? 0} · Neutral: {g.neutral_count ?? 0} · Negative:{' '}
            {g.negative_count ?? 0}
          </p>

          <h4>立场归属区分（媒体自身 vs 引述对象）</h4>
          <div className="intel-chip-row">
            {Object.entries(data.stance.expression_owner_counts).map(([k, v]) => (
              <span key={k} className="intel-badge">
                {k === 'quoted_actor' ? '引述对象 (quoted_actor)' : k}: {v}
              </span>
            ))}
          </div>
        </SectionCard>

        <SectionCard
          title="2 · Sentiment（文章情感表达 · 与对华立场独立）"
          subtitle="仅反映文章叙事语调/情绪，不直接等同于对中国大陆的立场"
        >
          <div className="intel-kpi-row">
            {['positive', 'neutral', 'negative', 'unknown'].map((k) => (
              <div key={k} className="intel-kpi-card">
                <div className="intel-kpi-label">{k}</div>
                <div className="intel-kpi-value">{data.sentiment.overall_counts[k] ?? 0}</div>
              </div>
            ))}
          </div>

          <h4 style={{ marginTop: '0.85rem' }}>各国情感分布</h4>
          <table>
            <thead>
              <tr>
                <th>国家</th>
                <th>+</th>
                <th>~</th>
                <th>−</th>
                <th>?</th>
              </tr>
            </thead>
            <tbody>
              {data.sentiment.by_country.map((c) => (
                <tr key={c.country_id}>
                  <td>
                    <strong>{c.country_id}</strong>
                  </td>
                  <td>{c.counts.positive ?? 0}</td>
                  <td>{c.counts.neutral ?? 0}</td>
                  <td>{c.counts.negative ?? 0}</td>
                  <td>{c.counts.unknown ?? 0}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </SectionCard>
      </div>

      {/* Country & Topic Stance Breakdown */}
      <SectionCard title="3 · 国别对华立场分布（含覆盖率与样本量提示）">
        <table>
          <thead>
            <tr>
              <th>国家</th>
              <th>文章数</th>
              <th>覆盖率</th>
              <th>正面 / 中性 / 负面（已分类分母）</th>
              <th>Unclassified</th>
              <th>样本</th>
            </tr>
          </thead>
          <tbody>
            {data.stance.by_country.map((r) => {
              const row = r as {
                scope_id: string
                article_count: number
                stance_coverage_rate: number | null
                positive_rate: number | null
                neutral_rate: number | null
                negative_rate: number | null
                unclassified_count: number
              }
              return (
                <tr key={row.scope_id}>
                  <td>
                    <Link to={`/countries?c=${encodeURIComponent(row.scope_id)}`}>
                      <strong>{row.scope_id}</strong>
                    </Link>
                  </td>
                  <td>{row.article_count}</td>
                  <td>{fmtPct(row.stance_coverage_rate)}</td>
                  <td style={{ minWidth: '220px' }}>
                    <StanceBar
                      positiveRate={row.positive_rate}
                      neutralRate={row.neutral_rate}
                      negativeRate={row.negative_rate}
                    />
                  </td>
                  <td>{row.unclassified_count}</td>
                  <td>
                    <SampleSizeBadge count={row.article_count} />
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </SectionCard>

      {/* Representative Articles */}
      <SectionCard title="4 · 代表文章（情感与立场并列对比，点击查看原文证据）">
        <table>
          <thead>
            <tr>
              <th>发布时间</th>
              <th>国家 / 信源</th>
              <th>标题</th>
              <th>情感</th>
              <th>对华立场</th>
              <th>归属</th>
            </tr>
          </thead>
          <tbody>
            {data.representative_articles.map((a) => (
              <tr key={a.article_id}>
                <td className="muted small">{fmtDateTime(a.published_at)}</td>
                <td>
                  <strong>{a.source_country || '—'}</strong> · {a.source_name}
                </td>
                <td>
                  <button
                    type="button"
                    className="linkish"
                    onClick={() => openEvidence(a.article_id)}
                  >
                    {a.title || a.article_id}
                  </button>
                </td>
                <td>
                  <span className="intel-badge">{a.sentiment_label}</span>
                </td>
                <td>
                  <StanceBadge label={a.stance_label} />
                </td>
                <td className="muted small">{a.expression_owner}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </SectionCard>
    </div>
  )
}
