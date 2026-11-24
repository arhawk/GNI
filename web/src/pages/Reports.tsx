import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchDailyReport, type DailyReport } from '../api'

export function ReportsPage() {
  const [data, setData] = useState<DailyReport | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchDailyReport()
      .then(setData)
      .catch((e: Error) => setError(e.message))
  }, [])

  if (error) {
    return (
      <div className="panel">
        <p className="error">Failed to load daily report: {error}</p>
        <p className="muted">
          Ensure API is running (<code>gni api serve</code>) and optionally{' '}
          <code>gni reports daily</code>.
        </p>
      </div>
    )
  }
  if (!data) return <div className="panel muted">Loading daily report…</div>

  const ov = data.overview || {}

  return (
    <div className="panel report-page">
      <h1>Report center · Daily</h1>
      <p className="muted small">
        Period {data.period} · generated {data.generated_at?.slice(0, 19).replace('T', ' ')} UTC
      </p>
      <p className="callout">{data.disclaimer}</p>

      <h2>1 · Overview</h2>
      <ul className="event-list">
        <li>
          China-related (≈24h): <strong>{String(ov.china_article_count_24h ?? '—')}</strong>
        </li>
        <li>Attention share: {fmt(ov.attention_share)}</li>
        <li>Sentiment (24h sample): {JSON.stringify(ov.sentiment_counts_24h || {})}</li>
        <li>
          Missing analysis queue: <strong>{data.missing_analysis}</strong>
        </li>
      </ul>

      <h2>2 · Coverage by country (calendar day)</h2>
      <table>
        <thead>
          <tr>
            <th>Country</th>
            <th>Articles</th>
            <th>Analyzed</th>
          </tr>
        </thead>
        <tbody>
          {data.coverage_by_country.map((r) => (
            <tr key={r.country_id}>
              <td>{r.country_id}</td>
              <td>{r.article_count}</td>
              <td>{r.analyzed_count}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2>3 · Event spine (newest first)</h2>
      <ul className="event-list">
        {data.events.map((e) => (
          <li key={e.event_id}>
            <Link to={`/events/${e.event_id}`}>{e.title}</Link>
            <span className="meta">
              {(e.event_time || '').slice(0, 16).replace('T', ' ') || '—'} · {e.article_count} arts
            </span>
            {e.evidence?.length > 0 && (
              <ul className="event-list">
                {e.evidence.slice(0, 3).map((ev) => (
                  <li key={ev.article_id} className="muted small">
                    [{ev.country_id || '?'}] {ev.title || ev.article_id}
                  </li>
                ))}
              </ul>
            )}
          </li>
        ))}
        {data.events.length === 0 && <li className="muted">No events — run events rebuild.</li>}
      </ul>

      <h2>4 · China-related articles (sample)</h2>
      <ul className="event-list">
        {data.china_articles.map((a) => (
          <li key={a.article_id}>
            <span>
              [{a.country_id}/{a.relevance}] {a.title}
            </span>
            <span className="meta">
              {a.sentiment ?? '—'} · {a.stance ?? '—'}
            </span>
          </li>
        ))}
        {data.china_articles.length === 0 && <li className="muted">No China-set articles in window.</li>}
      </ul>

      <h2>5 · Quality notes</h2>
      <ul>
        {data.quality_notes.map((n) => (
          <li key={n} className="muted small">
            {n}
          </li>
        ))}
      </ul>
    </div>
  )
}

function fmt(v: unknown) {
  if (v == null) return '—'
  if (typeof v === 'number') return Number.isInteger(v) ? String(v) : v.toFixed(4)
  return String(v)
}
