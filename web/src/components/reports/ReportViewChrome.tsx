import type { DailyReport, PeriodReport } from '../../api'
import {
  QualityGateBanner,
  ReportVisualDashboard,
  WindowSpecBadge,
} from './ReportVisualizations'

type CuratedRef = {
  article_id?: string
  title?: string
  source_name?: string
  country_code?: string
  china_stance?: string
  url?: string
  published_at?: string
}

export function ReportExportBar({
  cadence,
  period,
  selectedDate,
}: {
  cadence: 'daily' | 'weekly' | 'monthly'
  period?: string
  selectedDate?: string
}) {
  const mdHref =
    cadence === 'daily'
      ? `/api/reports/daily/package?format=markdown${selectedDate ? `&date=${encodeURIComponent(selectedDate)}` : ''}`
      : cadence === 'weekly'
        ? `/api/reports/weekly/package?format=markdown${selectedDate ? `&end=${encodeURIComponent(selectedDate)}` : ''}`
        : `/api/reports/monthly/package?format=markdown${selectedDate ? `&end=${encodeURIComponent(selectedDate)}` : ''}`

  return (
    <div className="mb-3 flex flex-wrap items-center justify-between gap-2 text-xs">
      <span className="text-slate-500">
        {cadence === 'daily'
          ? '日报模式 · 3–5 分钟快速监测'
          : cadence === 'weekly'
            ? '周报模式 · 变化归因与国别对比'
            : '月报模式 · 长期格局与结构性趋势'}
        {period ? ` · 周期 ${period}` : ''}
      </span>
      <a
        href={mdHref}
        target="_blank"
        rel="noreferrer"
        className="rounded-md border border-slate-300 bg-white px-2.5 py-1 font-medium text-slate-700 hover:bg-slate-50"
      >
        导出 Markdown 简报
      </a>
    </div>
  )
}

export function CuratedEvidencePanel({
  refs,
}: {
  refs?: CuratedRef[]
}) {
  const list = (refs ?? []).filter((r) => r && r.title).slice(0, 6)
  if (list.length === 0) return null
  return (
    <details className="mb-4 rounded-xl border border-slate-200 bg-slate-50/70 p-3.5 text-xs">
      <summary className="cursor-pointer font-semibold text-slate-700">
        精选代表证据（{list.length} 篇 · 多国/多源去重抽样）
      </summary>
      <ul className="mt-2.5 space-y-2">
        {list.map((r, idx) => (
          <li key={`${r.article_id ?? idx}`} className="rounded-lg border border-slate-200 bg-white p-2.5">
            <div className="flex flex-wrap items-center justify-between gap-1.5">
              <span className="font-medium text-slate-800">
                {r.url ? (
                  <a href={r.url} target="_blank" rel="noreferrer" className="hover:underline">
                    {r.title}
                  </a>
                ) : (
                  r.title
                )}
              </span>
              <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[11px] text-slate-600">
                {r.source_name || 'Unknown'}
                {r.country_code ? ` · ${r.country_code}` : ''}
                {r.china_stance ? ` · ${r.china_stance}` : ''}
              </span>
            </div>
          </li>
        ))}
      </ul>
    </details>
  )
}

export function DailyReportViewChrome({
  data,
  selectedDate,
}: {
  data: DailyReport
  selectedDate: string
}) {
  return (
    <div className="mb-4">
      <ReportExportBar cadence="daily" period={data.period} selectedDate={selectedDate} />
      <WindowSpecBadge spec={data.window_spec} />
      <QualityGateBanner gate={data.quality_gate} />
      <ReportVisualDashboard visualizations={data.visualizations} cadence="daily" />
    </div>
  )
}

export function WeeklyReportViewChrome({
  data,
  selectedDate,
}: {
  data: PeriodReport
  selectedDate: string
}) {
  const pkgRefs = (data.report_package as { evidence_refs?: CuratedRef[] } | undefined)?.evidence_refs
  return (
    <div className="mb-4">
      <ReportExportBar cadence="weekly" period={data.period} selectedDate={selectedDate} />
      <WindowSpecBadge spec={data.window_spec} />
      <QualityGateBanner gate={data.quality_gate} />
      <ReportVisualDashboard visualizations={data.visualizations} cadence="weekly" />
      <CuratedEvidencePanel refs={pkgRefs} />
    </div>
  )
}

export function MonthlyReportViewChrome({
  data,
  selectedDate,
}: {
  data: PeriodReport
  selectedDate: string
}) {
  const pkgRefs = (data.report_package as { evidence_refs?: CuratedRef[] } | undefined)?.evidence_refs
  return (
    <div className="mb-4">
      <ReportExportBar cadence="monthly" period={data.period} selectedDate={selectedDate} />
      <WindowSpecBadge spec={data.window_spec} />
      <QualityGateBanner gate={data.quality_gate} />
      <ReportVisualDashboard visualizations={data.visualizations} cadence="monthly" />
      <CuratedEvidencePanel refs={pkgRefs} />
    </div>
  )
}
