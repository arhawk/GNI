import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchEvents, type EventSummary } from '../api'

export function EventsPage() {
  const [events, setEvents] = useState<EventSummary[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchEvents(50)
      .then((r) => setEvents(r.events))
      .catch((e: Error) => setError(e.message))
  }, [])

  if (error) return <div className="panel error">{error}</div>

  return (
    <div className="panel">
      <h2>News & Events</h2>
      <p className="muted small">
        Phase 1 proto-Events from rule clustering — not a full cross-language event graph.
      </p>
      <ul className="event-list">
        {events.map((e) => (
          <li key={e.id}>
            <Link to={`/events/${e.id}`}>{e.title}</Link>
            <span className="meta">
              {e.status} · {e.article_count} arts · score {e.importance_score ?? '—'}
              {!e.has_physical_location && ' · no physical pin'}
            </span>
          </li>
        ))}
        {events.length === 0 && !error && (
          <li className="muted">Empty — run <code>gni events rebuild</code>.</li>
        )}
      </ul>
    </div>
  )
}
