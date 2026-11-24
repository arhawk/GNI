import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  fetchCountryChinaAttitude,
  fetchOverview,
  type CountryAttitudeDetail,
  type Overview as OverviewData,
} from '../api'
import { DualMap } from '../components/DualMap'
import { useTimeWindow } from '../TimeWindowContext'

type BoardMode = 'event_time_list' | 'country_china_attitude'

export function OverviewPage() {
  const { window, setDataExtent } = useTimeWindow()
  const [data, setData] = useState<OverviewData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [mode, setMode] = useState<BoardMode>('event_time_list')
  const [attitudeDetail, setAttitudeDetail] = useState<CountryAttitudeDetail | null>(null)
  const [attitudeError, setAttitudeError] = useState<string | null>(null)

  useEffect(() => {
    setError(null)
    const q =
      window.presetDays != null
        ? { days: window.presetDays }
        : {
            start: new Date(window.startMs).toISOString(),
            end: new Date(window.endMs).toISOString(),
          }
    fetchOverview(q)
      .then((payload) => {
        setData(payload)
        const min = payload.meta.data_min ? Date.parse(payload.meta.data_min) : null
        const max = payload.meta.data_max ? Date.parse(payload.meta.data_max) : null
        setDataExtent(
          Number.isFinite(min) ? min : null,
          Number.isFinite(max) ? max : Date.now(),
        )
      })
      .catch((e: Error) => setError(e.message))
  }, [window.startMs, window.endMs, window.presetDays, setDataExtent])

  const onCountryClick = useCallback((countryId: string) => {
    setAttitudeError(null)
    fetchCountryChinaAttitude(countryId)
      .then(setAttitudeDetail)
      .catch((e: Error) => setAttitudeError(e.message))
  }, [])

  if (error) {
    return (
      <div className="panel">
        <p className="error">Failed to load overview: {error}</p>
        <p className="muted">
          Start API: <code>gni api serve</code> then rebuild events.
        </p>
      </div>
    )
  }
  if (!data) return <div className="panel muted">Loading overview…</div>

  const k = data.kpis
  const topicCounts = countsFrom(data.topics)
  const sentCounts = countsFrom(data.sentiment)
  const topicEntries = Object.entries(topicCounts).sort((a, b) => b[1] - a[1])
  const sentEntries = Object.entries(sentCounts).sort((a, b) => b[1] - a[1])
  const timedEvents = [...data.events].sort((a, b) => {
    const ta = Date.parse(a.sort_time || a.event_time || a.window_end || a.window_start || '') || 0
    const tb = Date.parse(b.sort_time || b.event_time || b.window_end || b.window_start || '') || 0
    return tb - ta
  })

  return (
    <div className="overview">
      <p className="muted small">
        Window {data.meta.window_start?.slice(0, 16).replace('T', ' ')} →{' '}
        {data.meta.window_end?.slice(0, 16).replace('T', ' ')} UTC · universe{' '}
        {k.total_articles_universe ?? '—'}
      </p>

      <section className="block">
        <h2>A · Snapshot</h2>
        <div className="kpi-grid">
          <Kpi label="Total articles" value={k.total_articles_universe} hint="in window" />
          <Kpi label="China article count" value={k.china_article_count} hint="raw count" />
          <Kpi
            label="Weighted volume"
            value={fmtNum(k.weighted_article_volume)}
            hint="≠ article count"
          />
          <Kpi
            label="Monitoring countries"
            value={k.monitoring_countries}
            hint="active panel"
          />
          <Kpi
            label="Active sources (registry)"
            value={k.active_sources_registry}
            hint="active_status"
          />
          <Kpi
            label="China-set countries"
            value={k.china_reporting_countries ?? k.country_count}
            hint="in window"
          />
          <Kpi
            label="China-set sources"
            value={k.china_reporting_sources ?? k.source_count}
            hint="in window"
          />
          <Kpi label="Major events" value={k.major_events} hint="proto / Event" />
          <Kpi label="Alerts" value={k.alerts} />
        </div>
      </section>

      <section className="block">
        <div className="block-head">
          <h2>B · Board</h2>
          <div className="seg" role="group" aria-label="Board mode">
            <button
              type="button"
              className={mode === 'event_time_list' ? 'active' : ''}
              onClick={() => {
                setMode('event_time_list')
                setAttitudeDetail(null)
              }}
            >
              Latest events
            </button>
            <button
              type="button"
              className={mode === 'country_china_attitude' ? 'active' : ''}
              onClick={() => setMode('country_china_attitude')}
            >
              China attitude (sample)
            </button>
          </div>
        </div>
        <p className="muted small">{data.meta.map_modes_note}</p>

        {mode === 'event_time_list' && (
          <ul className="event-list board-list">
            {timedEvents.map((e) => (
              <li key={e.id}>
                <Link to={`/events/${e.id}`}>{e.title}</Link>
                <span className="meta">
                  {fmtWhen(e.sort_time || e.event_time || e.window_end)} · {e.article_count} arts ·{' '}
                  {e.status}
                </span>
              </li>
            ))}
            {timedEvents.length === 0 && (
              <li className="muted">
                No events yet — run <code>gni events rebuild</code>.
              </li>
            )}
          </ul>
        )}

        {mode === 'country_china_attitude' && (
          <>
            <DualMap
              mode="country_china_attitude"
              eventPins={[]}
              attitudePins={data.maps.country_china_attitude || []}
              onCountryClick={onCountryClick}
            />
            <div className="attitude-panel">
              {attitudeError && <p className="error">{attitudeError}</p>}
              {!attitudeDetail && !attitudeError && (
                <p className="muted small">
                  Click a colored country for positive / neutral / negative / unknown counts. Grey =
                  no monitored sample.
                </p>
              )}
              {attitudeDetail && (
                <>
                  <h3>
                    {attitudeDetail.country_id} · {attitudeDetail.label}
                  </h3>
                  <p className="muted small">{attitudeDetail.disclaimer}</p>
                  <div className="kpi-grid compact">
                    <Kpi label="Positive" value={attitudeDetail.counts.positive} />
                    <Kpi label="Neutral" value={attitudeDetail.counts.neutral} />
                    <Kpi label="Negative" value={attitudeDetail.counts.negative} />
                    <Kpi label="Unknown" value={attitudeDetail.counts.unknown} />
                  </div>
                  <ul className="event-list">
                    {attitudeDetail.articles.slice(0, 12).map((a) => (
                      <li key={a.article_id}>
                        {a.url ? (
                          <a href={a.url} target="_blank" rel="noreferrer">
                            {a.title || a.article_id}
                          </a>
                        ) : (
                          <span>{a.title || a.article_id}</span>
                        )}
                        <span className="meta">
                          {a.source_name} · {a.sentiment ?? '—'}
                        </span>
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </div>
          </>
        )}
      </section>

      <section className="block">
        <h2>C · Sentiment distribution</h2>
        <p className="muted small">Sentiment labels only — stance is a separate signal.</p>
        <div className="bars">
          {sentEntries.length === 0 && <p className="muted">No sentiment data in window.</p>}
          {sentEntries.map(([label, n]) => (
            <Bar key={label} label={label} value={n} max={sentEntries[0]?.[1] || 1} />
          ))}
        </div>
      </section>

      <section className="block">
        <h2>D · Topic share</h2>
        <p className="muted small">taxonomy_v0.4 — not threat-intelligence classes.</p>
        <div className="bars">
          {topicEntries.length === 0 && <p className="muted">No topic data in window.</p>}
          {topicEntries.slice(0, 12).map(([label, n]) => (
            <Bar key={label} label={label} value={n} max={topicEntries[0]?.[1] || 1} />
          ))}
        </div>
      </section>

      <section className="block">
        <h2>E · Important events & anomalies</h2>
        <p className="muted small">{data.anomalies.note}</p>
        <ul className="event-list">
          {data.anomalies.items.map((item) => (
            <li key={item.event_id}>
              <Link to={`/events/${item.event_id}`}>{item.title}</Link>
              <span className="meta">
                score {item.importance_score ?? '—'} · {item.article_count} arts
              </span>
            </li>
          ))}
          {data.anomalies.items.length === 0 && (
            <li className="muted">
              No events yet — run <code>gni events rebuild</code>.
            </li>
          )}
        </ul>
      </section>
    </div>
  )
}

function Kpi({
  label,
  value,
  hint,
}: {
  label: string
  value: number | string | null | undefined
  hint?: string
}) {
  return (
    <div className="kpi">
      <div className="kpi-value">{value ?? '—'}</div>
      <div className="kpi-label">{label}</div>
      {hint && <div className="kpi-hint">{hint}</div>}
    </div>
  )
}

function Bar({ label, value, max }: { label: string; value: number; max: number }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0
  return (
    <div className="bar-row">
      <span className="bar-label">{label}</span>
      <div className="bar-track">
        <div className="bar-fill" style={{ width: `${pct}%` }} />
      </div>
      <span className="bar-n">{value}</span>
    </div>
  )
}

function fmtNum(n: number | null | undefined) {
  if (n == null) return '—'
  return Number.isInteger(n) ? n : n.toFixed(2)
}

function fmtWhen(iso: string | null | undefined) {
  if (!iso) return '—'
  return iso.slice(0, 16).replace('T', ' ')
}

function countsFrom(blob: unknown): Record<string, number> {
  if (!blob || typeof blob !== 'object') return {}
  const obj = blob as Record<string, unknown>
  const counts = obj.counts
  if (counts && typeof counts === 'object') {
    return Object.fromEntries(
      Object.entries(counts as Record<string, unknown>).filter(
        (e): e is [string, number] => typeof e[1] === 'number',
      ),
    )
  }
  return Object.fromEntries(
    Object.entries(obj).filter((e): e is [string, number] => typeof e[1] === 'number'),
  )
}
