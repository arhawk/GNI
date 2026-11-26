import { useEffect, useState } from 'react'
import { fetchSystemStatus } from '../api'
import { SourceOpsTable, type SourceOpsRow } from '../components/tables'

export function SystemPage() {
  const [data, setData] = useState<Awaited<ReturnType<typeof fetchSystemStatus>> | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchSystemStatus()
      .then(setData)
      .catch((e: Error) => setError(e.message))
  }, [])

  if (error) return <div className="panel error">{error}</div>
  if (!data) return <div className="panel muted">加载系统状态…</div>

  const t = data.totals

  return (
    <div className="panel">
      <h2>系统与数据管理</h2>
      {data.notes.map((n) => (
        <p key={n} className="muted small">
          {n}
        </p>
      ))}
      <div className="kpi-grid compact">
        <div className="kpi">
          <div className="kpi-value">{t.sources}</div>
          <div className="kpi-label">注册来源</div>
        </div>
        <div className="kpi">
          <div className="kpi-value">{t.active_sources}</div>
          <div className="kpi-label">活跃来源</div>
        </div>
        <div className="kpi">
          <div className="kpi-value">{t.articles}</div>
          <div className="kpi-label">文章总量</div>
        </div>
        <div className="kpi">
          <div className="kpi-value">{t.analysis_backlog}</div>
          <div className="kpi-label">分析积压</div>
        </div>
        <div className="kpi">
          <div className="kpi-value">{t.excluded}</div>
          <div className="kpi-label">排除篇数</div>
        </div>
      </div>

      <h3>来源健康</h3>
      <SourceOpsTable rows={data.source_health as SourceOpsRow[]} />
    </div>
  )
}
