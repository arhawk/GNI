import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchOutlook, runAssessmentTaskApi, type OutlookPayload } from '../apiV2'
import { useEvidenceDrawer } from '../components/EvidenceContext'
import {
  ClassificationBadge,
  EmptyState,
  ErrorState,
  LoadingState,
  PartialDataBanner,
  SectionCard,
} from '../components/StateBlocks'
import '../components/intel.css'

export function OutlookPage() {
  const { openEvidence } = useEvidenceDrawer()
  const [data, setData] = useState<OutlookPayload | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)

  function load() {
    setLoading(true)
    setError(null)
    fetchOutlook()
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
  }, [])

  async function handleRunOutlook() {
    setRunning(true)
    setError(null)
    try {
      await runAssessmentTaskApi('outlook_assessment', { period: data?.meta.period, force: false })
      load()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setRunning(false)
    }
  }

  if (loading) return <LoadingState label="加载展望与观察清单 (Outlook & Watchlist)…" />
  if (error) return <ErrorState error={error} />
  if (!data) return <EmptyState title="暂无展望数据" />

  return (
    <div className="intel-page">
      <div className="intel-header-row">
        <div>
          <h1 style={{ margin: 0 }}>Outlook & Watchlist（条件性展望与观察清单）</h1>
          <p className="muted small" style={{ margin: '0.25rem 0 0' }}>
            周期：{data.meta.period} · 状态：{data.meta.status}
          </p>
        </div>
        <button
          type="button"
          className="intel-btn primary"
          disabled={running}
          onClick={handleRunOutlook}
        >
          {running ? '生成展望研判中…' : '运行 outlook_assessment'}
        </button>
      </div>

      <PartialDataBanner message={data.meta.disclaimer} />

      {data.executive_summary && (
        <div className="intel-banner">
          <strong>展望摘要：</strong> {data.executive_summary}
        </div>
      )}

      {/* Watchlist Cards */}
      <SectionCard
        title={`条件性观察清单 (${data.watchlist.length})`}
        subtitle="每项均明确标注观察对象、当前证据、可能发展、触发条件、替代情景与不确定性"
      >
        {data.watchlist.length === 0 ? (
          <p className="muted small">
            当前周期暂无结构化观察项。点击右上角「运行 outlook_assessment」或在报告中心生成 V2 研判即可产出。
          </p>
        ) : (
          <div className="intel-grid-2">
            {data.watchlist.map((w) => (
              <div key={w.id} className="intel-card">
                <div className="intel-header-row">
                  <h3 style={{ margin: 0 }}>{w.observation_object}</h3>
                  <ClassificationBadge kind={w.classification} />
                </div>
                {w.current_evidence && (
                  <p className="small">
                    <strong>当前证据：</strong> {w.current_evidence}
                  </p>
                )}
                {w.possible_development && (
                  <p className="small">
                    <strong>可能发展（条件性）：</strong> {w.possible_development}
                  </p>
                )}
                {w.trigger_condition && (
                  <p className="small">
                    <strong>触发条件：</strong> {w.trigger_condition}
                  </p>
                )}
                {w.alternative_scenario && (
                  <p className="small">
                    <strong>替代情景：</strong> {w.alternative_scenario}
                  </p>
                )}
                <p className="muted small">
                  <strong>不确定性：</strong> {w.uncertainty}
                </p>
                <div className="intel-chip-row">
                  {w.related_events.map((eid) => (
                    <Link key={eid} to={`/events/${eid}`} className="intel-ev-btn">
                      事件: {eid.slice(0, 10)}
                    </Link>
                  ))}
                  {w.related_topics.map((tid) => (
                    <Link key={tid} to={`/topics?t=${encodeURIComponent(tid)}`} className="intel-ev-btn">
                      议题: {tid}
                    </Link>
                  ))}
                  {w.evidence_refs.map((ref, idx) => {
                    const rid = ref.evidence_id || ref.article_id || ref.ref_id
                    if (!rid) return null
                    return (
                      <button
                        key={idx}
                        type="button"
                        className="intel-ev-btn"
                        onClick={() => openEvidence(rid)}
                      >
                        证据: {ref.label || rid.slice(0, 10)}
                      </button>
                    )
                  })}
                </div>
              </div>
            ))}
          </div>
        )}
      </SectionCard>

      {/* Strict 3-way separation */}
      <div className="intel-grid-3">
        <SectionCard title="已发生事实 (Fact)">
          {data.observations.length === 0 ? (
            <p className="muted small">无</p>
          ) : (
            data.observations.map((o, i) => (
              <div key={i} className="intel-finding-item">
                <ClassificationBadge kind="Fact" />
                <p className="small">{o.statement || o.summary || o.title}</p>
              </div>
            ))
          )}
        </SectionCard>
        <SectionCard title="条件性推断 (Inference)">
          {data.interpretations.length === 0 ? (
            <p className="muted small">无</p>
          ) : (
            data.interpretations.map((o, i) => (
              <div key={i} className="intel-finding-item">
                <ClassificationBadge kind="Inference" />
                <p className="small">{o.statement || o.summary || o.title}</p>
              </div>
            ))
          )}
        </SectionCard>
        <SectionCard title="未验证假设 / 展望 (Hypothesis)">
          {data.hypotheses.length === 0 ? (
            <p className="muted small">无</p>
          ) : (
            data.hypotheses.map((o, i) => (
              <div key={i} className="intel-finding-item">
                <ClassificationBadge kind={o.classification || 'Hypothesis'} />
                <p className="small">{o.statement || o.summary || o.title}</p>
              </div>
            ))
          )}
        </SectionCard>
      </div>
    </div>
  )
}
