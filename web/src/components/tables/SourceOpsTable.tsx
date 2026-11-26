import { useState } from 'react'
import './tables.css'

export type SourceOpsRow = {
  source_id: string
  name?: string | null
  country_id?: string | null
  source_type?: string | null
  status?: string | null
  active_status?: string | null
  success_count?: number
  failure_count?: number
  last_error?: string | null
}

function statusMeta(r: SourceOpsRow) {
  const st = (r.status || r.active_status || 'unknown').toLowerCase()
  if (st === 'ok' || st === 'active') return { label: st.toUpperCase(), cls: 'gni-pill-pos', isFail: false }
  if (st === 'rate_limited' || st === 'paused') return { label: st.toUpperCase(), cls: 'gni-pill-warn', isFail: true }
  return { label: st.toUpperCase(), cls: 'gni-pill-neg', isFail: true }
}

export function SourceOpsTable({
  rows,
  defaultOnlyFailed = false,
}: {
  rows: SourceOpsRow[]
  defaultOnlyFailed?: boolean
}) {
  const [onlyFailed, setOnlyFailed] = useState(defaultOnlyFailed)

  const sorted = [...rows].sort((a, b) => {
    const fa = statusMeta(a).isFail ? 0 : 1
    const fb = statusMeta(b).isFail ? 0 : 1
    if (fa !== fb) return fa - fb
    return (b.failure_count ?? 0) - (a.failure_count ?? 0)
  })
  const visible = onlyFailed ? sorted.filter((r) => statusMeta(r).isFail) : sorted

  return (
    <div className="gni-table-block">
      <div className="gni-table-head">
        <span className="muted small">
          共 {rows.length} 个源 · 异常 {sorted.filter((r) => statusMeta(r).isFail).length} 个
        </span>
        <button
          type="button"
          className="linkish"
          aria-pressed={onlyFailed}
          onClick={() => setOnlyFailed(!onlyFailed)}
        >
          {onlyFailed ? '显示全部源' : '仅看异常源'}
        </button>
      </div>
      <div className="gni-table-wrap">
        <table className="gni-table">
          <thead>
            <tr>
              <th>国家</th>
              <th>信源名称</th>
              <th>状态</th>
              <th className="gni-num">成功 / 失败</th>
              <th className="gni-num">成功率</th>
              <th>最近错误</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((r) => {
              const meta = statusMeta(r)
              const ok = Number(r.success_count ?? 0)
              const fail = Number(r.failure_count ?? 0)
              const total = ok + fail
              const rate = total > 0 ? `${((ok / total) * 100).toFixed(1)}%` : '—'
              return (
                <tr key={r.source_id} className={meta.isFail ? 'gni-row-flag' : undefined}>
                  <td>
                    <strong>{r.country_id || '—'}</strong>
                  </td>
                  <td>
                    <strong>{r.name || r.source_id}</strong>
                    {r.name && <div className="gni-mono muted">{r.source_id}</div>}
                  </td>
                  <td>
                    <span className={`gni-pill ${meta.cls}`}>{meta.label}</span>
                  </td>
                  <td className="gni-num">
                    {ok} / {fail}
                  </td>
                  <td className={`gni-num ${meta.isFail ? 'gni-c-warn' : 'gni-c-pos'}`}>{rate}</td>
                  <td className="gni-mono muted">{(r.last_error || '—').slice(0, 72)}</td>
                </tr>
              )
            })}
            {visible.length === 0 && (
              <tr>
                <td colSpan={6} className="muted">
                  当前无异常数据源
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
