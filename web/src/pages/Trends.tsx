import { useEffect, useState } from 'react'
import { fetchTrends, type TrendsPayload } from '../api'
import { useTimeWindow } from '../TimeWindowContext'

export function TrendsPage() {
  const { window } = useTimeWindow()
  const [country, setCountry] = useState('')
  const [data, setData] = useState<TrendsPayload | null>(null)
  const [error, setError] = useState<string | null>(null)

  const days = window.presetDays ?? Math.max(1, Math.round((window.endMs - window.startMs) / 86400000))

  useEffect(() => {
    setError(null)
    fetchTrends(days, country || undefined)
      .then(setData)
      .catch((e: Error) => setError(e.message))
  }, [days, country])

  if (error) return <div className="panel error">加载失败：{error}</div>
  if (!data) return <div className="panel muted">加载趋势…</div>

  const maxVol = Math.max(1, ...data.volume_series.map((d) => d.china_articles))

  return (
    <div className="panel">
      <h2>舆情趋势分析</h2>
      <p className="muted small">{data.note}</p>
      <div className="trends-controls">
        <label>
          国家筛选{' '}
          <select value={country} onChange={(e) => setCountry(e.target.value)}>
            <option value="">全部监测国</option>
            {['US', 'RU', 'DE', 'IN', 'AU'].map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </label>
        <span className="meta">窗口约 {data.days} 天 · 涉华 {data.china_article_count} 篇</span>
      </div>

      <h3>涉华报道量</h3>
      <div className="bars">
        {data.volume_series.length === 0 && <p className="muted">无数据</p>}
        {data.volume_series.map((d) => (
          <div className="bar-row" key={d.date}>
            <span className="bar-label">{d.date.slice(5)}</span>
            <div className="bar-track">
              <div
                className="bar-fill"
                style={{ width: `${Math.round((d.china_articles / maxVol) * 100)}%` }}
              />
            </div>
            <span className="bar-n">{d.china_articles}</span>
          </div>
        ))}
      </div>

      <h3>情感走势（分日）</h3>
      <table>
        <thead>
          <tr>
            <th>日期</th>
            <th>+</th>
            <th>~</th>
            <th>−</th>
            <th>?</th>
          </tr>
        </thead>
        <tbody>
          {data.sentiment_series.map((d) => (
            <tr key={d.date}>
              <td>{d.date}</td>
              <td>{d.positive}</td>
              <td>{d.neutral}</td>
              <td>{d.negative}</td>
              <td>{d.unknown}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3>议题 Top</h3>
      <ul className="event-list">
        {data.topics_top.map((t) => (
          <li key={t.label}>
            {t.label}
            <span className="meta">
              {t.count} · {(t.share * 100).toFixed(0)}%
            </span>
          </li>
        ))}
        {data.topics_top.length === 0 && <li className="muted">无议题样本</li>}
      </ul>
    </div>
  )
}
