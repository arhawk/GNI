import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { fetchEventDetail, type EventDetail } from '../api'
import { DualMap } from '../components/DualMap'

type ViewTab = 'where' | 'who' | 'how' | 'timeline'

export function EventDetailPage() {
  const { id } = useParams<{ id: string }>()
  const [data, setData] = useState<EventDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [tab, setTab] = useState<ViewTab>('where')

  useEffect(() => {
    if (!id) return
    fetchEventDetail(id)
      .then(setData)
      .catch((e: Error) => setError(e.message))
  }, [id])

  if (error) return <div className="panel error">Event load failed: {error}</div>
  if (!data) return <div className="panel muted">Loading event…</div>

  const e = data.event
  const where = data.views.where
  const who = data.views.who_reports
  const how = data.views.how_they_frame

  return (
    <div className="event-detail">
      <p className="crumb">
        <Link to="/events">Events</Link> / {e.status}
      </p>
      <header className="event-head">
        <h1>{e.title}</h1>
        <p className="muted">{e.summary}</p>
        <div className="meta-row">
          <span>Type: {e.event_type ?? '—'}</span>
          <span>
            Window: {e.window_start?.slice(0, 10) ?? '—'} → {e.window_end?.slice(0, 10) ?? '—'}
          </span>
          <span>Importance: {e.importance_score ?? '—'}</span>
          <span>Physical location: {e.has_physical_location ? 'yes' : 'no'}</span>
          {(e.actor_key || e.action_key) && (
            <span>
              Fingerprint: {e.actor_key ?? '?'} / {e.action_key ?? '?'} / {e.object_key ?? '?'}
            </span>
          )}
        </div>
        {data.metrics?.sentiment_shares && (
          <p className="muted small">
            Rolled-up sentiment (equal article share):{' '}
            {Object.entries(data.metrics.sentiment_shares)
              .map(([k, v]) => `${k} ${(v * 100).toFixed(0)}%`)
              .join(' · ')}
            {data.metrics.article_count != null && ` · ${data.metrics.article_count} articles`}
          </p>
        )}
        {data.participants.length > 0 && (
          <p className="participants">
            Participants:{' '}
            {data.participants.map((p) => p.participant_name || p.participant_id).join(', ')}
          </p>
        )}
      </header>

      <div className="seg" role="tablist">
        {(
          [
            ['where', 'Geographic (Where)'],
            ['who', 'Country (Who reports)'],
            ['how', 'Narrative (How they frame)'],
            ['timeline', 'Timeline'],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={tab === key}
            className={tab === key ? 'active' : ''}
            onClick={() => setTab(key)}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === 'where' && (
        <section className="panel">
          <h2>Where</h2>
          {where.note && <p className="callout">{where.note}</p>}
          {where.locations.length === 0 ? (
            <p className="muted">
              No typed locations. Policy/statement clusters may have no single physical site —
              do not pin reporting countries here.
            </p>
          ) : (
            <ul>
              {where.locations.map((loc, i) => (
                <li key={i}>
                  <strong>{loc.location_type}</strong> — {loc.label ?? loc.country_id ?? '—'}
                  {loc.lat != null && loc.lon != null && (
                    <span className="muted">
                      {' '}
                      ({loc.lat.toFixed(2)}, {loc.lon.toFixed(2)})
                    </span>
                  )}
                </li>
              ))}
            </ul>
          )}
          <DualMap
            mode="event_geography"
            eventPins={where.locations
              .filter((l) => l.lat != null && l.lon != null)
              .map((l) => ({
                event_id: e.id,
                title: e.title,
                location_type: l.location_type,
                lat: l.lat as number,
                lon: l.lon as number,
                layer: 'event_geography',
              }))}
          />
        </section>
      )}

      {tab === 'who' && (
        <section className="panel">
          <h2>Who reports</h2>
          <p className="muted small">
            Country → media → articles. Media country ≠ government stance.
          </p>
          <DualMap
            mode="reporting_source"
            eventPins={[]}
            reportingPins={who.reporting_map}
          />
          {who.countries.map((c) => (
            <div key={c.country_id} className="country-block">
              <h3>
                {c.country_id}{' '}
                <span className="muted">({c.article_count} articles)</span>
              </h3>
              {c.media.map((m) => (
                <div key={m.source_id} className="media-block">
                  <h4>
                    {m.source_name}{' '}
                    <span className="muted">· {m.article_count}</span>
                  </h4>
                  <ul>
                    {m.articles.map((a) => (
                      <li key={a.article_id}>
                        {a.url ? (
                          <a href={a.url} target="_blank" rel="noreferrer">
                            {a.title}
                          </a>
                        ) : (
                          a.title
                        )}
                        <span className="meta">
                          {[a.sentiment && `sent:${a.sentiment}`, a.frame && `frame:${a.frame}`]
                            .filter(Boolean)
                            .join(' · ')}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          ))}
          {who.countries.length === 0 && <p className="muted">No linked articles.</p>}
        </section>
      )}

      {tab === 'how' && (
        <section className="panel">
          <h2>How they frame</h2>
          <p className="muted small">
            Narratives are independent of country; evidence must point back to articles.
          </p>
          {how.narratives.length === 0 && (
            <p className="muted">No narrative clusters yet for this event.</p>
          )}
          {how.narratives.map((n) => (
            <div key={n.id} className="narrative-block">
              <h3>{n.label}</h3>
              {n.summary && <p>{n.summary}</p>}
              <ul>
                {n.evidence.map((ev, i) => (
                  <li key={`${ev.article_id}-${i}`}>
                    {ev.title ?? ev.article_id}
                    {ev.quote && <blockquote>{ev.quote}</blockquote>}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </section>
      )}

      {tab === 'timeline' && (
        <section className="panel">
          <h2>Timeline</h2>
          <ol className="timeline">
            {data.timeline.map((t, i) => (
              <li key={`${t.article_id}-${i}`}>
                <time>{t.at.slice(0, 16).replace('T', ' ')}</time>
                <span className="kind">{t.kind}</span>
                <span>{t.title}</span>
                {t.country_id && <span className="muted"> · {t.country_id}</span>}
              </li>
            ))}
            {data.timeline.length === 0 && <li className="muted">No timeline points.</li>}
          </ol>
        </section>
      )}
    </div>
  )
}
