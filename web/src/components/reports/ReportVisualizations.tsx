import type {
  ReportQualityGate,
  ReportVisualizations,
  ReportWindowSpec,
} from '../../api'

export function QualityGateBanner({ gate }: { gate?: ReportQualityGate }) {
  if (!gate) return null
  if (gate.status === 'passed') {
    return (
      <div className="mb-3 flex flex-wrap items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50/70 px-3 py-2 text-xs text-emerald-800">
        <span className="font-semibold">质量门禁通过</span>
        <span className="text-emerald-700/90">
          去重文章数 {gate.metrics?.article_count ?? 0}
          {gate.metrics?.stance_coverage_rate != null
            ? ` · 立场覆盖率 ${(gate.metrics.stance_coverage_rate * 100).toFixed(1)}%`
            : ''}
        </span>
      </div>
    )
  }
  const isBlocked = gate.status === 'blocked'
  const issues = isBlocked ? gate.blocking_issues : gate.warnings
  return (
    <div
      role="status"
      className={`mb-3 rounded-lg border px-3.5 py-2.5 text-xs ${
        isBlocked
          ? 'border-rose-300 bg-rose-50 text-rose-900'
          : 'border-amber-300 bg-amber-50/80 text-amber-900'
      }`}
    >
      <div className="font-semibold">
        {isBlocked ? '质量门禁阻断（需核查统计口径）' : '质量门禁提示（允许阅读，请关注数据限制）'}
      </div>
      {issues.length > 0 && (
        <ul className="mt-1 list-disc space-y-0.5 pl-4">
          {issues.map((item, idx) => (
            <li key={`${item.code}-${idx}`}>{item.message}</li>
          ))}
        </ul>
      )}
    </div>
  )
}

export function WindowSpecBadge({ spec }: { spec?: ReportWindowSpec }) {
  if (!spec) return null
  const modeLabel: Record<string, string> = {
    calendar_day: '自然日窗口',
    rolling_7d: '滚动 7 天',
    calendar_month: '自然月窗口',
    rolling_30d: '滚动 30 天',
  }
  return (
    <div className="mb-3 flex flex-wrap items-center gap-2 text-xs text-slate-600">
      <span className="rounded bg-slate-100 px-2 py-0.5 font-medium text-slate-700">
        {modeLabel[spec.window_mode] ?? spec.window_mode}
      </span>
      <span>时区：{spec.timezone}</span>
      {spec.is_partial_period && (
        <span className="rounded bg-amber-100 px-2 py-0.5 font-medium text-amber-800">
          未完整周期（已运行 {spec.elapsed_days}/{spec.total_days} 天 · MTD 公平环比）
        </span>
      )}
    </div>
  )
}

function TrendLineChart({
  data,
}: {
  data?: ReportVisualizations['trend_line']
}) {
  const series = data?.series ?? []
  if (!series.length) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <div className="text-sm font-semibold text-slate-800">{data?.title ?? '涉华报道量趋势'}</div>
        <div className="mt-3 text-xs text-slate-500">当前周期暂无趋势序列数据。</div>
      </div>
    )
  }
  const width = 460
  const height = 140
  const padX = 28
  const padY = 18
  const maxVal = Math.max(1, ...series.map((s) => s.article_count))
  const stepX = series.length > 1 ? (width - padX * 2) / (series.length - 1) : 0
  const pts = series.map((s, i) => {
    const x = padX + i * stepX
    const y = height - padY - (s.article_count / maxVal) * (height - padY * 2)
    return { x, y, ...s }
  })
  const pathD = pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ')
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="flex items-baseline justify-between gap-2">
        <h4 className="text-sm font-semibold text-slate-800">{data?.title ?? '涉华报道量趋势'}</h4>
        <span className="text-[11px] text-slate-500">峰值 {maxVal} 篇</span>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} className="mt-2 h-36 w-full overflow-visible" aria-label={data?.title}>
        <line x1={padX} y1={height - padY} x2={width - padX} y2={height - padY} stroke="#e2e8f0" strokeWidth="1" />
        <path d={pathD} fill="none" stroke="#2563eb" strokeWidth="2.2" strokeLinejoin="round" />
        {pts.map((p, i) => (
          <g key={`${p.label}-${i}`}>
            <circle cx={p.x} cy={p.y} r="3.2" fill={p.is_partial ? '#f59e0b' : '#2563eb'}>
              <title>{`${p.label}: ${p.article_count} 篇${p.is_partial ? '（未完整周期）' : ''}`}</title>
            </circle>
            {(i === 0 || i === pts.length - 1 || pts.length <= 7) && (
              <text x={p.x} y={height - 3} textAnchor="middle" fontSize="9" fill="#64748b">
                {p.label.slice(-5)}
              </text>
            )}
          </g>
        ))}
      </svg>
      {data?.caption && <p className="mt-1 text-[11px] text-slate-500">{data.caption}</p>}
    </div>
  )
}

