import type { ReactNode } from 'react'
import './intel.css'

export function LoadingState({ label = '加载中…' }: { label?: string }) {
  return <div className="panel muted">{label}</div>
}

export function ErrorState({ error, hint }: { error: string; hint?: string }) {
  return (
    <div className="panel">
      <p className="error">加载失败：{error}</p>
      {hint && <p className="muted small">{hint}</p>}
    </div>
  )
}

export function EmptyState({ title, detail }: { title: string; detail?: string }) {
  return (
    <div className="panel">
      <p>
        <strong>{title}</strong>
      </p>
      {detail && <p className="muted small">{detail}</p>}
    </div>
  )
}

export function PartialDataBanner({ message }: { message: string }) {
  return <div className="intel-banner intel-banner-warn">{message}</div>
}

export function SampleSizeBadge({ count, threshold = 10 }: { count: number; threshold?: number }) {
  if (count >= threshold) {
    return <span className="intel-badge">样本 n={count}</span>
  }
  return (
    <span className="intel-badge intel-badge-warn" title="样本量较小，比例分布仅供参考">
      小样本 n={count}
    </span>
  )
}

export function ClassificationBadge({ kind }: { kind?: string | null }) {
  const k = (kind || 'Inference').trim()
  const lower = k.toLowerCase()
  const cls =
    lower === 'fact'
      ? 'intel-badge-fact'
      : lower === 'hypothesis'
        ? 'intel-badge-hypothesis'
        : lower === 'outlook'
          ? 'intel-badge-outlook'
          : 'intel-badge-inference'
  const label =
    lower === 'fact'
      ? '事实 Fact'
      : lower === 'hypothesis'
        ? '假设 Hypothesis'
        : lower === 'outlook'
          ? '条件展望 Outlook'
          : '推断 Inference'
  return <span className={`intel-badge ${cls}`}>{label}</span>
}

export function StanceBadge({ label }: { label?: string | null }) {
  const v = label || 'Unclassified'
  const cls =
    v === 'Positive'
      ? 'intel-badge-pos'
      : v === 'Neutral'
        ? 'intel-badge-neu'
        : v === 'Negative'
          ? 'intel-badge-neg'
          : 'intel-badge-warn'
  return <span className={`intel-badge ${cls}`}>{v}</span>
}

export function StanceBar({
  positiveRate,
  neutralRate,
  negativeRate,
}: {
  positiveRate: number | null | undefined
  neutralRate: number | null | undefined
  negativeRate: number | null | undefined
}) {
  const p = typeof positiveRate === 'number' ? Math.max(0, positiveRate * 100) : 0
  const n = typeof neutralRate === 'number' ? Math.max(0, neutralRate * 100) : 0
  const neg = typeof negativeRate === 'number' ? Math.max(0, negativeRate * 100) : 0
  if (p + n + neg === 0) {
    return <span className="muted small">暂无已分类立场样本</span>
  }
  return (
    <div>
      <div className="intel-stance-bar" title={`Positive ${p.toFixed(1)}% / Neutral ${n.toFixed(1)}% / Negative ${neg.toFixed(1)}%`}>
        <div className="intel-stance-seg-pos" style={{ width: `${p}%` }} />
        <div className="intel-stance-seg-neu" style={{ width: `${n}%` }} />
        <div className="intel-stance-seg-neg" style={{ width: `${neg}%` }} />
      </div>
      <div className="muted small" style={{ marginTop: '0.2rem' }}>
        正面 {p.toFixed(1)}% · 中性 {n.toFixed(1)}% · 负面 {neg.toFixed(1)}%
      </div>
    </div>
  )
}

export function fmtPct(rate: number | null | undefined): string {
  if (typeof rate !== 'number' || Number.isNaN(rate)) return '—'
  return `${(rate * 100).toFixed(1)}%`
}

export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  return iso.replace('T', ' ').slice(0, 16)
}

export function SectionCard({
  title,
  subtitle,
  right,
  children,
}: {
  title: string
  subtitle?: string
  right?: ReactNode
  children: ReactNode
}) {
  return (
    <section className="panel">
      <div className="intel-header-row" style={{ marginBottom: '0.6rem' }}>
        <div>
          <h2 style={{ margin: 0 }}>{title}</h2>
          {subtitle && <p className="muted small" style={{ margin: '0.2rem 0 0' }}>{subtitle}</p>}
        </div>
        {right}
      </div>
      {children}
    </section>
  )
}
