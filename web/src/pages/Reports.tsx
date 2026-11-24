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
          Run API (<code>gni api serve</code>) and optionally <code>gni reports daily</code>.
        </p>
      </div>
    )
  }
  if (!data) return <div className="panel muted">Loading daily report…</div>

  const s = data.sections
  const nar = data.narratives || {}
  const att = s?.attention
  const tone = s?.tone
  const agenda = s?.agenda
  const quality = s?.quality
  const scope = data.country_scope || []

  return (
    <div className="panel report-page">
      <h1>Report center · Daily</h1>
      <p className="muted small">
        {data.period} · {data.schema_version || '—'} · {data.generator || '—'} ·{' '}
        {data.generated_at?.slice(0, 19).replace('T', ' ')} UTC
      </p>

      <h2>1 · 口径</h2>
      <p className="callout">{data.disclaimer}</p>

      <h2>2 · 今日对华关注</h2>
      {nar.attention && <p className="muted small">{nar.attention}</p>}
      <ul className="event-list">
        <li>
          对华相关: <strong>{att?.china_article_count ?? '—'}</strong>
        </li>
        <li>关注占比: {fmt(att?.attention_share)}</li>
        <li>当日采集: {att?.day_article_count ?? '—'}</li>
        <li>
          分析积压: <strong>{att?.missing_analysis ?? '—'}</strong>
        </li>
      </ul>
      <table>
        <thead>
          <tr>
            <th>国家</th>
            <th>当日篇数</th>
            <th>已分析</th>
            <th>涉华纳入</th>
            <th>源数</th>
          </tr>
        </thead>
        <tbody>
          {(att?.coverage_by_country || []).map((r) => (
            <tr key={r.country_id}>
              <td>{r.country_id}</td>
              <td>{r.article_count}</td>
              <td>{r.analyzed_count}</td>
              <td>{r.china_article_count ?? '—'}</td>
              <td>{r.source_count ?? '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2>3 · 语气与立场（分国）</h2>
      <p className="muted small">{tone?.note}</p>
      {nar.tone && <p className="muted small">{nar.tone}</p>}
      <h3>情感</h3>
      <table>
        <thead>
          <tr>
            <th>国家</th>
            <th>n</th>
            <th>+</th>
            <th>~</th>
            <th>−</th>
            <th>mixed</th>
            <th>?</th>
          </tr>
        </thead>
        <tbody>
          {scope.map((cid) => {
            const blob = tone?.by_country?.[cid]
            const sc = blob?.sentiment_counts || {}
            return (
              <tr key={cid}>
                <td>{cid}</td>
                <td>{blob?.analyzed_china ?? 0}</td>
                <td>{sc.positive ?? 0}</td>
                <td>{sc.neutral ?? 0}</td>
                <td>{sc.negative ?? 0}</td>
                <td>{sc.mixed ?? 0}</td>
                <td>{sc.unknown ?? 0}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
      <h3>立场（与情感分列）</h3>
      <table>
        <thead>
          <tr>
            <th>国家</th>
            <th>立场计数</th>
          </tr>
        </thead>
        <tbody>
          {scope.map((cid) => (
            <tr key={cid}>
              <td>{cid}</td>
              <td>
                <code>{JSON.stringify(tone?.by_country?.[cid]?.stance_counts || {})}</code>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2>4 · 议题与说法</h2>
      {nar.agenda && <p className="muted small">{nar.agenda}</p>}
      <div className="kpi-grid compact">
        <div>
          <h3>主议题</h3>
          <ul className="event-list">
            {(agenda?.topics_top || []).map((t) => (
              <li key={t.label}>
                {t.label} · {t.count} ({t.share})
              </li>
            ))}
            {(agenda?.topics_top || []).length === 0 && <li className="muted">无样本</li>}
          </ul>
        </div>
        <div>
          <h3>主框架</h3>
          <ul className="event-list">
            {(agenda?.frames_top || []).map((t) => (
              <li key={t.label}>
                {t.label} · {t.count} ({t.share})
              </li>
            ))}
            {(agenda?.frames_top || []).length === 0 && <li className="muted">无样本</li>}
          </ul>
        </div>
      </div>

      <h2>5 · 事件主线</h2>
      {nar.events && <p className="muted small">{nar.events}</p>}
      <ul className="event-list">
        {(s?.events || []).map((e) => (
          <li key={e.event_id}>
            <Link to={`/events/${e.event_id}`}>{e.title}</Link>
            <span className="meta">
              {(e.event_time || '').slice(0, 16).replace('T', ' ') || '—'} ·{' '}
              {e.multi_source ? '多源' : '单源'} · {(e.reporting_countries || []).join(',')}
            </span>
            <ul className="event-list">
              {(e.evidence || []).slice(0, 4).map((ev) => (
                <li key={ev.article_id} className="muted small">
                  [{ev.country_id}] {ev.title} · {ev.sentiment}/{ev.stance} ·{' '}
                  {ev.article_id.slice(0, 8)}
                </li>
              ))}
            </ul>
          </li>
        ))}
        {(s?.events || []).length === 0 && <li className="muted">无事件 — 先 events rebuild</li>}
      </ul>

      <h2>6 · 代表证据</h2>
      {scope.map((cid) => (
        <div key={cid}>
          <h3>{cid}</h3>
          <ul className="event-list">
            {(s?.evidence?.[cid] || []).map((a) => (
              <li key={a.article_id}>
                {a.url ? (
                  <a href={a.url} target="_blank" rel="noreferrer">
                    {a.title}
                  </a>
                ) : (
                  <span>{a.title}</span>
                )}
                <span className="meta">
                  {a.article_id.slice(0, 8)} · {a.sentiment ?? '—'} / {a.stance ?? '—'} ·{' '}
                  {a.topic ?? '—'} / {a.frame ?? '—'}
                </span>
              </li>
            ))}
            {(s?.evidence?.[cid] || []).length === 0 && <li className="muted">无样本</li>}
          </ul>
        </div>
      ))}

      <h2>7 · 质量与限制</h2>
      {nar.quality && <p className="muted small">{nar.quality}</p>}
      <ul>
        <li>
          分析积压: <strong>{quality?.missing_analysis}</strong>
        </li>
        <li>无样本国家: {(quality?.countries_without_sample || []).join(', ') || '—'}</li>
        {(quality?.notes || []).map((n) => (
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
