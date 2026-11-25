import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  fetchDailyReport,
  fetchMonthlyReport,
  fetchWeeklyReport,
  type DailyReport,
  type PeriodReport,
} from '../api'

type Tab = 'daily' | 'weekly' | 'monthly'

export function ReportsPage() {
  const [tab, setTab] = useState<Tab>('daily')
  const [data, setData] = useState<DailyReport | null>(null)
  const [period, setPeriod] = useState<PeriodReport | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showToneDetail, setShowToneDetail] = useState(false)
  const [showCoverageDetail, setShowCoverageDetail] = useState(false)
  const [showDetail, setShowDetail] = useState(false)

  useEffect(() => {
    setError(null)
    setData(null)
    setPeriod(null)
    if (tab === 'daily') {
      fetchDailyReport()
        .then((payload) => {
          if (!payload?.sections?.summary?.kpis) {
            setError(
              `日报 schema 不匹配（收到 ${payload?.schema_version || 'unknown'}）。请重启 :8000 API。`,
            )
            return
          }
          setData(payload)
        })
        .catch((e: Error) => setError(e.message))
      return
    }
    const loader = tab === 'weekly' ? fetchWeeklyReport() : fetchMonthlyReport()
    loader
      .then((payload) => setPeriod(payload))
      .catch((e: Error) => setError(e.message))
  }, [tab])

  return (
    <div className="panel report-page">
      <div className="report-tabs">
        <button type="button" className={tab === 'daily' ? 'active' : ''} onClick={() => setTab('daily')}>
          每日情报
        </button>
        <button type="button" className={tab === 'weekly' ? 'active' : ''} onClick={() => setTab('weekly')}>
          每周分析
        </button>
        <button
          type="button"
          className={tab === 'monthly' ? 'active' : ''}
          onClick={() => setTab('monthly')}
        >
          每月研判
        </button>
      </div>

      {error && <p className="error">加载失败: {error}</p>}
      {tab === 'daily' && !error && !data && <p className="muted">加载 Daily Brief…</p>}
      {tab === 'daily' && data && (
        <DailyBrief
          data={data}
          showToneDetail={showToneDetail}
          setShowToneDetail={setShowToneDetail}
          showCoverageDetail={showCoverageDetail}
          setShowCoverageDetail={setShowCoverageDetail}
        />
      )}
      {(tab === 'weekly' || tab === 'monthly') && !error && !period && (
        <p className="muted">加载{tab === 'weekly' ? '周报' : '月报'}…</p>
      )}
      {(tab === 'weekly' || tab === 'monthly') && period && (
        <PeriodBrief
          data={period}
          kind={tab === 'weekly' ? '周报' : '月报'}
          showDetail={showDetail}
          setShowDetail={setShowDetail}
        />
      )}
    </div>
  )
}

