import { Link } from 'react-router-dom'
import type { CanonicalAssessment, EventInterpretation } from '../../api'
import { EvidenceChips } from './EvidenceChips'
import { FindingsGrid } from './IntelligenceHeader'
import './narrative.css'

export function EventInterpretationCards({
  assessment,
  heading = '重点事件深度解读（Event Interpretation）',
}: {
  assessment?: CanonicalAssessment
  heading?: string
}) {
  if (!assessment) return null
  const items: EventInterpretation[] = (assessment.details?.event_interpretations || []) as EventInterpretation[]
  const summary = assessment.executive_summary || ''
  const findings = assessment.key_findings || []
  if (!items.length && !summary && !findings.length) return null

  return (
    <div className="gni-intel-panel">
      <div className="gni-intel-panel-head">
        <h3>{heading}</h3>
        <span className="muted small">
          Prompt: {assessment.prompt_version || '—'} · 区分事件本体变化 / 媒体关注度变化 / 各国跟进时间
        </span>
      </div>
      {summary && <p className="gni-intel-summary">{summary}</p>}

      {items.length > 0 && (
        <div className="gni-event-interp-list">
          {items.map((ev) => (
            <article key={ev.event_id} className="gni-event-interp-card">
              <div className="gni-intel-panel-head">
                <h4>
                  <Link to={`/events/${ev.event_id}`}>{ev.title}</Link>
                </h4>
                <div style={{ display: 'flex', gap: '0.35rem', alignItems: 'center' }}>
                  {ev.current_status && <span className="gni-tag">状态: {ev.current_status}</span>}
                  <span className="gni-tag">置信度: {ev.confidence || 'medium'}</span>
                  {ev.needs_review && <span className="gni-pill gni-pill-warn">需复核</span>}
                </div>
              </div>

              <div className="gni-event-interp-grid">
                {ev.what_happened && (
                  <div className="gni-kv-box">
                    <div className="gni-kv-label">发生了什么（What Happened）</div>
                    <div>{ev.what_happened}</div>
                  </div>
                )}
                {ev.background && (
                  <div className="gni-kv-box">
                    <div className="gni-kv-label">事件背景（Background）</div>
                    <div>{ev.background}</div>
                  </div>
                )}
                {ev.why_it_matters && (
                  <div className="gni-kv-box">
                    <div className="gni-kv-label">为什么值得关注（Why It Matters）</div>
                    <div>{ev.why_it_matters}</div>
                  </div>
                )}
                {ev.country_differences && (
                  <div className="gni-kv-box">
                    <div className="gni-kv-label">各国报道差异（Cross-Country View）</div>
                    <div>{ev.country_differences}</div>
                  </div>
                )}
              </div>

              {(ev.event_actual_changes || ev.coverage_attention_changes || ev.country_followup_timing) && (
                <div className="gni-event-interp-grid">
                  {ev.event_actual_changes && (
                    <div className="gni-kv-box">
                      <div className="gni-kv-label">1. 事件实际进展</div>
                      <div>{ev.event_actual_changes}</div>
                    </div>
                  )}
                  {ev.coverage_attention_changes && (
                    <div className="gni-kv-box">
                      <div className="gni-kv-label">2. 媒体关注度变化</div>
                      <div>{ev.coverage_attention_changes}</div>
                    </div>
                  )}
                  {ev.country_followup_timing && (
                    <div className="gni-kv-box">
                      <div className="gni-kv-label">3. 各国首次报道 / 跟进时间</div>
                      <div>{ev.country_followup_timing}</div>
                    </div>
                  )}
                </div>
              )}

              {((ev.media_viewpoints || []).length > 0 || (ev.what_to_monitor || []).length > 0) && (
                <div className="gni-two-col">
                  {(ev.media_viewpoints || []).length > 0 && (
                    <div className="gni-kv-box">
                      <div className="gni-kv-label">媒体主要观点</div>
                      <ul className="event-list" style={{ margin: 0 }}>
                        {(ev.media_viewpoints || []).map((v, i) => (
                          <li key={i}>{v}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {(ev.what_to_monitor || []).length > 0 && (
                    <div className="gni-kv-box">
                      <div className="gni-kv-label">后续观察重点</div>
                      <ul className="event-list" style={{ margin: 0 }}>
                        {(ev.what_to_monitor || []).map((m, i) => (
                          <li key={i}>{m}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}

              {(ev.limitations || []).length > 0 && (
                <p className="muted small" style={{ margin: '0.35rem 0' }}>
                  局限：{(ev.limitations || []).join('；')}
                </p>
              )}

              <EvidenceChips refs={ev.evidence_refs} />
            </article>
          ))}
        </div>
      )}

      <FindingsGrid findings={findings} />
      {(assessment.limitations || []).length > 0 && (
        <div className="gni-kv-box" style={{ marginTop: '0.5rem' }}>
          <div className="gni-kv-label">不确定性与局限（Uncertainties）</div>
          <ul className="event-list" style={{ margin: 0 }}>
            {(assessment.limitations || []).map((u, i) => (
              <li key={i} className="muted small">
                {u}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
