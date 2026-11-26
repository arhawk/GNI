import { useState } from 'react'
import { fetchArticleTrace, type TraceArticle, type V1StatRow } from '../../api'
import { EvidenceTraceTable } from './EvidenceTraceTable'
import './tables.css'

function fmtPct(v: number | null | undefined) {
  return typeof v === 'number' ? `${(v * 100).toFixed(1)}%` : '—'
}

export function StanceMatrixTable({
  rows,
  dimensionLabel,
  emptyText = '暂无样本',
  enableTrace = true,
}: {
  rows: V1StatRow[]
  dimensionLabel: string
  emptyText?: string
  enableTrace?: boolean
}) {
  const [selectedKey, setSelectedKey] = useState<string | null>(null)
  const [selectedTitle, setSelectedTitle] = useState<string>('')
  const [traceRows, setTraceRows] = useState<TraceArticle[]>([])
  const [traceLoading, setTraceLoading] = useState(false)
  const [traceError, setTraceError] = useState<string | null>(null)

  if (!rows.length) return <p className="muted small">{emptyText}</p>

  async function handleSelect(row: V1StatRow) {
    if (!enableTrace) return
    const key = `${row.scope_type}:${row.scope_id}`
    if (selectedKey === key) {
      setSelectedKey(null)
      return
    }
    setSelectedKey(key)
    setSelectedTitle(`${row.label_zh || row.scope_id}（共 ${row.article_count} 篇唯一文章）`)
    setTraceError(null)
    const ids = row.article_ids || []
    if (!ids.length) {
      setTraceRows([])
      return
    }
    setTraceLoading(true)
    try {
      const res = await fetchArticleTrace(ids, 20)
      setTraceRows(res.articles || [])
    } catch (e) {
      setTraceError(e instanceof Error ? e.message : String(e))
      setTraceRows([])
    } finally {
      setTraceLoading(false)
    }
  }

  return (
    <div className="gni-table-block">
      <div className="gni-table-wrap">
        <table className="gni-table">
          <thead>
            <tr>
              <th>{dimensionLabel}</th>
              <th className="gni-num">唯一文章数</th>
              <th>对华立场分布（不含 Unclassified 分母）</th>
              <th className="gni-num">Unclassified</th>
              <th className="gni-num">覆盖率</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const key = `${r.scope_type}:${r.scope_id}`
              const posW = typeof r.positive_rate === 'number' ? r.positive_rate * 100 : 0
              const neuW = typeof r.neutral_rate === 'number' ? r.neutral_rate * 100 : 0
              const negW = typeof r.negative_rate === 'number' ? r.negative_rate * 100 : 0
              const lowCov = typeof r.stance_coverage_rate === 'number' && r.stance_coverage_rate < 0.7
              const isSelected = selectedKey === key
              return (
                <tr
                  key={key}
                  className={`${enableTrace ? 'gni-clickable' : ''}${isSelected ? ' gni-selected' : ''}`}
                  onClick={() => handleSelect(r)}
                >
                  <td>
                    <strong>{r.label_zh || r.scope_id}</strong>
                  </td>
                  <td className="gni-num">
                    <strong>{r.article_count}</strong>
                  </td>
                  <td className="gni-bar-cell">
                    <div
                      className="gni-stance-bar"
                      role="img"
                      aria-label={`正面 ${fmtPct(r.positive_rate)} 中性 ${fmtPct(r.neutral_rate)} 负面 ${fmtPct(r.negative_rate)}`}
                    >
                      <span className="gni-seg-pos" style={{ width: `${posW.toFixed(1)}%` }} />
                      <span className="gni-seg-neu" style={{ width: `${neuW.toFixed(1)}%` }} />
                      <span className="gni-seg-neg" style={{ width: `${negW.toFixed(1)}%` }} />
                    </div>
                    <div className="gni-bar-meta">
                      <span className="gni-c-pos">
                        正 {fmtPct(r.positive_rate)} ({r.positive_count})
                      </span>
                      <span>
                        中 {fmtPct(r.neutral_rate)} ({r.neutral_count})
                      </span>
                      <span className="gni-c-neg">
                        负 {fmtPct(r.negative_rate)} ({r.negative_count})
                      </span>
                    </div>
                  </td>
                  <td className="gni-num muted">{r.unclassified_count}</td>
                  <td className={`gni-num${lowCov ? ' gni-c-warn' : ''}`}>
                    {fmtPct(r.stance_coverage_rate)}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <div className="gni-legend">
        <span>
          <i className="gni-dot gni-seg-pos" />
          正面 Positive
        </span>
        <span>
          <i className="gni-dot gni-seg-neu" />
          中性 Neutral
        </span>
        <span>
          <i className="gni-dot gni-seg-neg" />
          负面 Negative
        </span>
        {enableTrace && <span>· 点击任意行可查看溯源文章与原文立场证据</span>}
      </div>

      {selectedKey && (
        <div className="gni-drawer">
          <div className="gni-drawer-head">
            <span>溯源文章 · {selectedTitle}</span>
            <button type="button" className="linkish" onClick={() => setSelectedKey(null)}>
              收起溯源
            </button>
          </div>
          <EvidenceTraceTable articles={traceRows} loading={traceLoading} error={traceError} />
        </div>
      )}
    </div>
  )
}
