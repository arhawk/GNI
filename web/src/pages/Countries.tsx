import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  fetchCountries,
  fetchCountryDetail,
  type CountryDetail,
  type CountryListItem,
} from '../api'

export function CountriesPage() {
  const [params, setParams] = useSearchParams()
  const selected = (params.get('c') || '').toUpperCase()
  const [list, setList] = useState<CountryListItem[]>([])
  const [detail, setDetail] = useState<CountryDetail | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchCountries()
      .then((r) => {
        setList(r.countries)
        if (!params.get('c') && r.countries[0]) {
          setParams({ c: r.countries[0].country_id }, { replace: true })
        }
      })
      .catch((e: Error) => setError(e.message))
    // eslint-disable-next-line react-hooks/exhaustive-deps -- seed once
  }, [])

  useEffect(() => {
    if (!selected) return
    setDetail(null)
    fetchCountryDetail(selected)
      .then(setDetail)
      .catch((e: Error) => setError(e.message))
  }, [selected])

  if (error) return <div className="panel error">{error}</div>

  return (
    <div className="countries-layout">
      <aside className="countries-list panel">
        <h2>国家</h2>
        <p className="muted small">全球对华监测 · 当前接入国</p>
        <ul className="event-list">
          {list.map((c) => (
            <li key={c.country_id}>
              <button
                type="button"
                className={c.country_id === selected ? 'linkish active' : 'linkish'}
                onClick={() => setParams({ c: c.country_id })}
              >
                {c.name} ({c.country_id})
              </button>
              <span className="meta">
                涉华 {c.china_article_count} · 源 {c.active_sources}/{c.source_count}
              </span>
            </li>
          ))}
        </ul>
      </aside>
      <section className="panel countries-detail">
        {!detail && <p className="muted">加载详情…</p>}
        {detail && (
          <>
            <h2>
              {detail.name} · {detail.country_id}
            </h2>
            <p className="callout">{detail.disclaimer}</p>
            <p className="muted small">涉华纳入文章 {detail.china_article_count}</p>

            <h3>媒体（按来源分区）</h3>
            <table>
              <thead>
                <tr>
                  <th>来源</th>
                  <th>分区</th>
                  <th>状态</th>
                  <th>涉华</th>
                </tr>
              </thead>
              <tbody>
                {detail.media.map((m) => (
                  <tr key={m.source_id}>
                    <td>
                      {m.name}
                      <div className="meta">{m.source_id}</div>
                    </td>
                    <td>{m.source_bucket || '—'}</td>
                    <td>{m.active_status}</td>
                    <td>{m.china_article_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>

            <h3>情感 / 立场（分列）</h3>
            <p className="muted small">
              情感 {JSON.stringify(detail.sentiment_counts)} · 立场{' '}
              {JSON.stringify(detail.stance_counts)}
            </p>

            <h3>议题 / 框架</h3>
            <ul className="event-list">
              {detail.topics_top.map((t) => (
                <li key={t.label}>
                  议题 {t.label}
                  <span className="meta">{t.count}</span>
                </li>
              ))}
              {detail.frames_top.map((t) => (
                <li key={`f-${t.label}`}>
                  框架 {t.label}
                  <span className="meta">{t.count}</span>
                </li>
              ))}
            </ul>

            <h3>近期文章</h3>
            <ul className="event-list">
              {detail.recent_articles.map((a) => (
                <li key={a.article_id}>
                  {a.url ? (
                    <a href={a.url} target="_blank" rel="noreferrer">
                      {a.title}
                    </a>
                  ) : (
                    <span>{a.title}</span>
                  )}
                  <span className="meta">
                    {a.sentiment ?? '—'} · {a.source_id}
                  </span>
                </li>
              ))}
            </ul>
          </>
        )}
      </section>
    </div>
  )
}