function CountryBarChart({
  data,
}: {
  data?: ReportVisualizations['country_bar']
}) {
  const items = (data?.items ?? []).slice(0, 8)
  const maxVal = Math.max(1, ...items.map((i) => i.article_count))
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="flex items-baseline justify-between">
        <h4 className="text-sm font-semibold text-slate-800">{data?.title ?? '国家分布（按信源国家）'}</h4>
        <span className="text-[11px] text-slate-500">Top {items.length}</span>
      </div>
      {items.length === 0 ? (
        <div className="mt-3 text-xs text-slate-500">暂无国家分布数据。</div>
      ) : (
        <div className="mt-2.5 space-y-2">
          {items.map((item) => {
            const pct = Math.max(4, (item.article_count / maxVal) * 100)
            const lowSample = item.article_count < 3
            const cov =
              item.stance_coverage_rate != null ? `${(item.stance_coverage_rate * 100).toFixed(0)}%` : '—'
            return (
              <div key={item.country_code} className="space-y-0.5">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-medium text-slate-700">
                    {item.country_name || item.country_code}
                  </span>
                  <span className="text-[11px] text-slate-500">
                    {item.article_count} 篇 ·{' '}
                    {lowSample ? (
                      <span className="rounded bg-amber-100 px-1 py-0.5 text-[10px] font-medium text-amber-800">
                        样本不足（n&lt;3，不计覆盖率百分比）
                      </span>
                    ) : (
                      `覆盖率 ${cov}`
                    )}
                  </span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
                  <div className="h-full rounded-full bg-sky-600" style={{ width: `${pct}%` }} />
                </div>
              </div>
            )
          })}
        </div>
      )}
      {data?.caption && <p className="mt-2 text-[11px] text-slate-500">{data.caption}</p>}
    </div>
  )
}

function StanceStackedBar({
  data,
}: {
  data?: ReportVisualizations['stance_stacked']
}) {
  const d = data?.data
  if (!d || d.article_count === 0) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <h4 className="text-sm font-semibold text-slate-800">{data?.title ?? '涉华立场分布'}</h4>
        <div className="mt-3 text-xs text-slate-500">当前窗口暂无文章立场数据。</div>
      </div>
    )
  }
  const posPct = ((d.positive_rate ?? 0) * 100).toFixed(1)
  const neuPct = ((d.neutral_rate ?? 0) * 100).toFixed(1)
  const negPct = ((d.negative_rate ?? 0) * 100).toFixed(1)
  const covPct = d.stance_coverage_rate != null ? `${(d.stance_coverage_rate * 100).toFixed(1)}%` : '—'
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="flex items-baseline justify-between gap-2">
        <h4 className="text-sm font-semibold text-slate-800">{data?.title ?? '涉华立场分布'}</h4>
        <span className="text-[11px] text-slate-500">覆盖率 {covPct}</span>
      </div>
      <div className="mt-3 flex h-4 w-full overflow-hidden rounded-full bg-slate-100">
        <div className="bg-emerald-500" style={{ width: `${posPct}%` }} title={`正面 ${posPct}% (${d.positive_count} 篇)`} />
        <div className="bg-slate-400" style={{ width: `${neuPct}%` }} title={`中性 ${neuPct}% (${d.neutral_count} 篇)`} />
        <div className="bg-rose-500" style={{ width: `${negPct}%` }} title={`负面 ${negPct}% (${d.negative_count} 篇)`} />
      </div>
      <div className="mt-2.5 flex flex-wrap items-center gap-3 text-xs text-slate-700">
        <span>正面 {posPct}% ({d.positive_count})</span>
        <span>中性 {neuPct}% ({d.neutral_count})</span>
        <span>负面 {negPct}% ({d.negative_count})</span>
        <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[11px] text-slate-600">
          Unclassified: {d.unclassified_count}（不计入比例分母）
        </span>
      </div>
      {data?.caption && <p className="mt-2 text-[11px] text-slate-500">{data.caption}</p>}
    </div>
  )
}

