import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  fetchCountries,
  fetchCountryDetail,
  type CountryDetail,
  type CountryListItem,
} from '../api'
import { fetchCountriesCompare, type CountryComparePayload } from '../apiV2'
import { useEvidenceDrawer } from '../components/EvidenceContext'
import {
  ErrorState,
  fmtPct,
  LoadingState,
  PartialDataBanner,
  SampleSizeBadge,
  SectionCard,
  StanceBar,
} from '../components/StateBlocks'
import '../components/intel.css'

export function CountriesPage() {
  const [params, setParams] = useSearchParams()
  const { openEvidence } = useEvidenceDrawer()
  const selected = (params.get('c') || '').toUpperCase()
  const [list, setList] = useState<CountryListItem[]>([])
  const [compareCodes, setCompareCodes] = useState<string[]>(['US', 'RU', 'DE'])
  const [days, setDays] = useState(30)
  const [compareData, setCompareData] = useState<CountryComparePayload | null>(null)
  const [detail, setDetail] = useState<CountryDetail | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchCountries()
      .then((r) => {
        setList(r.countries)
        if (!params.get('c') && r.countries[0]) {
          setParams({ c: r.countries[0].country_id }, { replace: true })
        }
        if (r.countries.length > 0) {
          setCompareCodes(r.countries.slice(0, Math.min(4, r.countries.length)).map((c) => c.country_id))
        }
      })
      .catch((e: Error) => setError(e.message))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (compareCodes.length === 0) return
    fetchCountriesCompare(compareCodes, days)
      .then(setCompareData)
      .catch((e: Error) => setError(e.message))
  }, [compareCodes, days])

  useEffect(() => {
    if (!selected) return
    setDetail(null)
    fetchCountryDetail(selected)
      .then(setDetail)
      .catch((e: Error) => setError(e.message))
  }, [selected])

  function toggleCountry(code: string) {
    setCompareCodes((prev) => {
      if (prev.includes(code)) {
        return prev.length > 1 ? prev.filter((c) => c !== code) : prev
      }
      return [...prev, code]
    })
  }

  if (error) return <ErrorState error={error} />

  return (
    <div className="intel-page">
      <div className="intel-header-row">
        <div>
          <h1 style={{ margin: 0 }}>Country Comparison（多国媒体涉华报道比较）</h1>
          <p className="muted small" style={{ margin: '0.25rem 0 0' }}>
            国家归属严格按信源所属国 (source_country)，比较时强制展示样本量与立场覆盖率。
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

      {/* Multi-Country Selector */}
      <SectionCard
        title="选择比较国家"
        subtitle={compareData?.meta.attribution_note}
      >
        <div className="intel-chip-row">
          {list.map((c) => {
            const active = compareCodes.includes(c.country_id)
            return (
              <button
                key={c.country_id}
                type="button"
                className={active ? 'intel-btn primary' : 'intel-btn'}
                onClick={() => toggleCountry(c.country_id)}
              >
                {active ? '✓ ' : ''}
                {c.name} ({c.country_id}) · {c.china_article_count} 篇
              </button>
            )
          })}
        </div>
      </SectionCard>

      {/* Multi-Country Comparison Matrix */}
      {!compareData ? (
        <LoadingState label="加载多国对比数据…" />
      ) : (
        <SectionCard
          title="多国并排对比（报道量、覆盖、情感、对华立场、议题与事件）"
          subtitle={compareData.meta.stance_note}
        >
          {compareData.country_comparison_assessment && (
            <div className="intel-banner" style={{ marginBottom: '0.75rem' }}>
              <strong>跨国比较研判：</strong>{' '}
              {compareData.country_comparison_assessment.executive_summary}
            </div>
          )}

          <div className="intel-grid-3">
            {compareData.countries.map((c) => (
              <div key={c.country_id} className="intel-card">
                <div className="intel-header-row">
                  <h3 style={{ margin: 0 }}>
                    {c.country_name} ({c.country_id})
                  </h3>
                  <SampleSizeBadge count={c.article_count} />
                </div>

                <div className="muted small" style={{ marginTop: '0.25rem' }}>
                  涉华文章 <strong>{c.article_count}</strong> 篇（较上期{' '}
                  {c.delta >= 0 ? `+${c.delta}` : c.delta}）· 发稿媒体 {c.reporting_sources}/
                  {c.total_registered_sources}
                </div>

                {c.small_sample_warning && c.sample_note && (
                  <div style={{ marginTop: '0.5rem' }}>
                    <PartialDataBanner message={c.sample_note} />
                  </div>
                )}

                <div style={{ marginTop: '0.65rem' }}>
                  <div className="muted small">对华立场 (target: china_mainland) · 覆盖率 {fmtPct(c.stance.stance_coverage_rate)}</div>
                  <StanceBar
                    positiveRate={c.stance.positive_rate}
                    neutralRate={c.stance.neutral_rate}
                    negativeRate={c.stance.negative_rate}
                  />
                  <div className="muted small">
                    Unclassified: {c.stance.unclassified_count}（不计入比例分母）
                  </div>
                </div>

                <div style={{ marginTop: '0.6rem' }}>
                  <div className="muted small">情感分布（Sentiment，与立场独立）</div>
                  <div className="intel-chip-row">
                    {Object.entries(c.sentiment_counts).map(([k, v]) => (
                      <span key={k} className="intel-badge">
                        {k}: {v}
                      </span>
                    ))}
                  </div>
                </div>

                <div style={{ marginTop: '0.6rem' }}>
                  <div className="muted small">主要关注议题</div>
                  <div className="intel-chip-row">
                    {c.topics_top.length === 0 ? (
                      <span className="muted small">无议题样本</span>
                    ) : (
                      c.topics_top.slice(0, 4).map((t) => (
                        <Link
                          key={t.topic_id}
                          to={`/topics?t=${encodeURIComponent(t.topic_id)}`}
                          className="intel-ev-btn"
                        >
                          {t.topic_id} ({t.article_count})
                        </Link>
                      ))
                    )}
                  </div>
                </div>

                {c.top_events.length > 0 && (
                  <div style={{ marginTop: '0.6rem' }}>
                    <div className="muted small">重点关注事件</div>
                    <ul className="event-list">
                      {c.top_events.slice(0, 3).map((e) => (
                        <li key={e.event_id}>
                          <Link to={`/events/${e.event_id}`}>{e.title}</Link>
                          <span className="meta">{e.article_count}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {c.representative_articles.length > 0 && (
                  <div style={{ marginTop: '0.6rem' }}>
                    <div className="muted small">代表文章</div>
                    <div className="intel-chip-row">
                      {c.representative_articles.slice(0, 2).map((a) => (
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
                )}

                <div style={{ marginTop: '0.65rem' }}>
                  <button
                    type="button"
                    className="linkish small"
                    onClick={() => setParams({ c: c.country_id })}
                  >
                    查看 {c.country_id} 媒体明细 ↓
                  </button>
                </div>
              </div>
            ))}
          </div>
        </SectionCard>
      )}

      {/* Single Country Media Registry Detail */}
      {detail && (
        <SectionCard
          title={`${detail.name} (${detail.country_id}) · 接入媒体与近期文章`}
          subtitle={detail.disclaimer}
        >
          <table>
            <thead>
              <tr>
                <th>来源</th>
                <th>分区</th>
                <th>状态</th>
                <th>涉华文章</th>
              </tr>
            </thead>
            <tbody>
              {detail.media.map((m) => (
                <tr key={m.source_id}>
                  <td>
                    {m.name} <span className="muted small">({m.source_id})</span>
                  </td>
                  <td>{m.source_bucket || '—'}</td>
                  <td>{m.active_status}</td>
                  <td>{m.china_article_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </SectionCard>
      )}
    </div>
  )
}