function PeriodBrief({
  data,
  kind,
  showDetail,
  setShowDetail,
}: {
  data: PeriodReport
  kind: string
  showDetail: boolean
  setShowDetail: (v: boolean) => void
}) {
  const s = data.sections as {
    summary?: {
      overview_text?: string
      kpis?: Record<string, number>
      source_buckets?: Record<string, number>
      outlook?: string
    }
    major_events?: Array<Record<string, unknown>>
    topic_trends?: Array<Record<string, unknown>>
    event_evolution?: Array<Record<string, unknown>>
    cross_country_narrative?: unknown
    sentiment_stance?: { note?: string; by_country_sentiment?: Record<string, Record<string, number>> }
    signals?: Array<Record<string, unknown>>
    quality?: { notes?: string[] }
  }
  const nar = data.narratives || {}
  const kpis = s.summary?.kpis || {}

  return (
    <article className="daily-brief">
      <header className="brief-hero">
        <p className="muted small">
          {kind} · {data.schema_version} · {data.period}
        </p>
        <h1>{kind} · 全球对华监测（当前接入）</h1>
        <p className="callout">{data.disclaimer}</p>
        <p>{s.summary?.overview_text || nar.executive}</p>
        <div className="kpi-grid compact">
          {Object.entries(kpis).map(([k, v]) => (
            <div key={k}>
              <div className="muted small">{k}</div>
              <strong>{v}</strong>
            </div>
          ))}
        </div>
      </header>

      <section className="brief-section">
        <h2>大事与主题</h2>
        <ul className="event-list">
          {(s.major_events || []).slice(0, 8).map((ev) => (
            <li key={String(ev.id)}>
              {ev.href ? (
                <Link to={String(ev.href)}>{String(ev.title)}</Link>
              ) : (
                String(ev.title)
              )}{' '}
              <span className="muted small">· 重要度 {String(ev.importance_score ?? '—')}</span>
            </li>
          ))}
          {(s.major_events || []).length === 0 && <li className="muted">窗口内无事件卡</li>}
        </ul>
        {(s.topic_trends || []).length > 0 && (
          <>
            <h3>主题环比</h3>
            <ul className="event-list">
              {(s.topic_trends || []).slice(0, 8).map((t) => (
                <li key={String(t.topic)}>
                  {String(t.topic)} · Δ {String(t.delta ?? 0)}
                  {t.status ? ` (${String(t.status)})` : ''}
                </li>
              ))}
            </ul>
          </>
        )}
      </section>

      <section className="brief-section">
        <h2>情感 / 立场 / 信号</h2>
        <p className="muted small">{s.sentiment_stance?.note}</p>
        <p>{nar.signals}</p>
        <ul className="event-list">
          {(s.signals || []).slice(0, 6).map((sig) => (
            <li key={String(sig.id)}>
              <strong>{String(sig.title)}</strong>
              <div className="muted small">{String(sig.summary || '')}</div>
            </li>
          ))}
        </ul>
        {s.summary?.outlook && <p className="callout">{s.summary.outlook}</p>}
      </section>

      <section className="brief-section">
        <button type="button" onClick={() => setShowDetail(!showDetail)}>
          {showDetail ? '收起明细' : '展开数据明细'}
        </button>
        {showDetail && (
          <pre className="muted small" style={{ whiteSpace: 'pre-wrap' }}>
            {JSON.stringify(
              {
                source_buckets: s.summary?.source_buckets,
                event_evolution: s.event_evolution,
                cross_country_narrative: s.cross_country_narrative,
                sentiment: s.sentiment_stance?.by_country_sentiment,
                quality: s.quality,
              },
              null,
              2,
            )}
          </pre>
        )}
      </section>
    </article>
  )
}

function SentimentBar({
  shares,
  n,
  compact,
}: {
  shares?: { positive: number; neutral: number; negative: number }
  n?: number
  compact?: boolean
}) {
  const pos = Math.max(0, shares?.positive ?? 0)
  const neu = Math.max(0, shares?.neutral ?? 0)
  const neg = Math.max(0, shares?.negative ?? 0)
  const sum = pos + neu + neg
  if (!sum || !(n && n > 0)) {
    return <span className="muted small">{compact ? '无情感样本' : '暂无媒体情感样本'}</span>
  }
  return (
    <div className={`sentiment-bar-wrap${compact ? ' compact' : ''}`} title="正面 / 中立 / 负面 · 情感语气 ≠ 立场">
      <div className="sentiment-bar" role="img" aria-label={`正面 ${Math.round(pos * 100)}% 中立 ${Math.round(neu * 100)}% 负面 ${Math.round(neg * 100)}%`}>
        <span className="seg pos" style={{ flex: pos }} />
        <span className="seg neu" style={{ flex: neu }} />
        <span className="seg neg" style={{ flex: neg }} />
      </div>
      {!compact && (
        <div className="sentiment-legend muted small">
          <span className="leg pos">正面 {Math.round(pos * 100)}%</span>
          <span className="leg neu">中立 {Math.round(neu * 100)}%</span>
          <span className="leg neg">负面 {Math.round(neg * 100)}%</span>
          <span>· n={n}</span>
        </div>
      )}
    </div>
  )
}

function TopicBars({
  topics,
}: {
  topics: Array<{ label: string; count: number; share: number }>
}) {
  const max = Math.max(1, ...topics.map((t) => t.count))
  if (topics.length === 0) return <p className="muted">无主题样本</p>
  return (
    <div className="bars topic-bars">
      {topics.map((t) => (
        <div className="bar-row" key={t.label}>
          <div className="bar-label">
            <Link to="/trends">{t.label}</Link>
          </div>
          <div className="bar-track">
            <div className="bar-fill" style={{ width: `${(t.count / max) * 100}%` }} />
          </div>
          <div className="bar-n">{t.count}</div>
        </div>
      ))}
    </div>
  )
}

