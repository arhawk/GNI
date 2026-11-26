import type { NarrativeTaskOutput } from '../../api'
import { EvidenceChips } from './EvidenceChips'
import { FindingsGrid } from './IntelligenceHeader'
import './narrative.css'

export function OutlookSignalsPanel({
  task,
  heading = '新兴风险信号与后续观察（Outlook & Monitoring）',
}: {
  task?: NarrativeTaskOutput
  heading?: string
}) {
  if (!task) return null
  const signals = task.outlook_signals || []
  if (!signals.length && !task.summary && !(task.findings || []).length) return null

  return (
    <div className="gni-intel-panel">
      <div className="gni-intel-panel-head">
        <h3>{heading}</h3>
        <span className="muted small">条件性研判，非既定预测 · Prompt: {String(task.meta?.prompt_version || '—')}</span>
      </div>
      {task.summary && <p className="gni-intel-summary">{task.summary}</p>}

      {signals.length > 0 && (
        <div className="gni-outlook-grid">
          {signals.map((sig, idx) => (
            <div key={idx} className="gni-outlook-card">
              <div className="gni-finding-top">
                <span className="gni-cls-badge gni-cls-hypothesis">条件性信号</span>
                <span className="gni-tag">置信度: {sig.confidence || 'medium'}</span>
                {sig.needs_review && <span className="gni-pill gni-pill-warn">需复核</span>}
              </div>
              <strong>{sig.signal}</strong>
              {sig.reasoning && <div>依据：{sig.reasoning}</div>}
              {sig.potential_trigger && (
                <div className="small">
                  <strong>潜在触发条件：</strong>
                  {sig.potential_trigger}
                </div>
              )}
              {(sig.what_to_monitor || []).length > 0 && (
                <div className="small">
                  <strong>监测指标：</strong>
                  {(sig.what_to_monitor || []).join('；')}
                </div>
              )}
              {sig.uncertainty && (
                <div className="muted small">
                  <strong>不确定性：</strong>
                  {sig.uncertainty}
                </div>
              )}
              <EvidenceChips refs={sig.evidence_refs} />
            </div>
          ))}
        </div>
      )}

      <FindingsGrid findings={task.findings} />
    </div>
  )
}
