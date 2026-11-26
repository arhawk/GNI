import type { V1StatRow } from '../../api'
import './tables.css'

export function TrendDeltaTable({
  current,
  previous,
  dimensionLabel = '维度',
  showBoard = false,
}: {
  current: V1StatRow[]
  previous: V1StatRow[]
  dimensionLabel?: string
  showBoard?: boolean
}) {
  const prevMap = new Map(previous.map((r) => [r.scope_id, r]))
  const rows = current
    .filter((r) => r.article_count > 0 || (prevMap.get(r.scope_id)?.article_count ?? 0) > 0)
    .map((cur) => {
      const prev = prevMap.get(cur.scope_id)
      const prevCount = prev?.article_count ?? 0
      const deltaCount = cur.article_count - prevCount
      const negDelta =
        typeof cur.negative_rate === 'number' && typeof prev?.negative_rate === 'number'
          ? (cur.negative_rate - prev.negative_rate) * 100
          : null
      let status: 'anomaly' | 'rising' | 'steady' = 'steady'
      if ((deltaCount >= 5 && negDelta !== null && negDelta >= 10) || deltaCount >= 10) {
        status = 'anomaly'
      } else if (deltaCount >= 3 || (negDelta !== null && negDelta >= 8)) {
        status = 'rising'
      }
      return { cur, prevCount, deltaCount, negDelta, status }
    })
    .sort((a, b) => Math.abs(b.deltaCount) - Math.abs(a.deltaCount) || b.cur.article_count - a.cur.article_count)

  if (!rows.length) return <p className="muted small">暂无环比对比样本</p>

  return (
    <div className="gni-table-block">
      <div className="gni-table-wrap">
        <table className="gni-table">
          <thead>
            <tr>
              <th>{dimensionLabel}</th>
              {showBoard && <th>所属板块</th>}
              <th className="gni-num">本期</th>
              <th className="gni-num">上期</th>
              <th className="gni-num">量变 Δ</th>
              <th className="gni-num">负面率 Δ</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ cur, prevCount, deltaCount, negDelta, status }) => {
              const deltaCls = deltaCount > 0 ? 'gni-c-warn' : deltaCount < 0 ? 'gni-c-pos' : 'muted'
              const negCls =
                negDelta === null ? 'muted' : negDelta > 0 ? 'gni-c-neg' : negDelta < 0 ? 'gni-c-pos' : 'muted'
              return (
                <tr key={cur.scope_id} className={status === 'anomaly' ? 'gni-row-flag' : undefined}>
                  <td>
                    <strong>{cur.label_zh || cur.scope_id}</strong>
                  </td>
                  {showBoard && <td className="muted small">{cur.board_id || '—'}</td>}
                  <td className="gni-num">
                    <strong>{cur.article_count}</strong>
                  </td>
                  <td className="gni-num muted">{prevCount}</td>
                  <td className={`gni-num ${deltaCls}`}>
                    {deltaCount > 0 ? `+${deltaCount}` : String(deltaCount)}
                  </td>
                  <td className={`gni-num ${negCls}`}>
                    {negDelta === null ? '—' : `${negDelta > 0 ? '+' : ''}${negDelta.toFixed(1)}%`}
                  </td>
                  <td>
                    {status === 'anomaly' && <span className="gni-pill gni-pill-neg">异动</span>}
                    {status === 'rising' && <span className="gni-pill gni-pill-warn">升温</span>}
                    {status === 'steady' && <span className="gni-pill gni-pill-neu">平稳</span>}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
