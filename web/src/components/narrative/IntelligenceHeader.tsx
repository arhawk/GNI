import { useState } from 'react'
import type { NarrativeFinding, ReportIntelligenceBlock } from '../../api'
import { EvidenceChips } from './EvidenceChips'
import './narrative.css'

function statusLabel(status?: string): { text: string; pill: string } {
  switch (status) {
    case 'completed':
      return { text: 'AI 情报解读已校验', pill: 'gni-pill-pos' }
    case 'needs_review':
      return { text: '已生成（部分项需人工复核）', pill: 'gni-pill-warn' }
    case 'partial':
      return { text: '部分任务已完成', pill: 'gni-pill-warn' }
    case 'failed':
      return { text: '解读任务失败（已回退规则报告）', pill: 'gni-pill-neg' }
    default:
      return { text: '仅规则统计基线（未生成 AI 解读）', pill: 'gni-pill-neu' }
  }
}

export function ClassificationBadge({ value }: { value: string }) {
  const norm = (value || 'Inference').toLowerCase()
  if (norm === 'fact') {
    return <span className="gni-cls-badge gni-cls-fact">Fact 事实</span>
  }
  if (norm === 'hypothesis') {
    return <span className="gni-cls-badge gni-cls-hypothesis">Hypothesis 待验证假设</span>
  }
  return <span className="gni-cls-badge gni-cls-inference">Inference 分析推断</span>
}

export function FindingsGrid({ findings }: { findings?: NarrativeFinding[] }) {
  if (!findings || findings.length === 0) return null
  return (
    <div className="gni-findings-grid">
      {findings.map((f, idx) => (
        <div key={`${f.title}-${idx}`} className="gni-finding-card">
          <div className="gni-finding-top">
            <ClassificationBadge value={f.classification} />
            <span className="gni-tag">置信度: {f.confidence || 'medium'}</span>
            {f.needs_review && <span className="gni-pill gni-pill-warn">需复核</span>}
          </div>
          <strong>{f.title}</strong>
          <div className="small">{f.conclusion}</div>
          {f.reasoning && <div className="muted small">依据：{f.reasoning}</div>}
          {(f.limitations || []).length > 0 && (
            <div className="muted small">局限：{(f.limitations || []).join('；')}</div>
          )}
          {(f.validation_notes || []).length > 0 && (
            <div className="gni-c-warn small">校验提示：{(f.validation_notes || []).join('；')}</div>
          )}
          <EvidenceChips refs={f.evidence_refs} />
        </div>
      ))}
    </div>
  )
}

