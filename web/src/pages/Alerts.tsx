import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  acknowledgeAlert,
  closeAlert,
  fetchAlerts,
  resolveAlert,
  runAlerts,
  type AlertItem,
} from '../api'

const SUB_LABEL: Record<string, string> = {
  volume_spike: '报道量异常',
  attitude_shift: '态度异常',
  sentiment_shift: '情感异常',
  stance_shift: '立场异常',
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
  const [busy, setBusy] = useState(false)

  const reload = useCallback(() => {
    return fetchAlerts()
      .then((r) => {
        setIntel(r.intelligence)
        setSystem(r.system)
        setDisclaimer(r.disclaimer)
        setCounts(r.counts)
      })
      .catch((e: Error) => setError(e.message))
  }, [])

  useEffect(() => {
    reload()
  }, [reload])

  async function onRun() {
    setBusy(true)
    setError(null)
    try {
      await runAlerts()
      await reload()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  async function onAction(id: string, action: 'ack' | 'resolve' | 'close') {
    setBusy(true)
    setError(null)
    try {
      if (action === 'ack') await acknowledgeAlert(id)
      else if (action === 'resolve') await resolveAlert(id)
      else await closeAlert(id)
      await reload()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  if (error) return <div className="panel error">{error}</div>

  return (
    <div className="alerts-page">
      <div className="panel">
        <h2>异常与预警</h2>
        <p className="callout">{disclaimer}</p>
        <p className="muted small">
          情报 {counts.intelligence} · 系统 {counts.system} · 高严重度 {counts.high}
        </p>
        <button type="button" disabled={busy} onClick={onRun}>
          运行规则引擎
        </button>
      </div>
      <div className="alerts-grid">
        <section className="panel">
          <h3>A · 舆情情报预警</h3>
          <p className="muted small">面向研究：报道/态度/叙事/重大事件/跨国扩散</p>
          <AlertList items={intel} busy={busy} onAction={onAction} />
        </section>
        <section className="panel">
          <h3>B · 系统运行告警</h3>
          <p className="muted small">面向运维：源故障、采集、积压、模型、质量</p>
          <AlertList items={system} busy={busy} onAction={onAction} />
        </section>
      </div>
    </div>
  )
}

function AlertList({
  items,
  busy,
  onAction,
}: {
  items: AlertItem[]
  busy: boolean
  onAction: (id: string, action: 'ack' | 'resolve' | 'close') => void
}) {
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
              {a.status && <span className="muted small"> · {a.status}</span>}
            </div>
            <div className="muted small">{a.summary}</div>
            <div className="alert-actions">
              {evId && (
                <Link className="small" to={`/events/${evId}`}>
                  查看事件
                </Link>
              )}
              <button type="button" className="small" disabled={busy} onClick={() => onAction(a.id, 'ack')}>
                确认
              </button>
              <button
                type="button"
                className="small"
                disabled={busy}
                onClick={() => onAction(a.id, 'resolve')}
              >
                解决
              </button>
              <button
                type="button"
                className="small"
                disabled={busy}
                onClick={() => onAction(a.id, 'close')}
              >
                关闭
              </button>
            </div>
          </li>
        )
      })}
    </ul>
  )
}