function TopicDeltaChart({
  data,
}: {
  data?: ReportVisualizations['topic_delta']
}) {
  const items = (data?.items ?? []).slice(0, 8)
  const maxVal = Math.max(1, ...items.map((i) => i.article_count))
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <h4 className="text-sm font-semibold text-slate-800">{data?.title ?? '议题分布与环比变化'}</h4>
      {items.length === 0 ? (
        <div className="mt-3 text-xs text-slate-500">暂无议题分布数据。</div>
      ) : (
        <div className="mt-2.5 space-y-2">
          {items.map((item) => {
            const pct = Math.max(4, (item.article_count / maxVal) * 100)
            const deltaStr = item.delta > 0 ? `+${item.delta}` : `${item.delta}`
            const deltaColor = item.delta > 0 ? 'text-rose-600' : item.delta < 0 ? 'text-emerald-600' : 'text-slate-400'
            return (
              <div key={item.topic} className="space-y-0.5">
                <div className="flex items-center justify-between text-xs">
                  <span className="truncate font-medium text-slate-700">{item.topic}</span>
                  <span className="shrink-0 text-[11px] text-slate-600">
                    {item.article_count} 篇 <span className={`ml-1 font-medium ${deltaColor}`}>({deltaStr})</span>
                  </span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
                  <div className="h-full rounded-full bg-indigo-500" style={{ width: `${pct}%` }} />
                </div>
              </div>
            )
          })}
        </div>
      )}
      {data?.caption && <p className="mt-2 text-[11px] text-slate-500">{data.caption}</p>}
    </div>
  )
}

function EventTimelineList({
  data,
}: {
  data?: ReportVisualizations['event_timeline']
}) {
  const items = (data?.items ?? []).slice(0, 6)
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <h4 className="text-sm font-semibold text-slate-800">{data?.title ?? '重点事件时间线'}</h4>
      {items.length === 0 ? (
        <div className="mt-3 text-xs text-slate-500">当前周期暂无聚合事件。</div>
      ) : (
        <ol className="mt-2.5 space-y-2 border-l border-slate-200 pl-3">
          {items.map((ev) => (
            <li key={ev.event_id || ev.title} className="text-xs">
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium text-slate-800">{ev.title}</span>
                <span className="shrink-0 text-[11px] text-slate-500">{ev.article_count} 篇</span>
              </div>
              <div className="mt-0.5 text-[11px] text-slate-500">
                {ev.event_time
                  ? `${ev.event_time_basis === 'proxy_published_at' ? '事件时间（代理：最早发布时间）' : '事件时间'}：${ev.event_time.slice(0, 16).replace('T', ' ')}`
                  : '事件时间：时间未知'}
                {ev.countries && ev.countries.length > 0 ? ` · 国家：${ev.countries.join(', ')}` : ''}
              </div>
            </li>
          ))}
        </ol>
      )}
      {data?.caption && <p className="mt-2 text-[11px] text-slate-500">{data.caption}</p>}
    </div>
  )
}

export function ReportVisualDashboard({
  visualizations,
  cadence,
}: {
  visualizations?: ReportVisualizations
  cadence: 'daily' | 'weekly' | 'monthly'
}) {
  if (!visualizations) return null
  return (
    <section className="mb-6 space-y-3" aria-label="确定性数据可视化">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold tracking-wide text-slate-700">
          {cadence === 'daily'
            ? '关键统计图景（日报监测）'
            : cadence === 'weekly'
              ? '周度变化可视化（趋势 · 国别 · 议题 · 立场）'
              : '月度格局可视化（长周期趋势 · 国别 · 议题 · 立场）'}
        </h3>
        <span className="text-[11px] text-slate-500">数据驱动 · 严格遵循 V1.0 统计口径</span>
      </div>
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        <TrendLineChart data={visualizations.trend_line} />
        <StanceStackedBar data={visualizations.stance_stacked} />
        <CountryBarChart data={visualizations.country_bar} />
        <TopicDeltaChart data={visualizations.topic_delta} />
      </div>
      {cadence !== 'daily' && <EventTimelineList data={visualizations.event_timeline} />}
    </section>
  )
}