export function IntelligenceHeader({
  intelligence,
  analyzing,
  analyzeError,
  onGenerate,
  onRetryFailed,
  title = '综合研判（Executive Judgment）',
}: {
  intelligence?: ReportIntelligenceBlock
  analyzing: boolean
  analyzeError: string | null
  onGenerate: (force: boolean) => void
  onRetryFailed: (failedTasks: string[]) => void
  title?: string
}) {
  const [showValidation, setShowValidation] = useState(false)
  const st = statusLabel(intelligence?.status)
  const meta = intelligence?.meta
  const taskStatuses = intelligence?.task_statuses || {}
  const failedTasks = Object.entries(taskStatuses)
    .filter(([, info]) => info.status === 'failed')
    .map(([k]) => k)
  const validationIssues = Object.entries(taskStatuses)
    .map(([k, info]) => {
      const v = info.validation as
        | {
            numeric_issues?: string[]
            evidence_issues?: string[]
            reasoning_issues?: string[]
            dropped_count?: number
            downgraded_count?: number
          }
        | null
        | undefined
      const all = [
        ...(v?.numeric_issues || []),
        ...(v?.evidence_issues || []),
        ...(v?.reasoning_issues || []),
      ]
      return { key: k, title: info.title_zh || k, issues: all, dropped: v?.dropped_count || 0, downgraded: v?.downgraded_count || 0 }
    })
    .filter((x) => x.issues.length > 0)
  const execTask = intelligence?.tasks?.executive_analysis

  return (
    <div>
      <div className="gni-intel-bar">
        <div>
          <div className="gni-intel-bar-left">
            <span className={`gni-pill ${st.pill}`}>{st.text}</span>
            {meta && meta.completed_tasks > 0 && (
              <span className="muted small">
                任务 {meta.completed_tasks}/{meta.total_tasks}
                {meta.model_versions?.length ? ` · 模型 ${meta.model_versions.join(', ')}` : ''}
                {meta.total_tokens ? ` · ${meta.total_tokens} tok` : ''}
              </span>
            )}
            {intelligence?.stale && (
              <span className="gni-pill gni-pill-warn">底层统计已更新，建议刷新解读</span>
            )}
          </div>
          {Object.keys(taskStatuses).length > 0 && (
            <div className="gni-intel-tasks-strip">
              {Object.entries(taskStatuses).map(([key, info]) => {
                const cls =
                  info.status === 'completed'
                    ? 'ok'
                    : info.status === 'failed'
                      ? 'err'
                      : info.status === 'needs_review' || info.status === 'degraded'
                        ? 'warn'
                        : ''
                return (
                  <span
                    key={key}
                    className={`gni-task-pill ${cls}`}
                    title={`${info.prompt_version || ''} · ${info.status}${info.error_message ? ` · ${info.error_message}` : ''}`}
                  >
                    {info.title_zh || key}: {info.status}
                  </span>
                )
              })}
            </div>
          )}
          {intelligence?.fallback_reason && (
            <p className="muted small" style={{ margin: '0.35rem 0 0' }}>
              回退说明：{intelligence.fallback_reason}
            </p>
          )}
          {validationIssues.length > 0 && (
            <div style={{ marginTop: '0.35rem' }}>
              <button
                type="button"
                className="linkish"
                onClick={() => setShowValidation(!showValidation)}
              >
                {showValidation
                  ? '收起校验复核原因'
                  : `查看校验复核原因（${validationIssues.reduce((acc, x) => acc + x.issues.length, 0)} 项）`}
              </button>
              {showValidation && (
                <div className="gni-kv-box" style={{ marginTop: '0.35rem' }}>
                  {validationIssues.map((item) => (
                    <div key={item.key} style={{ marginBottom: '0.35rem' }}>
                      <strong>
                        {item.title}
                        {item.dropped > 0 ? ` · 剔除 ${item.dropped}` : ''}
                        {item.downgraded > 0 ? ` · 降级 ${item.downgraded}` : ''}
                      </strong>
                      <ul className="event-list" style={{ margin: '0.2rem 0 0' }}>
                        {item.issues.slice(0, 6).map((msg, i) => (
                          <li key={i} className="gni-c-warn small">
                            {msg}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
          {analyzeError && (
            <p className="gni-c-neg small" style={{ margin: '0.35rem 0 0' }}>
              触发解读失败（规则报告仍正常展示）：{analyzeError}
            </p>
          )}
        </div>

        <div className="gni-intel-bar-actions">
          {failedTasks.length > 0 && (
            <button
              type="button"
              className="gni-btn-secondary"
              disabled={analyzing}
              onClick={() => onRetryFailed(failedTasks)}
            >
              {analyzing ? '执行中…' : `重试失败任务 (${failedTasks.length})`}
            </button>
          )}
          <button
            type="button"
            className="gni-btn-primary"
            disabled={analyzing}
            onClick={() => onGenerate(Boolean(meta && meta.completed_tasks > 0))}
          >
            {analyzing
              ? '正在生成 AI 情报解读…'
              : meta && meta.completed_tasks > 0
                ? '刷新 AI 情报解读'
                : '生成 AI 情报解读'}
          </button>
        </div>
      </div>

      {execTask && (
        <div className="gni-intel-panel">
          <div className="gni-intel-panel-head">
            <h3>{title}</h3>
            <span className="muted small">
              Prompt: {String(execTask.meta?.prompt_version || '—')} · 状态: {execTask.status}
            </span>
          </div>
          {execTask.summary && <p className="gni-intel-summary">{execTask.summary}</p>}

          {((execTask.important_changes || []).length > 0 || (execTask.main_drivers || []).length > 0) && (
            <div className="gni-two-col">
              {(execTask.important_changes || []).length > 0 && (
                <div className="gni-kv-box">
                  <div className="gni-kv-label">核心变化（Important Changes）</div>
                  <ul className="event-list" style={{ margin: 0 }}>
                    {(execTask.important_changes || []).map((c, i) => (
                      <li key={i}>{c}</li>
                    ))}
                  </ul>
                </div>
              )}
              {(execTask.main_drivers || []).length > 0 && (
                <div className="gni-kv-box">
                  <div className="gni-kv-label">主要驱动因素（Main Drivers）</div>
                  <ul className="event-list" style={{ margin: 0 }}>
                    {(execTask.main_drivers || []).map((d, i) => (
                      <li key={i}>{d}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          <FindingsGrid findings={execTask.findings} />

          {((execTask.uncertainties || []).length > 0 || (execTask.follow_up_questions || []).length > 0) && (
            <div className="gni-two-col">
              {(execTask.uncertainties || []).length > 0 && (
                <div className="gni-kv-box">
                  <div className="gni-kv-label">不确定性与局限（Uncertainties）</div>
                  <ul className="event-list" style={{ margin: 0 }}>
                    {(execTask.uncertainties || []).map((u, i) => (
                      <li key={i} className="muted">
                        {u}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {(execTask.follow_up_questions || []).length > 0 && (
                <div className="gni-kv-box">
                  <div className="gni-kv-label">待进一步核查（Follow-up Questions）</div>
                  <ul className="event-list" style={{ margin: 0 }}>
                    {(execTask.follow_up_questions || []).map((q, i) => (
                      <li key={i}>{q}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
