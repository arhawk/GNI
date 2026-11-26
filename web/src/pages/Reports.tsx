import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  analyzeReport,
  fetchDailyReport,
  fetchMonthlyReport,
  fetchWeeklyReport,
  type DailyReport,
  type PeriodReport,
  type V1StatsByScope,
} from '../api'
import {
  CrossCountryAnalysisBlock,
  EventInterpretationCards,
  IntelligenceHeader,
  OutlookSignalsPanel,
  StanceAnalysisBlock,
  TopicTrendAnalysisBlock,
} from '../components/narrative'
import {
  EventRiskTable,
  SourceOpsTable,
  StanceMatrixTable,
  TrendDeltaTable,
} from '../components/tables'

type Tab = 'daily' | 'weekly' | 'monthly'

export function ReportsPage() {
  const [tab, setTab] = useState<Tab>('daily')
  const [data, setData] = useState<DailyReport | null>(null)
  const [period, setPeriod] = useState<PeriodReport | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [analyzeError, setAnalyzeError] = useState<string | null>(null)
  const [showToneDetail, setShowToneDetail] = useState(false)
  const [showCoverageDetail, setShowCoverageDetail] = useState(false)
  const [showDetail, setShowDetail] = useState(false)

  useEffect(() => {
    setError(null)
    setAnalyzeError(null)
    setData(null)
    setPeriod(null)
    if (tab === 'daily') {
      fetchDailyReport()
        .then((payload) => {
          const v4 =
            payload?.schema_version === 'daily_report_schema_v4' &&
            payload?.sections?.overview_stats != null &&
            payload?.sections?.summary?.risk_banner != null
          if (!v4) {
            setError(
              `日报空壳/旧版（收到 ${payload?.schema_version || 'unknown'}，缺 overview_stats 或 risk_banner）。请重启 gni api serve 加载 daily_report_schema_v4，勿继续渲染空五段。`,
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

  async function triggerAnalyze(reportType: Tab, opts: { force?: boolean; tasks?: string[] }) {
    setAnalyzing(true)
    setAnalyzeError(null)
    try {
      const periodArg =
        reportType === 'daily'
          ? data?.period
          : reportType === 'monthly'
            ? period?.period
            : period?.period?.split('_')[1]
      const updated = await analyzeReport<DailyReport | PeriodReport>(reportType, {
        period: periodArg,
        force: opts.force,
        tasks: opts.tasks,
      })
      if (reportType === 'daily') {
        setData(updated as DailyReport)
      } else {
        setPeriod(updated as PeriodReport)
      }
    } catch (e) {
      setAnalyzeError(e instanceof Error ? e.message : String(e))
    } finally {
      setAnalyzing(false)
    }
  }

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
          analyzing={analyzing}
          analyzeError={analyzeError}
          onGenerate={(force) => triggerAnalyze('daily', { force })}
          onRetryFailed={(tasks) => triggerAnalyze('daily', { tasks, force: true })}
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
          tab={tab}
          analyzing={analyzing}
          analyzeError={analyzeError}
          onGenerate={(force) => triggerAnalyze(tab, { force })}
          onRetryFailed={(tasks) => triggerAnalyze(tab, { tasks, force: true })}
          showDetail={showDetail}
          setShowDetail={setShowDetail}
        />
      )}
    </div>
  )
}

function PeriodBrief({
  data,
  tab,
  analyzing,
  analyzeError,
  onGenerate,
  onRetryFailed,
  showDetail,
  setShowDetail,
}: {
  data: PeriodReport
  tab: 'weekly' | 'monthly'
  analyzing: boolean
  analyzeError: string | null
  onGenerate: (force: boolean) => void
  onRetryFailed: (tasks: string[]) => void
  showDetail: boolean
  setShowDetail: (v: boolean) => void
}) {
  const isMonthly = tab === 'monthly'
  const kind = isMonthly ? '月报' : '周报'
  const s = data.sections as {
    v1_stats?: V1StatsByScope
    v1_stats_prev?: V1StatsByScope
    historical_v1_stats?: Array<Record<string, unknown>>
    country_profiles?: Array<Record<string, unknown>>
    narrative_landscape?: {
      dominant_frames?: Array<{ frame: string; count: number }>
      emerging_frames?: Array<{ frame: string; this_month: number; last_month: number }>
      fading_frames?: Array<{ frame: string; this_month: number; last_month: number }>
      note?: string
    }
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
    quality?: { notes?: string[]; months_with_history?: number; missing_months?: string[] }
  }
  const nar = data.narratives || {}
  const kpis = s.summary?.kpis || {}
  const intel = data.intelligence
  const tasks = intel?.tasks || {}

  return (
    <article className="daily-brief">
      <header className="brief-hero">
        <p className="muted small">
          {kind} · {data.schema_version} · {data.period} · {data.generator || 'rule'}
        </p>
        <h1>
          {isMonthly ? '每月战略研判 · Monthly Strategic Review' : '每周变化分析 · Weekly Intelligence Report'}
        </h1>
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
        <h2>{isMonthly ? '1 · 月度战略总评（Monthly Executive Assessment）' : '1 · 周度综合研判（Weekly Executive Summary）'}</h2>
        <IntelligenceHeader
          intelligence={intel}
          analyzing={analyzing}
          analyzeError={analyzeError}
          onGenerate={onGenerate}
          onRetryFailed={onRetryFailed}
          title={isMonthly ? '月度战略总评与核心发现' : '周度核心变化与综合研判（本周 vs 上周）'}
        />
      </section>

      {isMonthly && (s.historical_v1_stats || []).length > 0 && (
        <section className="brief-section">
          <h2>2 · 全球关注格局与近 6 个月文章级重算序列</h2>
          <p className="muted small">
            所有月度统计均直接基于文章级 V1.0 口径重算（不合并周报）；缺失月份如实标 0，不伪装成趋势。
          </p>
          <div className="gni-table-wrap">
            <table className="gni-table">
              <thead>
                <tr>
                  <th>月份</th>
                  <th className="gni-num">唯一文章数</th>
                  <th className="gni-num">正面 %</th>
                  <th className="gni-num">中性 %</th>
                  <th className="gni-num">负面 %</th>
                  <th className="gni-num">立场覆盖率</th>
                </tr>
              </thead>
              <tbody>
                {(s.historical_v1_stats || []).map((row, idx) => (
                  <tr key={String(row.month || idx)}>
                    <td className="gni-mono">{String(row.month || '—')}</td>
                    <td className="gni-num">
                      <strong>{String(row.article_count ?? 0)}</strong>
                    </td>
                    <td className="gni-num">{row.positive_pct != null ? `${row.positive_pct}%` : '—'}</td>
                    <td className="gni-num">{row.neutral_pct != null ? `${row.neutral_pct}%` : '—'}</td>
                    <td className="gni-num">{row.negative_pct != null ? `${row.negative_pct}%` : '—'}</td>
                    <td className="gni-num">
                      {row.stance_coverage_pct != null ? `${row.stance_coverage_pct}%` : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section className="brief-section">
        <h2>{isMonthly ? '3 · 重大事件回顾（Major Event Retrospective）' : '2 · 本周重点事件与演化（Major Event Evolution）'}</h2>
        <EventInterpretationCards
          task={tasks.event_analysis}
          heading={isMonthly ? '月度重大事件阶段性回顾' : '本周事件演化分析（事件本体 vs 媒体关注 vs 跟进时间）'}
        />
        <ul className="event-list">
          {(s.major_events || []).slice(0, 10).map((ev) => (
            <li key={String(ev.event_id || ev.id)}>
              {ev.href ? (
                <Link to={String(ev.href)}>{String(ev.title)}</Link>
              ) : (
                String(ev.title)
              )}{' '}
              <span className="muted small">
                · 重要度 {String(ev.importance_score ?? '—')} · 关联 {String(ev.article_count ?? 0)} 篇
              </span>
            </li>
          ))}
          {(s.major_events || []).length === 0 && <li className="muted">窗口内无事件卡</li>}
        </ul>
      </section>

      <section className="brief-section">
        <h2>{isMonthly ? '4 · 长期议题结构与趋势（Topic Trends）' : '3 · 议题趋势变化解释（Topic Trend Interpretation）'}</h2>
        <TopicTrendAnalysisBlock
          task={tasks.topic_trend_analysis}
          title={isMonthly ? '长期议题结构变化与持续性分析' : '本周 vs 上周议题变化原因解释'}
          dataSlot={
            s.v1_stats && s.v1_stats_prev ? (
              <TrendDeltaTable
                current={s.v1_stats.topics || []}
                previous={s.v1_stats_prev.topics || []}
                dimensionLabel="15 议题（量变与态度变分离）"
                showBoard
              />
            ) : undefined
          }
        />
      </section>

      <section className="brief-section">
        <h2>
          {isMonthly
            ? '5 · 国别媒体画像与叙事格局（Country-Level & Narrative Landscape）'
            : '4 · 跨国叙事横向比较（Cross-country Narrative Comparison）'}
        </h2>
        <CrossCountryAnalysisBlock
          task={tasks.cross_country_analysis}
          title={isMonthly ? '国别监测媒体画像与主导/新兴叙事格局' : '同事件 / 同议题跨国叙事比较'}
          dataSlot={
            isMonthly && (s.country_profiles || []).length > 0 ? (
              <div className="gni-table-wrap">
                <table className="gni-table">
                  <thead>
                    <tr>
                      <th>国家</th>
                      <th className="gni-num">本月篇数</th>
                      <th className="gni-num">环比 Δ</th>
                      <th className="gni-num">负面率</th>
                      <th className="gni-num">覆盖率</th>
                      <th>样本状态</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(s.country_profiles || []).map((cp) => (
                      <tr key={String(cp.country_id)}>
                        <td>
                          <Link to={`/countries?c=${encodeURIComponent(String(cp.country_id))}`}>
                            <strong>{String(cp.country_id)}</strong>
                          </Link>
                        </td>
                        <td className="gni-num">{String(cp.article_count ?? 0)}</td>
                        <td className="gni-num">{String(cp.delta ?? 0)}</td>
                        <td className="gni-num">{fmtPct(cp.negative_rate as number | null)}</td>
                        <td className="gni-num">{fmtPct(cp.stance_coverage_rate as number | null)}</td>
                        <td className="small muted">{cp.sample_sufficient ? '可用' : '样本不足'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : undefined
          }
        />
      </section>

      <section className="brief-section">
        <h2>{isMonthly ? '6 · 长期对华立场趋势（Long-term Stance Trends）' : '5 · 情感与对华立场变化（Sentiment & Stance Changes）'}</h2>
        <StanceAnalysisBlock
          task={tasks.stance_analysis}
          title={isMonthly ? '长期对华立场演变与单事件冲击辨析' : '周度对华立场比例 vs 绝对数量变化解读'}
          dataSlot={s.v1_stats ? <V1StatsBlock v1={s.v1_stats} /> : undefined}
        />
        <p className="muted small">{s.sentiment_stance?.note}</p>
      </section>

      <section className="brief-section">
        <h2>{isMonthly ? '7 · 战略风险信号与条件性展望（Strategic Signals & Outlook）' : '6 · 新兴风险与下周监测重点（Emerging Signals & Next Week）'}</h2>
        <OutlookSignalsPanel
          task={tasks.emerging_signals}
          heading={isMonthly ? '战略风险信号与下月条件性展望' : '持续性异常、跨国扩散信号与下周监测清单'}
        />
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
        <h2>{isMonthly ? '8 · 数据覆盖与口径说明（Data Coverage & Methodology）' : '7 · 数据覆盖与原始明细'}</h2>
        {(s.quality?.notes || []).map((n, i) => (
          <p key={i} className="muted small">
            {n}
          </p>
        ))}
        <button type="button" onClick={() => setShowDetail(!showDetail)}>
          {showDetail ? '收起明细' : '展开原始统计明细 JSON'}
        </button>
        {showDetail && (
          <pre className="muted small" style={{ whiteSpace: 'pre-wrap' }}>
            {JSON.stringify(
              {
                source_buckets: s.summary?.source_buckets,
                event_evolution: s.event_evolution,
                cross_country_narrative: s.cross_country_narrative,
                narrative_landscape: s.narrative_landscape,
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
  analyzing,
  analyzeError,
  onGenerate,
  onRetryFailed,
  showToneDetail,
  setShowToneDetail,
  showCoverageDetail,
  setShowCoverageDetail,
}: {
  data: DailyReport
  analyzing: boolean
  analyzeError: string | null
  onGenerate: (force: boolean) => void
  onRetryFailed: (tasks: string[]) => void
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

  const stats = s.overview_stats
  const ingest = stats?.ingest || {}
  const risk = summary.risk_banner
  const tech = stats?.sentiment_tech
  const intel = data.intelligence
  const tasks = intel?.tasks || {}

  return (
    <div className="daily-brief daily-brief-v4">
      <header className="brief-header">
        <div className="brief-eyebrow">DAILY BRIEF · 预警优先</div>
        <h1>全球对华监测 · 日报</h1>
        <p className="muted small">
          当前接入 {connectedN} 国
          {data.connected?.active_sources != null ? ` · 活跃源 ${data.connected.active_sources}` : ''} ·{' '}
          {data.period} · {data.schema_version} · {data.generator || 'rule'}
        </p>
        <p className="callout">{data.disclaimer}</p>
      </header>

      <section className="brief-section">
        <h2>1 · 当日摘要与综合研判</h2>
        <div className={`risk-banner ${risk?.has_high_risk ? 'hot' : 'calm'}`}>
          {risk?.text || nar.risk || '—'}
        </div>
        <IntelligenceHeader
          intelligence={intel}
          analyzing={analyzing}
          analyzeError={analyzeError}
          onGenerate={onGenerate}
          onRetryFailed={onRetryFailed}
          title="当日综合研判与关键变化（Daily Executive Judgment）"
        />
        <p className="brief-lede">{summary.judgment_text || nar.executive || summary.overview_text}</p>
        {summary.confidence && (
          <p className="muted small">规则研判置信度：{summary.confidence}</p>
        )}
        <ol className="brief-changes">
          {(summary.top_changes || []).map((c) => (
            <li key={c.title}>
              {c.href ? <Link to={c.href}>{c.title}</Link> : <strong>{c.title}</strong>}
              <span className="muted"> — {c.summary}</span>
            </li>
          ))}
        </ol>
      </section>

      <section className="brief-section">
        <h2>2 · 数据统计（程序确定性计算）</h2>
        <div className="kpi-grid brief-kpis brief-kpis-hero">
          <Kpi label="今日要闻" value={stories} />
          <Kpi label="涉华有效" value={articles} hint={deltaHint(cmp?.vs_yesterday?.delta, '较昨日')} />
          <Kpi label="引用来源" value={sourcesCited} />
        </div>
        <div className="kpi-grid compact">
          <Kpi label="当日采集" value={Number(ingest.day_total ?? kpis.day_articles ?? 0)} />
          <Kpi label="排除/重复" value={Number((ingest.excluded_from_metrics ?? 0) + (ingest.duplicates ?? 0))} />
          <Kpi label="采集异常源" value={Number(stats?.crawl_summary?.failing ?? 0)} />
        </div>
        <MediaVolumeSpark
          today={kpis.china_articles}
          yesterday={cmp?.vs_yesterday?.china_articles}
          weekAvg={cmp?.vs_7d_avg?.china_articles}
        />
        {s.v1_stats && <V1StatsBlock v1={s.v1_stats} />}
        {tech && (
          <p className="muted small">
            情感分均值（技术）{tech.score_mean ?? '—'}
            {tech.vs_yesterday_delta != null ? ` · 较昨 Δ ${tech.vs_yesterday_delta}` : ''} · {tech.note}
          </p>
        )}
        <h3>各国情感简表</h3>
        <table className="tone-mini">
          <thead>
            <tr>
              <th>国家</th>
              <th>n</th>
              <th>正/中/负</th>
              <th>摘要</th>
            </tr>
          </thead>
          <tbody>
            {s.tone.by_country.map((row) => {
              const sc = row.sentiment_counts || {}
              const unavailable = row.status === 'unavailable' || row.status === 'no_sample'
              return (
                <tr key={row.country_id} className={unavailable ? 'tone-unavailable' : undefined}>
                  <td>
                    <Link to={row.href || `/countries?c=${row.country_id}`}>{row.country_id}</Link>
                  </td>
                  <td>{row.n}</td>
                  <td className="muted small">
                    {unavailable ? '样本不足' : `${sc.positive ?? 0}/${sc.neutral ?? 0}/${sc.negative ?? 0}`}
                  </td>
                  <td className="small">{row.summary_text}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
        {stats?.media_type_counts_zh && (
          <p className="muted small">
            媒体类型：
            {Object.entries(stats.media_type_counts_zh)
              .map(([k, v]) => `${k} ${v}`)
              .join(' · ') || '—'}
          </p>
        )}
        <button type="button" className="linkish" onClick={() => setShowToneDetail(!showToneDetail)}>
          {showToneDetail ? '收起立场计数' : '展开立场计数 / 官方vs媒体主题'}
        </button>
        {showToneDetail && (
          <pre className="muted small" style={{ whiteSpace: 'pre-wrap' }}>
            {JSON.stringify(
              {
                stance: s.tone.overall_stance_counts,
                by_media_type: stats?.sentiment_by_media_type,
                narrative_split: stats?.narrative_split,
              },
              null,
              2,
            )}
          </pre>
        )}
      </section>

      <section className="brief-section">
        <div className="brief-section-head">
          <h2>3 · 当日重点事件（深度解读 + 风险表）</h2>
          <p className="muted small">主国｜媒体类型｜标题与叙事｜覆盖｜情感｜风险；异动行左侧红条提示</p>
        </div>
        <EventInterpretationCards
          task={tasks.event_analysis}
          heading="当日重点事件分析卡（发生了什么 / 背景 / 为何关注 / 各国差异 / 后续观察）"
        />
        <EventRiskTable events={s.major_events || []} />
        {(s.secondary_events || []).length > 0 && (
          <details className="secondary-events">
            <summary className="muted small">次要 / 弱对华相关事件（{s.secondary_events!.length}）</summary>
            <ul className="event-list">
              {s.secondary_events!.map((ev) => (
                <li key={ev.event_id}>
                  <Link to={ev.href || `/events/${ev.event_id}`}>{ev.title}</Link>
                  <span className="muted small">
                    {' '}
                    · 信号 {ev.china_signal_score ?? '—'} · {ev.risk_level || 'unmapped'}
                  </span>
                </li>
              ))}
            </ul>
          </details>
        )}
        {(s.orphan_headlines || []).length > 0 && (
          <div className="orphan-headlines">
            <h3>指纹外敏感标题</h3>
            <ul className="event-list">
              {s.orphan_headlines!.map((oh) => (
                <li key={String(oh.article_id)}>
                  <strong>{oh.title}</strong>
                  <span className="muted small">
                    {' '}
                    · {oh.country_id || '—'} · {oh.risk_level}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
        <TopicBars topics={s.coverage.topics_top || []} />
        {s.coverage.taxonomy_confidence === 'low' && (
          <p className="callout">议题 taxonomy 低置信（当日主题过度集中）。</p>
        )}
        <button type="button" className="linkish" onClick={() => setShowCoverageDetail(!showCoverageDetail)}>
          {showCoverageDetail ? '收起事件证据明细' : '展开事件证据 / 覆盖明细'}
        </button>
        {showCoverageDetail &&
          (s.major_events || []).slice(0, 5).map((ev) => (
            <article key={`d-${ev.event_id}`} className="event-card">
              <h3>
                <Link to={ev.href || `/events/${ev.event_id}`}>{ev.title}</Link>
              </h3>
              <p className="muted small">{ev.overview_text}</p>
              <ul className="event-list">
                {(ev.evidence || []).slice(0, 4).map((evi) => (
                  <li key={evi.article_id} className="muted small">
                    [{evi.country_id}] {evi.title} · {evi.sentiment}/{evi.stance}
                  </li>
                ))}
              </ul>
            </article>
          ))}
      </section>

      <section className="brief-section">
        <h2>4 · 舆情异动解释与明日监测重点</h2>
        <OutlookSignalsPanel
          task={tasks.emerging_signals}
          heading="异动解释与明日监测优先级（Anomaly Explanation & Tomorrow's Priorities）"
        />
        <ul className="event-list">
          {(s.anomalies || []).map((a, idx) => (
            <li key={String(a.id || a.event_id || a.title || idx)} className={a.kind === 'event_anomaly' ? 'row-anomaly-item' : undefined}>
              <span className={`sev sev-${a.severity === 'high' || a.risk_level === 'high' ? 'high' : 'medium'}`}>
                {String(a.kind || 'signal')}
              </span>{' '}
              {a.href ? <Link to={String(a.href)}>{String(a.title)}</Link> : <strong>{String(a.title)}</strong>}
              <div className="muted small">
                {String(a.summary || (Array.isArray(a.reasons) ? a.reasons.join('；') : '') || '')}
              </div>
            </li>
          ))}
          {(s.anomalies || []).length === 0 && <li className="muted">当日无显著异动</li>}
        </ul>
      </section>

      <section className="brief-section">
        <h2>5 · 次日跟踪 + 采集状态</h2>
        <p className="muted small">{s.ops?.note}</p>
        <h3>规则跟踪建议</h3>
        <ul className="event-list">
          {(s.ops?.follow_ups || []).map((f) => (
            <li key={String(f.event_id || f.title)}>
              {f.href ? <Link to={f.href}>{f.title}</Link> : f.title}
              <div className="muted small">{f.action}</div>
            </li>
          ))}
          {(s.ops?.follow_ups || []).length === 0 && <li className="muted">无专项跟踪项</li>}
        </ul>
        <h3>采集状态</h3>
        <SourceOpsTable rows={s.ops?.crawl_status || []} defaultOnlyFailed />
        <p className="muted small">
          局限：分析积压 {s.quality.missing_analysis}；无样本国{' '}
          {(s.quality.countries_without_sample || []).join(', ') || '—'}。
          {(s.quality.notes || []).slice(0, 2).join(' ')}
        </p>
      </section>
    </div>
  )
}

function fmtPct(v: number | null | undefined) {
  return typeof v === 'number' ? `${(v * 100).toFixed(1)}%` : '—'
}

function V1StatsBlock({ v1 }: { v1: V1StatsByScope }) {
  const [dim, setDim] = useState<'board' | 'country' | 'topic'>('board')
  const g = v1.global
  if (!g) return null
  const boards = (v1.boards || []).filter((b) => b.article_count > 0)
  const countries = v1.countries || []
  const topics = (v1.topics || []).filter((t) => t.article_count > 0)

  const activeRows = dim === 'board' ? boards : dim === 'country' ? countries : topics
  const activeLabel =
    dim === 'board'
      ? '四大板块（板块间允许重叠）'
      : dim === 'country'
        ? '信源所属国家 (source_country)'
        : '15 个议题（允许跨议题重叠）'

  return (
    <div className="v1-stats-block" style={{ marginTop: 12, marginBottom: 16 }}>
      <div className="gni-table-head">
        <h3>V1.0 对华立场与议题统计（Article Count · published_at）</h3>
        <div className="gni-seg-group" role="group" aria-label="切换统计维度">
          <button
            type="button"
            className="gni-seg-btn"
            aria-pressed={dim === 'board'}
            onClick={() => setDim('board')}
          >
            四大板块
          </button>
          <button
            type="button"
            className="gni-seg-btn"
            aria-pressed={dim === 'country'}
            onClick={() => setDim('country')}
          >
            信源国家
          </button>
          <button
            type="button"
            className="gni-seg-btn"
            aria-pressed={dim === 'topic'}
            onClick={() => setDim('topic')}
          >
            15 议题
          </button>
        </div>
      </div>
      <p className="small">
        全球唯一涉华文章 <strong>{g.article_count}</strong> 篇 · 正面{' '}
        <strong>{fmtPct(g.positive_rate)}</strong> ({g.positive_count}) / 中性{' '}
        <strong>{fmtPct(g.neutral_rate)}</strong> ({g.neutral_count}) / 负面{' '}
        <strong>{fmtPct(g.negative_rate)}</strong> ({g.negative_count}) · Unclassified{' '}
        {g.unclassified_count} · 立场判定覆盖率 <strong>{fmtPct(g.stance_coverage_rate)}</strong>
      </p>
      <StanceMatrixTable rows={activeRows} dimensionLabel={activeLabel} />
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
