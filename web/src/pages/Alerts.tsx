import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchAlerts, type AlertItem } from '../api'

const SUB_LABEL: Record<string, string> = {
  volume_spike: '报道量异常',
  attitude_shift: '态度异常',
  narrative_shift: '叙事变化',
  major_event: '重大事件',
  transnational: '跨国扩散',
  source_failure: '数据源故障',
  collection_stall: '采集异常',
  analysis_backlog: '分析积压',
  model_failure: '模型异常',
  data_quality: '数据质量',
}

export function AlertsPage() {
  const [intel, setIntel] = useState<AlertItem[]>([])
  const [system, setSystem] = useState<AlertItem[]>([])
  const [disclaimer, setDisclaimer] = useState('')
  const [counts, setCounts] = useState({ intelligence: 0, system: 0, high: 0 })
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchAlerts()
      .then((r) => {
        setIntel(r.intelligence)
        setSystem(r.system)
        setDisclaimer(r.disclaimer)
        setCounts(r.counts)
      })
      .catch((e: Error) => setError(e.message))
  }, [])

  if (error) return <div className="panel error">{error}</div>

  return (
    <div className="alerts-page">
      <div className="panel">
        <h2>异常与预警</h2>
        <p className="callout">{disclaimer}</p>
        <p className="muted small">
          情报 {counts.intelligence} · 系统 {counts.system} · 高严重度 {counts.high}
        </p>
      </div>
      <div className="alerts-grid">
        <section className="panel">
          <h3>A · 舆情情报预警</h3>
          <p className="muted small">面向研究：报道/态度/叙事/重大事件/跨国扩散</p>
          <AlertList items={intel} />
        </section>
        <section className="panel">
          <h3>B · 系统运行告警</h3>
          <p className="muted small">面向运维：源故障、采集、积压、模型、质量</p>
          <AlertList items={system} />
        </section>
      </div>
    </div>
  )
}

function AlertList({ items }: { items: AlertItem[] }) {
  if (items.length === 0) return <p className="muted">当前窗口无触发信号。</p>
  return (
    <ul className="event-list">
      {items.map((a) => {
        const evId = typeof a.evidence?.event_id === 'string' ? a.evidence.event_id : null
        return (
          <li key={a.id}>
            <div>
              <span className={`sev sev-${a.severity}`}>{a.severity}</span>{' '}
              <strong>{SUB_LABEL[a.subcategory] || a.subcategory}</strong> · {a.title}
            </div>
            <div className="muted small">{a.summary}</div>
            {evId && (
              <Link className="small" to={`/events/${evId}`}>
                查看事件
              </Link>
            )}
          </li>
        )
      })}
    </ul>
  )
}
