import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchReportCalendar, type ReportCalendarDay } from '../api'
import { fetchDashboard, type DashboardPayload } from '../apiV2'
import { DEFAULT_REPORT_DATE, ReportCalendarPopover } from './Reports'
import {
  EmptyState,
  ErrorState,
  fmtDateTime,
  fmtPct,
  LoadingState,
  PartialDataBanner,
  SectionCard,
  StanceBar,
} from '../components/StateBlocks'
import '../components/intel.css'

export function OverviewPage() {
  const [selectedDate, setSelectedDate] = useState<string>(DEFAULT_REPORT_DATE)
  const [trendDays, setTrendDays] = useState<number>(14)
  const [calendarOpen, setCalendarOpen] = useState(false)
  const [calendarMonth, setCalendarMonth] = useState<string>(DEFAULT_REPORT_DATE.slice(0, 7))
  const [calendarView, setCalendarView] = useState<'day' | 'month'>('day')
  const [calendarDays, setCalendarDays] = useState<ReportCalendarDay[]>([])
  const calendarAnchorRef = useRef<HTMLDivElement | null>(null)

  const [data, setData] = useState<DashboardPayload | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    fetchReportCalendar(calendarMonth)
      .then((res) => {
        if (!cancelled) setCalendarDays(res.days || [])
      })
      .catch(() => {
        if (!cancelled) setCalendarDays([])
      })
    return () => {
      cancelled = true
    }
  }, [calendarMonth])

  useEffect(() => {
    if (!calendarOpen) return
    function onDocClick(e: MouseEvent) {
      if (calendarAnchorRef.current && !calendarAnchorRef.current.contains(e.target as Node)) {
        setCalendarOpen(false)
      }
    }
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') setCalendarOpen(false)
    }
    document.addEventListener('mousedown', onDocClick)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('mousedown', onDocClick)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [calendarOpen])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchDashboard(selectedDate, trendDays)
      .then((res) => {
        if (!cancelled) setData(res)
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [selectedDate, trendDays])

  if (loading) return <LoadingState label="加载 Global Intelligence Dashboard…" />
  if (error) {
    return (
      <ErrorState
        error={error}
        hint="请确认后端 API 正在运行：gni api serve（默认 127.0.0.1:8000）。"
      />
    )
  }
  if (!data) return <EmptyState title="暂无仪表盘数据" />

  const ov = data.executive_overview
  const st = ov.stance_distribution
  const att = data.global_attention
  const maxTrend = Math.max(1, ...att.volume_trend.map((d) => d.china_articles))

  return (
    <div className="intel-page">
      <div
        className="intel-header-row"
        style={{ flexWrap: 'nowrap', alignItems: 'center', justifyContent: 'space-between', gap: '1rem' }}
      >
        <h1 style={{ margin: 0 }}>Global Intelligence Dashboard</h1>
        <div
          className="intel-filter-bar"
          style={{ marginLeft: 'auto', flexShrink: 0, alignItems: 'center', gap: '0.6rem', flexWrap: 'nowrap' }}
        >
          <label className="small muted" style={{ whiteSpace: 'nowrap' }}>
            统计窗口{' '}
            <select value={trendDays} onChange={(e) => setTrendDays(Number(e.target.value))}>
              <option value={7}>近 7 天</option>
              <option value={14}>近 14 天</option>
              <option value={30}>近 30 天</option>
              <option value={90}>近 90 天</option>
            </select>
          </label>
          <div className="report-date-anchor" ref={calendarAnchorRef}>
            <button
              type="button"
              className="report-date-trigger"
              aria-expanded={calendarOpen}
              aria-haspopup="dialog"
              onClick={() => {
                setCalendarOpen((v) => {
                  const next = !v
                  if (next) setCalendarView('day')
                  return next
                })
              }}
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <rect x="3" y="4" width="18" height="18" rx="2" />
                <line x1="16" y1="2" x2="16" y2="6" />
                <line x1="8" y1="2" x2="8" y2="6" />
                <line x1="3" y1="10" x2="21" y2="10" />
              </svg>
              <span>{selectedDate}</span>
              <span aria-hidden="true">{calendarOpen ? '▴' : '▾'}</span>
            </button>
            {calendarOpen && (
              <ReportCalendarPopover
                month={calendarMonth}
                days={calendarDays}
                selectedDate={selectedDate}
                view={calendarView}
                onChangeView={setCalendarView}
                onChangeMonth={setCalendarMonth}
                onSelectDate={(d) => {
                  setSelectedDate(d)
                  const ym = d.slice(0, 7)
                  if (ym !== calendarMonth) setCalendarMonth(ym)
                  setCalendarOpen(false)
                }}
              />
            )}
          </div>
        </div>
      </div>

      <div className="intel-header-row" style={{ marginTop: '-0.35rem', alignItems: 'center' }}>
        <p className="muted small" style={{ margin: 0 }}>
          周期 {data.meta.period} · 窗口 {fmtDateTime(data.meta.period_start)} →{' '}
          {fmtDateTime(data.meta.period_end)} UTC · 方法论 {data.meta.methodology_version} · 核心指标：
          {data.meta.core_kpi}
        </p>
        <div className="intel-chip-row" style={{ marginLeft: 'auto', flexShrink: 0 }}>
          <Link to={data.daily_report_entry.href} className="intel-btn primary">
            阅读完整情报分析 ({data.daily_report_entry.chapter_count} 章) →
          </Link>
          <Link to="/explorer" className="intel-btn">
            证据与文章浏览
          </Link>
        </div>
      </div>

      {ov.stance_coverage_rate != null && ov.stance_coverage_rate < 0.8 && (
        <PartialDataBanner
          message={`当前窗口立场覆盖率 ${fmtPct(ov.stance_coverage_rate)}（${st.classified_count}/${ov.article_count} 篇已完成 V1.0 对华立场标注，其余 ${st.unclassified_count} 篇为 Unclassified）。正中负比例分母不含 Unclassified。`}
        />
      )}

      {/* Minimal Monitoring Overview: KPI + Stance Bar */}
      <SectionCard
        title="核心监测速览（Monitoring Snapshot）"
        subtitle="完整 A–E 态势研判、国别/议题分布与重点事件已移至「情报分析 → 每日简报」"
      >
        <div className="intel-kpi-row">
          <div className="intel-kpi-card primary">
            <div className="intel-kpi-label">今日涉华唯一文章总量 (Article Count)</div>
            <div className="intel-kpi-value">{ov.article_count}</div>
            <div className="intel-kpi-sub">
              较昨日 {ov.vs_yesterday ? `${ov.vs_yesterday.delta >= 0 ? '+' : ''}${ov.vs_yesterday.delta}` : '—'} ·
              较7日均 {ov.vs_7d_avg ? `${ov.vs_7d_avg.delta >= 0 ? '+' : ''}${ov.vs_7d_avg.delta}` : '—'}
            </div>
          </div>
          <div className="intel-kpi-card">
            <div className="intel-kpi-label">高重要事件数</div>
            <div className="intel-kpi-value">{ov.major_events ?? 0}</div>
            <div className="intel-kpi-sub">重要度 ≥ 0.7 · 新发现 {ov.new_events ?? 0} 个</div>
          </div>
          <div className="intel-kpi-card">
            <div className="intel-kpi-label">报道媒体 / 活跃信源</div>
            <div className="intel-kpi-value">
              {ov.reporting_sources}
              <span className="muted small"> / {ov.active_sources ?? '—'}</span>
            </div>
            <div className="intel-kpi-sub">当期涉华发稿信源</div>
          </div>
          <div className="intel-kpi-card">
            <div className="intel-kpi-label">Stance Coverage Rate</div>
            <div className="intel-kpi-value">{fmtPct(ov.stance_coverage_rate)}</div>
            <div className="intel-kpi-sub">
              已分类 {st.classified_count} · Unclassified {st.unclassified_count}
            </div>
          </div>
        </div>

        <div style={{ marginTop: '0.9rem' }}>
          <div className="intel-header-row" style={{ marginBottom: '0.35rem' }}>
            <strong style={{ fontSize: '0.88rem' }}>
              整体对华立场分布（target: {st.target}）
            </strong>
            <Link to="/stance" className="muted small">
              进入情感与立场分析 →
            </Link>
          </div>
          <StanceBar
            positiveRate={st.positive_rate}
            neutralRate={st.neutral_rate}
            negativeRate={st.negative_rate}
          />
          {st.denominator_note && <p className="muted small">{st.denominator_note}</p>}
        </div>
      </SectionCard>

      {/* Near-N-day Volume Trend */}
      <SectionCard
        title={`近 ${trendDays} 日全球涉华报道量趋势`}
        subtitle="按发布时间 published_at 统计的每日涉华去重文章量"
        right={
          <Link to="/trends" className="muted small">
            查看历史趋势 →
          </Link>
        }
      >
        {att.volume_trend.length === 0 ? (
          <p className="muted small">暂无历史趋势样本</p>
        ) : (
          <div className="bars">
            {att.volume_trend.map((d) => (
              <div className="bar-row" key={d.date}>
                <span className="bar-label">{d.date.slice(5)}</span>
                <div className="bar-track">
                  <div
                    className="bar-fill"
                    style={{ width: `${Math.round((d.china_articles / maxTrend) * 100)}%` }}
                  />
                </div>
                <span className="bar-n">{d.china_articles}</span>
              </div>
            ))}
          </div>
        )}
      </SectionCard>

      {/* Quick Entry Footer */}
      <div className="intel-banner intel-header-row">
        <div>
          <strong>情报分析 · 每日简报（含 A–E 完整态势与 1–4 深度研判）</strong>
          <div className="muted small">
            报告 ID：{data.daily_report_entry.report_id || data.meta.period} · 生成状态：
            {data.daily_report_entry.generation_status || '—'} · 校验状态：
            {data.daily_report_entry.validation_status || '—'}
          </div>
        </div>
        <Link to="/reports" className="intel-btn primary">
          进入每日简报 →
        </Link>
      </div>
    </div>
  )
}
