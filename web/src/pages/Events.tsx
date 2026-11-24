import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchEvents, type EventSummary } from '../api'

export function EventsPage() {
  const [events, setEvents] = useState<EventSummary[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchEvents(50)
      .then((r) => {
        const sorted = [...r.events].sort((a, b) => {
          const ta =
            Date.parse(a.sort_time || a.event_time || a.window_end || a.window_start || '') || 0
          const tb =
            Date.parse(b.sort_time || b.event_time || b.window_end || b.window_start || '') || 0
          return tb - ta
        })
        setEvents(sorted)
      })
      .catch((e: Error) => setError(e.message))
  }, [])

  if (error) return <div className="panel error">{error}</div>

  return (
    <div className="panel">
      <h2>新闻中心 · 事件</h2>
      <p className="muted small">按事件时间倒序；无地理坐标也可出现在列表中。</p>
      <ul className="event-list">
        {events.map((e) => (
          <li key={e.id}>
            <Link to={`/events/${e.id}`}>{e.title}</Link>
            <span className="meta">
              {(e.sort_time || e.event_time || e.window_end || '').slice(0, 16).replace('T', ' ') ||
                '—'}{' '}
              · {e.status} · {e.article_count} arts
            </span>
          </li>
        ))}
        {events.length === 0 && !error && (
          <li className="muted">
            Empty — run <code>gni events rebuild</code>.
          </li>
        )}
      </ul>
    </div>
  )
}
