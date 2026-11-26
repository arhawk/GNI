import { Link } from 'react-router-dom'
import './tables.css'

export type EventRiskRow = {
  event_id: string
  title: string
  href?: string
  primary_country?: string | null
  source_bucket_zh?: string | null
  source_bucket?: string | null
  event_type?: string | null
  narrative_labels?: string[]
  sentiment_label?: string | null
  sentiment_n?: number
  risk_level?: string
  sectors?: Array<{ id: string; label: string }>
  coverage?: { article_count?: number; country_count?: number; source_count?: number }
  anomaly?: { flagged?: boolean; reasons?: string[] }
}

function riskPillClass(level?: string) {
  if (level === 'high') return 'gni-pill-neg'
  if (level === 'medium' || level === 'watch') return 'gni-pill-warn'
  return 'gni-pill-neu'
}

export function EventRiskTable({ events }: { events: EventRiskRow[] }) {
  return (
    <div className="gni-table-block">
      <div className="gni-table-wrap">
        <table className="gni-table">
          <thead>
            <tr>
              <th>#</th>
              <th>主国 / 媒体</th>
              <th>事件标题 · 叙事/赛道 · 异动原因</th>
              <th className="gni-num">覆盖</th>
              <th>情感 / 立场</th>
              <th>风险等级</th>
            </tr>
          </thead>
          <tbody>
            {events.map((ev, i) => {
              const flagged = Boolean(ev.anomaly?.flagged)
              const tags = [
                ...(ev.narrative_labels || []),
                ...(ev.sectors || []).filter((s) => s.id !== 'unmapped').map((s) => s.label),
              ].slice(0, 4)
              return (
                <tr key={ev.event_id} className={flagged ? 'gni-row-flag' : undefined}>
                  <td className="gni-mono muted">{String(i + 1).padStart(2, '0')}</td>
                  <td>
                    <strong>{ev.primary_country || '—'}</strong>
                    <div className="muted small">{ev.source_bucket_zh || ev.source_bucket || '—'}</div>
                  </td>
                  <td>
                    <Link to={ev.href || `/events/${ev.event_id}`}>
                      <strong>{ev.title}</strong>
                    </Link>
                    {tags.length > 0 && (
                      <div>
                        {tags.map((t) => (
                          <span key={t} className="gni-tag">
                            {t}
                          </span>
                        ))}
                      </div>
                    )}
                    {flagged && (ev.anomaly?.reasons || []).length > 0 && (
                      <div className="gni-c-neg small">{(ev.anomaly?.reasons || []).join('；')}</div>
                    )}
                  </td>
                  <td className="gni-num">
                    {ev.coverage?.article_count != null ? (
                      <>
                        <strong>{ev.coverage.article_count} 篇</strong>
                        <div className="muted small">
                          {ev.coverage.country_count ?? 0} 国 · {ev.coverage.source_count ?? 0} 源
                        </div>
                      </>
                    ) : (
                      '—'
                    )}
                  </td>
                  <td className="small muted">{ev.sentiment_label || '—'}</td>
                  <td>
                    <span className={`gni-pill ${riskPillClass(ev.risk_level)}`}>
                      {(ev.risk_level || 'unmapped').toUpperCase()}
                    </span>
                  </td>
                </tr>
              )
            })}
            {events.length === 0 && (
              <tr>
                <td colSpan={6} className="muted">
                  当日无重点事件 — 可先运行 events rebuild
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