function MediaVolumeSpark({
  today,
  yesterday,
  weekAvg,
}: {
  today: number
  yesterday?: number
  weekAvg?: number
}) {
  const vals = [yesterday ?? 0, weekAvg ?? 0, today].map((v) => Math.max(0, Number(v) || 0))
  const max = Math.max(1, ...vals)
  const labels = ['昨日', '近7日均', '今日']
  return (
    <div className="media-spark" title="仅媒体报道量，无社媒公众兴趣">
      <div className="media-spark-bars">
        {vals.map((v, i) => (
          <div key={labels[i]} className="media-spark-col">
            <div className="media-spark-bar" style={{ height: `${(v / max) * 100}%` }} />
            <span className="muted small">{labels[i]}</span>
            <strong className="small">{v}</strong>
          </div>
        ))}
      </div>
      <p className="muted small">媒体报道量对比（无社媒栏）</p>
    </div>
  )
}

function DailyBrief({
  data,
  showToneDetail,
  setShowToneDetail,
  showCoverageDetail,
  setShowCoverageDetail,
}: {
  data: DailyReport
  showToneDetail: boolean
  setShowToneDetail: (v: boolean) => void
  showCoverageDetail: boolean
  setShowCoverageDetail: (v: boolean) => void
}) {
  const s = data.sections
  const summary = s.summary
  const kpis = summary.kpis
  const nar = data.narratives || {}
  const cmp = summary.comparisons
  const connectedN = data.connected?.countries ?? data.country_scope?.length ?? 0
  const stories = kpis.stories ?? data.event_count ?? (s.major_events || []).length
  const articles = kpis.articles_analyzed ?? kpis.china_articles
  const sourcesCited = kpis.sources_cited ?? kpis.reporting_sources

  return (
    <div className="daily-brief daily-brief-v3">
      <header className="brief-header">
        <div className="brief-eyebrow">DAILY BRIEF · 每日情报</div>
        <h1>全球对华监测</h1>
        <p className="muted small">
          当前接入 {connectedN} 国
          {data.connected?.active_sources != null ? ` · 活跃源 ${data.connected.active_sources}` : ''} ·{' '}
          {data.period} · {data.schema_version}
        </p>
        <p className="callout">{data.disclaimer}</p>
      </header>

      <section className="brief-section brief-discover">
        <h2>1 · 快速发现</h2>
        <p className="brief-lede">{summary.overview_text || nar.executive}</p>
        <div className="kpi-grid brief-kpis brief-kpis-hero">
          <Kpi label="今日要闻" value={stories} hint="重大/相关事件卡" />
          <Kpi
            label="涉华文章"
            value={articles}
            hint={deltaHint(cmp?.vs_yesterday?.delta, '较昨日')}
          />
          <Kpi label="引用来源" value={sourcesCited} hint={`本日报道国 ${kpis.reporting_countries}`} />
        </div>
        <MediaVolumeSpark
          today={kpis.china_articles}
          yesterday={cmp?.vs_yesterday?.china_articles}
          weekAvg={cmp?.vs_7d_avg?.china_articles}
        />
        <h3>今日值得关注</h3>
        <ol className="brief-changes">
          {(summary.top_changes || []).map((c) => (
            <li key={c.title}>
              {c.href ? <Link to={c.href}>{c.title}</Link> : <strong>{c.title}</strong>}
              <span className="muted"> — {c.summary}</span>
            </li>
          ))}
          {(summary.top_changes || []).length === 0 && <li className="muted">暂无突出变化信号</li>}
        </ol>
      </section>

      <section className="brief-section">
        <div className="brief-section-head">
          <h2>2 · 今日重大事件</h2>
          <p className="muted small sentiment-legend-inline">
            情感条：<span className="leg pos">正面</span> / <span className="leg neu">中立</span> /{' '}
            <span className="leg neg">负面</span>（≠立场、≠国家态度）
          </p>
        </div>
        <ul className="story-list">
          {(s.major_events || []).map((ev, i) => (
            <li key={ev.event_id} className="story-row">
              <span className="story-idx">{String(i + 1).padStart(2, '0')}</span>
              <div className="story-main">
                <Link className="story-title" to={ev.href || `/events/${ev.event_id}`}>
                  {ev.title}
                </Link>
                <div className="muted small">
                  {ev.coverage?.article_count ?? 0} 篇 · {ev.coverage?.country_count ?? 0} 国
                  {(ev.importance_score ?? 0) >= 0.7 ? ' · 高重要性' : ''}
                </div>
              </div>
              <div className="story-sentiment">
                <SentimentBar shares={ev.sentiment_shares} n={ev.sentiment_n} compact />
                <span className="muted small tabular">{ev.coverage?.article_count ?? 0}</span>
              </div>
            </li>
          ))}
          {(s.major_events || []).length === 0 && (
            <li className="muted">当日无重大/相关事件 — 可先运行 events rebuild。</li>
          )}
        </ul>

        {(s.major_events || []).map((ev, i) => (
          <article key={`detail-${ev.event_id}`} className="event-card">
            <div className="event-card-head">
              <span className="event-idx">事件 {String(i + 1).padStart(2, '0')}</span>
              {(ev.importance_score ?? 0) >= 0.7 && <span className="sev sev-high">高重要性</span>}
              {ev.event_type && <span className="meta">{ev.event_type}</span>}
            </div>
            <h3>
              <Link to={ev.href || `/events/${ev.event_id}`}>{ev.title}</Link>
            </h3>
            <SentimentBar shares={ev.sentiment_shares} n={ev.sentiment_n} />
            <p>{ev.overview_text}</p>
            <div className="muted small">
              event_time: {(ev.event_time || '—').toString().slice(0, 16).replace('T', ' ')} · first_seen:{' '}
              {(ev.first_seen_at || '—').toString().slice(0, 16).replace('T', ' ')}
            </div>
            <dl className="event-core">
              <div>
                <dt>主体</dt>
                <dd>{ev.core?.actor || '—'}</dd>
              </div>
              <div>
                <dt>行动</dt>
                <dd>{ev.core?.action || '—'}</dd>
              </div>
              <div>
                <dt>对象</dt>
                <dd>{ev.core?.object || '—'}</dd>
              </div>
              <div>
                <dt>覆盖</dt>
                <dd>
                  {ev.coverage?.article_count ?? 0} 篇 · {ev.coverage?.country_count ?? 0} 国 ·{' '}
                  {ev.coverage?.source_count ?? 0} 源
                </dd>
              </div>
            </dl>
            {(ev.by_country_views || []).length > 0 && (
              <>
                <h4>分国报道视角</h4>
                <ul className="event-list">
                  {ev.by_country_views!.map((v) => (
                    <li key={v.country_id}>
                      <Link to={v.href || `/countries?c=${v.country_id}`}>{v.country_id}</Link> · {v.article_count}{' '}
                      篇 · 情感 {v.dominant_sentiment || '—'} / 立场 {v.dominant_stance || '—'}
                      {v.frame ? ` · 框架 ${v.frame}` : ''}
                    </li>
                  ))}
                </ul>
              </>
            )}
            <h4>证据</h4>
            <ul className="event-list">
              {(ev.evidence || []).slice(0, 6).map((evi) => (
                <li key={evi.article_id} className="muted small">
                  [{evi.country_id}]{' '}
                  {evi.url ? (
                    <a href={evi.url} target="_blank" rel="noreferrer">
                      {evi.title}
                    </a>
                  ) : (
                    evi.title
                  )}{' '}
                  · {evi.sentiment}/{evi.stance}
                </li>
              ))}
            </ul>
          </article>
        ))}
      </section>

      <section className="brief-section brief-two-col">
        <div>
          <h2>3 · 主题分布</h2>
          <TopicBars topics={s.coverage.topics_top || []} />
        </div>
        <div>
          <h2>4 · 全球监测覆盖（当前接入）</h2>
          <p className="muted small">{s.coverage.note}</p>
          {nar.coverage && <p>{nar.coverage}</p>}
          <ul className="coverage-chips">
            {(data.connected?.country_ids || data.country_scope || []).map((cid) => {
              const row = s.coverage.by_country.find((r) => r.country_id === cid)
              return (
                <li key={cid}>
                  <Link to={`/countries?c=${cid}`}>{cid}</Link>
                  <span className="muted small"> · {row?.article_count ?? 0} 篇</span>
                </li>
              )
            })}
          </ul>
          <button type="button" className="linkish" onClick={() => setShowCoverageDetail(!showCoverageDetail)}>
            {showCoverageDetail ? '收起国家/媒体明细' : '展开国家/媒体明细'}
          </button>
          {showCoverageDetail && (
            <table>
              <thead>
                <tr>
                  <th>国家</th>
                  <th>涉华篇数</th>
                  <th>加权量</th>
                  <th>源数</th>
                </tr>
              </thead>
              <tbody>
                {s.coverage.by_country.map((r) => (
                  <tr key={r.country_id}>
                    <td>
                      <Link to={r.href || `/countries?c=${r.country_id}`}>{r.country_id}</Link>
                    </td>
                    <td>{r.article_count}</td>
                    <td>{r.weighted_volume ?? '—'}</td>
                    <td>{r.source_count ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>

      <section className="brief-section">
        <h2>5 · 情感与立场</h2>
        <p className="muted small">{s.tone.note}</p>
        {nar.tone && <p className="muted small">{nar.tone}</p>}
        <ul className="tone-summaries">
          {s.tone.by_country.map((row) => (
            <li key={row.country_id}>
              <Link to={row.href || `/countries?c=${row.country_id}`}>{row.country_id}</Link> — {row.summary_text}
            </li>
          ))}
        </ul>
        <button type="button" className="linkish" onClick={() => setShowToneDetail(!showToneDetail)}>
          {showToneDetail ? '收起计数表' : '展开情感/立场计数表'}
        </button>
        {showToneDetail && (
          <table>
            <thead>
              <tr>
                <th>国家</th>
                <th>n</th>
                <th>情感</th>
                <th>立场</th>
              </tr>
            </thead>
            <tbody>
              {s.tone.by_country.map((row) => (
                <tr key={row.country_id}>
                  <td>{row.country_id}</td>
                  <td>{row.n}</td>
                  <td>
                    <code>{JSON.stringify(row.sentiment_counts)}</code>
                  </td>
                  <td>
                    <code>{JSON.stringify(row.stance_counts)}</code>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="brief-section">
        <h2>6 · 新兴信号与预警</h2>
        {nar.signals && <p className="muted small">{nar.signals}</p>}
        <ul className="event-list">
          {(s.signals || []).map((sig) => (
            <li key={sig.id || sig.title}>
              <span className={`sev sev-${sig.severity === 'high' ? 'high' : sig.severity === 'medium' ? 'medium' : 'low'}`}>
                {sig.status || 'needs_review'}
              </span>{' '}
              <Link to={sig.href || '/alerts'}>{sig.title}</Link>
              <div className="muted small">{sig.summary}</div>
            </li>
          ))}
          {(s.signals || []).length === 0 && <li className="muted">当日无情报信号</li>}
        </ul>
      </section>

      <section className="brief-section">
        <h2>7 · 数据覆盖说明</h2>
        {nar.quality && <p>{nar.quality}</p>}
        <ul>
          <li>
            分析积压: <strong>{s.quality.missing_analysis}</strong>
          </li>
          <li>当前无报道国家: {(s.quality.countries_without_sample || []).join(', ') || '—'}</li>
          {(s.quality.notes || []).map((n) => (
            <li key={n} className="muted small">
              {n}
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}

function Kpi({ label, value, hint }: { label: string; value: number; hint?: string }) {
  return (
    <div className="brief-kpi">
      <div className="brief-kpi-value">{value}</div>
      <div className="brief-kpi-label">{label}</div>
      {hint && <div className="muted small">{hint}</div>}
    </div>
  )
}

function deltaHint(delta: number | undefined, prefix: string) {
  if (delta == null) return undefined
  const sign = delta > 0 ? '+' : ''
  return `${prefix} ${sign}${delta}`
}
