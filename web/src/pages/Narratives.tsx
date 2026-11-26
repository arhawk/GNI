import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchNarratives, type NarrativeItem, type NarrativesPayload } from '../apiV2'
import { useEvidenceDrawer } from '../components/EvidenceContext'
import {
  EmptyState,
  ErrorState,
  fmtDateTime,
  LoadingState,
  PartialDataBanner,
  SectionCard,
} from '../components/StateBlocks'
import '../components/intel.css'

export function NarrativesPage() {
  const { openEvidence } = useEvidenceDrawer()
  const [days, setDays] = useState(30)
  const [data, setData] = useState<NarrativesPayload | null>(null)
  const [selected, setSelected] = useState<NarrativeItem | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchNarratives(days)
      .then((res) => {
        if (cancelled) return
        setData(res)
        setSelected(res.narratives[0] ?? null)
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

  if (loading) return <LoadingState label="加载叙事分析 (Narrative Analysis)…" />
  if (error) return <ErrorState error={error} />
  if (!data) return <EmptyState title="暂无叙事数据" />

  return (
    <div className="intel-page">
      <div className="intel-header-row">
        <div>
          <h1 style={{ margin: 0 }}>Narrative Analysis（叙事结构与演化追踪）</h1>
          <p className="muted small" style={{ margin: '0.25rem 0 0' }}>
            共识别 {data.meta.total} 个叙事簇 · 窗口 {fmtDateTime(data.meta.period_start)} →{' '}
            {fmtDateTime(data.meta.period_end)} UTC
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

      <PartialDataBanner message={data.meta.non_coordination_note} />

      {data.narrative_assessment && (
        <div className="intel-banner">
          <strong>叙事研判摘要 ({data.narrative_assessment.status})：</strong>{' '}
          {data.narrative_assessment.executive_summary}
        </div>
      )}

      {data.narratives.length === 0 ? (
        <EmptyState
          title="当前窗口内暂无聚合叙事簇"
          detail="需文章具备 V1.1 叙事提取或事件叙事聚类记录；历史旧版 v0.1 文章尚未包含叙事字段。"
        />
      ) : (
        <div className="intel-grid-2">
          <SectionCard title="叙事列表（主导 / 新兴 / 观察）">
            <ul className="event-list">
              {data.narratives.map((n) => (
                <li key={n.narrative_id}>
                  <button
                    type="button"
                    className={selected?.narrative_id === n.narrative_id ? 'linkish active' : 'linkish'}
                    onClick={() => setSelected(n)}
                  >
                    <strong>{n.name}</strong>
                  </button>
                  <span className="meta">
                    <span className="intel-badge">{n.trend_status}</span> · {n.article_count} 篇 ·{' '}
                    {n.related_countries.join(', ') || '—'}
                  </span>
                </li>
              ))}
            </ul>
          </SectionCard>

          {selected && (
            <SectionCard
              title={selected.name}
              subtitle={`Narrative ID: ${selected.narrative_id} · 来源: ${selected.source}`}
              right={<span className="intel-badge">{selected.trend_status}</span>}
            >
              <p>
                <strong>Core Claim：</strong> {selected.core_claim}
              </p>
              <div className="intel-chip-row">
                <span className="intel-badge">主框架: {selected.main_frame || '未标注'}</span>
                <span className="intel-badge">涉及文章: {selected.article_count}</span>
                <span className="intel-badge">
                  涉及国家: {selected.related_countries.join(', ') || '—'}
                </span>
                <span className="intel-badge">
                  首次出现: {selected.first_seen ? fmtDateTime(selected.first_seen) : '未知'}
                </span>
                <span className="intel-badge">
                  最近出现: {selected.last_seen ? fmtDateTime(selected.last_seen) : '未知'}
                </span>
              </div>

              {selected.related_topics.length > 0 && (
                <div className="intel-chip-row" style={{ marginTop: '0.6rem' }}>
                  {selected.related_topics.map((t) => (
                    <Link key={t} to={`/topics?t=${encodeURIComponent(t)}`} className="intel-ev-btn">
                      议题: {t}
                    </Link>
                  ))}
                </div>
              )}

              <h4 style={{ marginTop: '0.85rem' }}>
                支撑证据 (Supporting Evidence · {selected.supporting_evidence.length})
              </h4>
              {selected.supporting_evidence.length === 0 ? (
                <p className="muted small">暂无支撑证据片段</p>
              ) : (
                <ul className="event-list">
                  {selected.supporting_evidence.map((ev, i) => (
                    <li key={i}>
                      <button
                        type="button"
                        className="linkish"
                        onClick={() => openEvidence(ev.article_id)}
                      >
                        {ev.title || ev.article_id}
                      </button>
                      <span className="meta">
                        {ev.source_country || '—'} · {fmtDateTime(ev.published_at)}
                      </span>
                      {ev.quote && <div className="muted small">“{ev.quote}”</div>}
                    </li>
                  ))}
                </ul>
              )}

              <h4 style={{ marginTop: '0.85rem' }}>
                反例 / 反向观点 (Counter Evidence · {selected.counter_evidence.length})
              </h4>
              {selected.counter_evidence.length === 0 ? (
                <p className="muted small">当前样本中未观察到显式反例。</p>
              ) : (
                <ul className="event-list">
                  {selected.counter_evidence.map((ev, i) => (
                    <li key={i}>
                      <button
                        type="button"
                        className="linkish"
                        onClick={() => openEvidence(ev.article_id)}
                      >
                        {ev.title || ev.article_id}
                      </button>
                      <span className="meta">{ev.source_country || '—'}</span>
                    </li>
                  ))}
                </ul>
              )}
            </SectionCard>
          )}
        </div>
      )}
    </div>
  )
}
