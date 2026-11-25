import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchDailyReport, type DailyReport } from '../api'

type Tab = 'daily' | 'weekly' | 'monthly'

export function ReportsPage() {
  const [tab, setTab] = useState<Tab>('daily')
  const [data, setData] = useState<DailyReport | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showToneDetail, setShowToneDetail] = useState(false)
  const [showCoverageDetail, setShowCoverageDetail] = useState(false)

  useEffect(() => {
    if (tab !== 'daily') return
    setError(null)
    setData(null)
    fetchDailyReport()
      .then(setData)
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

      {tab === 'weekly' && <PlaceholderKind kind="周报" focus="变化、演化、跨国叙事" />}
      {tab === 'monthly' && <PlaceholderKind kind="月报" focus="长期趋势、格局、展望" />}
      {tab === 'daily' && error && (
        <p className="error">加载日报失败: {error}</p>
      )}
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
    </div>
  )
}

function PlaceholderKind({ kind, focus }: { kind: string; focus: string }) {
  return (
    <div className="report-placeholder">
      <h1>{kind} · 规划中</h1>
      <p className="muted">
        定位：{focus}。规格已冻结，实现后置于日报链路验收之后。见仓库{' '}
        <code>docs/{kind === '周报' ? 'WEEKLY' : 'MONTHLY'}_REPORT_SPEC.md</code>。
      </p>
      <p className="callout">三层产品共享底层数据，但不是「更长的新闻摘要」。</p>
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

  return (
    <div className="daily-brief">
      <header className="brief-header">
        <div className="brief-eyebrow">DAILY BRIEF · 每日情报</div>
        <h1>Global China Media Intelligence</h1>
        <p className="muted small">
          {data.period} · {data.schema_version} · {data.generator} ·{' '}
          {data.generated_at?.slice(0, 19).replace('T', ' ')} UTC
          {data.validation && (
            <>
              {' '}
              · validation {data.validation.ok ? 'ok' : 'issues'}
            </>
          )}
        </p>
        <p className="callout">{data.disclaimer}</p>
      </header>

      <section className="brief-section">
        <h2>1 · 今日摘要</h2>
        <p className="brief-lede">{summary.overview_text || nar.executive}</p>
        <div className="kpi-grid brief-kpis">
          <Kpi label="涉华文章" value={kpis.china_articles} hint={deltaHint(cmp?.vs_yesterday?.delta, '较昨日')} />
          <Kpi label="报道国家" value={kpis.reporting_countries} />
          <Kpi label="新增事件" value={kpis.new_events} />
          <Kpi label="重大事件" value={kpis.major_events} hint={`近7日日均涉华 ${cmp?.vs_7d_avg?.china_articles ?? '—'}`} />
        </div>
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
        <h2>2 · 今日重大事件</h2>
        <p className="muted small">按重要性排序；文章为证据。event_time ≠ first_seen_at。</p>
        {(s.major_events || []).map((ev, i) => (
          <article key={ev.event_id} className="event-card">
            <div className="event-card-head">
              <span className="event-idx">事件 {String(i + 1).padStart(2, '0')}</span>
              {(ev.importance_score ?? 0) >= 0.7 && <span className="sev sev-high">高重要性</span>}
              {ev.event_type && <span className="meta">{ev.event_type}</span>}
            </div>
            <h3>
              <Link to={ev.href || `/events/${ev.event_id}`}>{ev.title}</Link>
            </h3>
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
                <h4>分国报道视角（样本）</h4>
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
            {(ev.follow_ups || []).length > 0 && (
              <>
                <h4>后续关注</h4>
                <ul className="event-list">
                  {ev.follow_ups!.map((q) => (
                    <li key={q}>{q}</li>
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
        {(s.major_events || []).length === 0 && (
          <p className="muted">当日无重大/相关事件 — 可先运行 events rebuild。</p>
        )}
      </section>

      <section className="brief-section">
        <h2>3 · 全球报道概况</h2>
        <p className="muted small">{s.coverage.note}</p>
        {nar.coverage && <p>{nar.coverage}</p>}
        <div className="kpi-grid compact">
          <div>
            <h3>主议题</h3>
            <ul className="event-list">
              {(s.coverage.topics_top || []).map((t) => (
                <li key={t.label}>
                  <Link to="/trends">{t.label}</Link> · {t.count}
                </li>
              ))}
              {(s.coverage.topics_top || []).length === 0 && <li className="muted">无样本</li>}
            </ul>
          </div>
          <div>
            <h3>主框架</h3>
            <ul className="event-list">
              {(s.coverage.frames_top || []).map((t) => (
                <li key={t.label}>
                  {t.label} · {t.count}
                </li>
              ))}
              {(s.coverage.frames_top || []).length === 0 && <li className="muted">无样本</li>}
            </ul>
          </div>
        </div>
        <button type="button" className="linkish" onClick={() => setShowCoverageDetail(!showCoverageDetail)}>
          {showCoverageDetail ? '收起数据明细' : '展开国家/媒体明细'}
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
      </section>

      <section className="brief-section">
        <h2>4 · 情感与立场</h2>
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
        <h2>5 · 新兴信号与预警</h2>
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
        <h2>6 · 数据覆盖说明</h2>
        {nar.quality && <p>{nar.quality}</p>}
        <ul>
          <li>
            分析积压: <strong>{s.quality.missing_analysis}</strong>
          </li>
          <li>无样本国家: {(s.quality.countries_without_sample || []).join(', ') || '—'}</li>
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
