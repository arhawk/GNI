import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  fetchTopicDetail,
  fetchTopics,
  type TopicDetailPayload,
  type TopicsOverviewPayload,
} from '../apiV2'
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

export function TopicsPage() {
  const [params, setParams] = useSearchParams()
  const { openEvidence } = useEvidenceDrawer()
  const [days, setDays] = useState(30)
  const [overview, setOverview] = useState<TopicsOverviewPayload | null>(null)
  const [detail, setDetail] = useState<TopicDetailPayload | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [detailLoading, setDetailLoading] = useState(false)

  const selectedTopic = params.get('t') || ''

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchTopics(days)
      .then((res) => {
        if (cancelled) return
        setOverview(res)
        if (!params.get('t') && res.topics.length > 0) {
          const top = [...res.topics].sort((a, b) => b.article_count - a.article_count)[0]
          setParams({ t: top.topic_id }, { replace: true })
        }
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [days])

  useEffect(() => {
    if (!selectedTopic) return
    let cancelled = false
    setDetailLoading(true)
    fetchTopicDetail(selectedTopic, days)
      .then((res) => {
        if (!cancelled) setDetail(res)
      })
      .catch(() => {
        if (!cancelled) setDetail(null)
      })
      .finally(() => {
        if (!cancelled) setDetailLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [selectedTopic, days])

  if (loading) return <LoadingState label="加载 4 大板块 × 15 议题分析…" />
  if (error) return <ErrorState error={error} />
  if (!overview) return <EmptyState title="暂无议题数据" />

  const maxTrend = Math.max(1, ...(detail?.trend || []).map((d) => d.article_count))

  return (
    <div className="intel-page">
      <div className="intel-header-row">
        <div>
          <h1 style={{ margin: 0 }}>Topic Analysis（四大板块 × 十五固定议题）</h1>
          <p className="muted small" style={{ margin: '0.25rem 0 0' }}>
            全球唯一涉华文章总量：{overview.meta.global_unique_article_count} 篇 · 方法论{' '}
            {overview.meta.methodology_version} · 分类体系 {overview.meta.taxonomy_version}
          </p>
        </div>
        <div className="intel-filter-bar">
          <label className="small muted">
            统计窗口{' '}
            <select value={days} onChange={(e) => setDays(Number(e.target.value))}>
              <option value={7}>近 7 天</option>
              <option value={14}>近 14 天</option>
              <option value={30}>近 30 天</option>
              <option value={90}>近 90 天</option>
            </select>
          </label>
        </div>
      </div>

      <PartialDataBanner message={overview.meta.overlap_note} />

      {/* A. 4 Boards x 15 Topics Overview */}
      <SectionCard title="A · Topic Overview（四大板块与十五议题）">
        <div className="intel-grid-2">
          {overview.taxonomy_boards.map((board) => {
            const bTopics = overview.topics.filter((t) => board.topic_ids.includes(t.topic_id))
            const bStat = overview.boards.find((b) => b.scope_id === board.board_id)
            return (
              <div key={board.board_id} className="intel-card">
                <div className="intel-header-row">
                  <h3 style={{ margin: 0 }}>{board.label_zh}</h3>
                  <span className="intel-badge">{bStat?.article_count ?? 0} 篇</span>
                </div>
                <ul className="event-list" style={{ marginTop: '0.5rem' }}>
                  {bTopics.map((t) => (
                    <li key={t.topic_id}>
                      <button
                        type="button"
                        className={t.topic_id === selectedTopic ? 'linkish active' : 'linkish'}
                        onClick={() => setParams({ t: t.topic_id })}
                      >
                        {t.label_zh || t.topic_id}
                      </button>
                      <span className="meta">
                        {t.article_count} 篇 ({fmtPct(t.share_of_global)}) ·{' '}
                        {t.delta >= 0 ? `+${t.delta}` : t.delta}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )
          })}
        </div>
      </SectionCard>

      {/* B / C / D: Selected Topic Detail */}
      {detailLoading && <LoadingState label="加载议题详情…" />}
      {!detailLoading && detail && (
        <>
          <SectionCard
            title={`B · ${detail.topic.label_zh} (${detail.topic.topic_id}) — 趋势与分布`}
            right={<SampleSizeBadge count={detail.topic.article_count ?? 0} />}
          >
            <div className="intel-grid-2">
              <div>
                <h4>每日报道量趋势 (published_at)</h4>
                {detail.trend.length === 0 ? (
                  <p className="muted small">该窗口内无报道样本</p>
                ) : (
                  <div className="bars">
                    {detail.trend.map((d) => (
                      <div className="bar-row" key={d.date}>
                        <span className="bar-label">{d.date.slice(5)}</span>
                        <div className="bar-track">
                          <div
                            className="bar-fill"
                            style={{ width: `${Math.round((d.article_count / maxTrend) * 100)}%` }}
                          />
                        </div>
                        <span className="bar-n">{d.article_count}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div>
                <h4>对华立场分布与国家分布</h4>
                <StanceBar
                  positiveRate={detail.topic.positive_rate}
                  neutralRate={detail.topic.neutral_rate}
                  negativeRate={detail.topic.negative_rate}
                />
                <p className="muted small" style={{ marginTop: '0.35rem' }}>
                  立场覆盖率：{fmtPct(detail.topic.stance_coverage_rate)} · Unclassified：
                  {detail.topic.unclassified_count ?? 0}
                </p>
                <h4>主要报道国家（信源所属国）</h4>
                <div className="intel-chip-row">
                  {detail.by_country.map((c) => (
                    <Link
                      key={c.country_id}
                      to={`/countries?c=${encodeURIComponent(c.country_id)}`}
                      className="intel-ev-btn"
                    >
                      {c.country_id}: {c.article_count}
                    </Link>
                  ))}
                </div>
              </div>
            </div>
          </SectionCard>

          <SectionCard title="C · Topic Interpretation（驱动事件、媒体与叙事）">
            {detail.topic_assessment && (
              <div className="intel-banner" style={{ marginBottom: '0.75rem' }}>
                <strong>研判摘要 ({detail.topic_assessment.status})：</strong>{' '}
                {detail.topic_assessment.executive_summary}
              </div>
            )}
            <div className="intel-grid-3">
              <div className="intel-card">
                <h4>主要驱动事件</h4>
                {detail.related_events.length === 0 ? (
                  <p className="muted small">暂无关联事件</p>
                ) : (
                  <ul className="event-list">
                    {detail.related_events.map((e) => (
                      <li key={e.event_id}>
                        <Link to={`/events/${e.event_id}`}>{e.title}</Link>
                        <span className="meta">{e.topic_article_count} 篇</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              <div className="intel-card">
                <h4>主要参与媒体</h4>
                <ul className="event-list">
                  {detail.top_sources.map((s) => (
                    <li key={s.source_name}>
                      <span>{s.source_name}</span>
                      <span className="meta">{s.article_count} 篇</span>
                    </li>
                  ))}
                </ul>
              </div>
              <div className="intel-card">
                <h4>代表性叙事</h4>
                {detail.top_narratives.length === 0 ? (
                  <p className="muted small">暂无文章级叙事标注</p>
                ) : (
                  <ul className="event-list">
                    {detail.top_narratives.map((n) => (
                      <li key={n.label}>
                        <span>{n.label}</span>
                        <span className="meta">{n.article_count} 篇</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </SectionCard>

          <SectionCard
            title={`D · Topic Articles（相关文章 ${detail.articles.length} 篇）`}
            right={
              <Link to={`/explorer?topic=${encodeURIComponent(detail.topic.topic_id)}`} className="muted small">
                在文章浏览器中查看全部 →
              </Link>
            }
          >
            {detail.articles.length === 0 ? (
              <p className="muted small">暂无相关文章</p>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>发布时间</th>
                    <th>国家 / 信源</th>
                    <th>标题</th>
                    <th>情感 / 立场</th>
                    <th>追溯</th>
                  </tr>
                </thead>
                <tbody>
                  {detail.articles.map((a) => (
                    <tr key={a.article_id}>
                      <td className="muted small">{fmtDateTime(a.published_at)}</td>
                      <td>
                        <strong>{a.source_country || '—'}</strong> · {a.source_name}
                      </td>
                      <td>
                        <Link to={`/articles/${a.article_id}`}>{a.title || a.article_id}</Link>
                      </td>
                      <td>
                        <span className="intel-badge">{a.sentiment_label}</span>{' '}
                        <StanceBadge label={a.stance_label} />
                      </td>
                      <td>
                        <button
                          type="button"
                          className="intel-ev-btn"
                          onClick={() => openEvidence(a.article_id)}
                        >
                          查看证据
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </SectionCard>
        </>
      )}
    </div>
  )
}
