import type { CanonicalAssessment, OutlookSignalItem } from '../../api'
import { EvidenceChips } from './EvidenceChips'
import { FindingsGrid } from './IntelligenceHeader'
import './narrative.css'

export function OutlookSignalsPanel({
  assessment,
  heading = '新兴风险信号与后续观察（Outlook & Monitoring）',
}: {
  assessment?: CanonicalAssessment
  heading?: string
}) {
  if (!assessment) return null
  const signals: OutlookSignalItem[] = (
    (assessment.details?.outlook_signals as OutlookSignalItem[] | undefined) ||
    assessment.watch_items ||
    []
  ).filter((s) => s && typeof s === 'object' && 'signal' in s)
  const summary = assessment.executive_summary || ''
  const findings = assessment.key_findings || []
  const limitations = assessment.limitations || []
  const followUps = (assessment.details?.follow_up_questions || []) as string[]
  if (!signals.length && !summary && !findings.length) return null

  return (
    <div className="gni-intel-panel">
      <div className="gni-intel-panel-head">
        <h3>{heading}</h3>
        <span className="muted small">条件性研判，非既定预测 · Prompt: {assessment.prompt_version || '—'}</span>
      </div>
      {summary && <p className="gni-intel-summary">{summary}</p>}

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

      <FindingsGrid findings={findings} />
      {(limitations.length > 0 || followUps.length > 0) && (
        <div className="gni-two-col" style={{ marginTop: '0.5rem' }}>
          {limitations.length > 0 && (
            <div className="gni-kv-box">
              <div className="gni-kv-label">不确定性与局限（Uncertainties）</div>
              <ul className="event-list" style={{ margin: 0 }}>
                {limitations.map((u, i) => (
                  <li key={i} className="muted small">
                    {u}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {followUps.length > 0 && (
            <div className="gni-kv-box">
              <div className="gni-kv-label">待进一步核查（Follow-up Questions）</div>
              <ul className="event-list" style={{ margin: 0 }}>
                {followUps.map((q, i) => (
                  <li key={i} className="small">
                    {q}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
