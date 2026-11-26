import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import type {
  CanonicalAssessment,
  CrossCountryInterpretation,
  StanceInterpretationItem,
  TopicTrendInterpretation,
} from '../../api'
import { EvidenceChips } from './EvidenceChips'
import { FindingsGrid } from './IntelligenceHeader'
import './narrative.css'

/**
 * Unified 4-step analytical shell:
 * 1. Analysis conclusion -> 2. Key evidence -> 3. Data/table slot -> 4. Drill-down entries.
 */
export function AnalysisSectionShell({
  title,
  subtitle,
  conclusion,
  evidenceSlot,
  dataSlot,
  drilldownLinks,
}: {
  title: string
  subtitle?: string
  conclusion?: ReactNode
  evidenceSlot?: ReactNode
  dataSlot?: ReactNode
  drilldownLinks?: Array<{ label: string; to: string }>
}) {
  return (
    <div className="gni-intel-panel">
      <div className="gni-intel-panel-head">
        <h3>{title}</h3>
        {subtitle && <span className="muted small">{subtitle}</span>}
      </div>
      {conclusion && (
        <>
          <div className="gni-shell-step">1 · 分析结论</div>
          {conclusion}
        </>
      )}
      {evidenceSlot && (
        <>
          <div className="gni-shell-step">2 · 关键证据与分层判断</div>
          {evidenceSlot}
        </>
      )}
      {dataSlot && (
        <>
          <div className="gni-shell-step">3 · 确定性统计数据（程序计算）</div>
          {dataSlot}
        </>
      )}
      {drilldownLinks && drilldownLinks.length > 0 && (
        <>
          <div className="gni-shell-step">4 · 下钻入口</div>
          <div className="gni-ev-chips">
            {drilldownLinks.map((d) => (
              <Link key={d.to + d.label} to={d.to} className="gni-ev-chip">
                {d.label} →
              </Link>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

function persistenceZh(v?: string) {
  if (v === 'ongoing') return '持续趋势'
  if (v === 'short_term') return '短期波动'
  return '历史数据不足'
}

export function TopicTrendAnalysisBlock({
  assessment,
  dataSlot,
  title = '议题趋势解释（Trend Interpretation）',
}: {
  assessment?: CanonicalAssessment
  dataSlot?: ReactNode
  title?: string
}) {
  if (!assessment && !dataSlot) return null
  const items = ((assessment?.details?.topic_deep_dives || assessment?.details?.topic_shifts || []) as TopicTrendInterpretation[])

  return (
    <AnalysisSectionShell
      title={title}
      subtitle="严格区分：关注度变化（Attention）≠ 立场变化（Stance）≠ 议题结构变化（Structure）"
      conclusion={
        assessment ? (
          <div>
            {assessment.executive_summary && <p className="gni-intel-summary">{assessment.executive_summary}</p>}
            {items.length > 0 && (
              <div className="gni-findings-grid">
                {items.map((t) => (
                  <div key={t.topic_id} className="gni-finding-card">
                    <div className="gni-finding-top">
                      <strong>{t.topic_label || t.topic_id}</strong>
                      <span className="gni-tag">{persistenceZh(t.persistence)}</span>
                      <span className="gni-tag">置信度: {t.confidence || 'medium'}</span>
                      {t.needs_review && <span className="gni-pill gni-pill-warn">需复核</span>}
                    </div>
                    {t.attention_change && (
                      <div className="small">
                        <strong>关注度变化：</strong>
                        {t.attention_change}
                      </div>
                    )}
                    {t.stance_change && (
                      <div className="small">
                        <strong>立场变化：</strong>
                        {t.stance_change}
                      </div>
                    )}
                    {t.topic_structure_change && (
                      <div className="small">
                        <strong>议题结构：</strong>
                        {t.topic_structure_change}
                      </div>
                    )}
                    {(t.drivers || []).length > 0 && (
                      <div className="muted small">驱动因素：{(t.drivers || []).join('；')}</div>
                    )}
                    {(t.limitations || []).length > 0 && (
                      <div className="muted small">局限：{(t.limitations || []).join('；')}</div>
                    )}
                    <EvidenceChips refs={t.evidence_refs} />
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : undefined
      }
      evidenceSlot={
        assessment?.key_findings?.length || assessment?.limitations?.length ? (
          <>
            <FindingsGrid findings={assessment.key_findings} />
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
          </>
        ) : undefined
      }
      dataSlot={dataSlot}
      drilldownLinks={[
        { label: '查看趋势分析页', to: '/trends' },
        { label: '查看事件列表', to: '/events' },
      ]}
    />
  )
}

export function CrossCountryAnalysisBlock({
  assessment,
  dataSlot,
  title = '跨国媒体叙事横向比较（Comparative Analysis）',
}: {
  assessment?: CanonicalAssessment
  dataSlot?: ReactNode
  title?: string
}) {
  if (!assessment && !dataSlot) return null
  const items = ((assessment?.details?.cross_country_comparisons || assessment?.details?.country_differences || []) as CrossCountryInterpretation[])

  return (
    <AnalysisSectionShell
      title={title}
      subtitle="基于各国代表文章实际表达比较，严禁仅凭篇数推断差异；样本不足国家单独披露"
      conclusion={
        assessment ? (
          <div>
            {assessment.executive_summary && <p className="gni-intel-summary">{assessment.executive_summary}</p>}
            {items.map((item, idx) => (
              <div key={`${item.subject_id || idx}`} className="gni-event-interp-card" style={{ marginBottom: '0.7rem' }}>
                <div className="gni-intel-panel-head">
                  <h4>{item.subject_label || item.subject_id || '跨国叙事对比'}</h4>
                  <div style={{ display: 'flex', gap: '0.35rem', alignItems: 'center' }}>
                    <span className="gni-tag">{item.subject_type || 'topic'}</span>
                    <span className="gni-tag">置信度: {item.confidence || 'medium'}</span>
                    {item.needs_review && <span className="gni-pill gni-pill-warn">需复核</span>}
                  </div>
                </div>
                {item.common_focus && (
                  <p className="small" style={{ margin: '0.25rem 0' }}>
                    <strong>共同关注点：</strong>
                    {item.common_focus}
                  </p>
                )}
                {item.major_differences && (
                  <p className="small" style={{ margin: '0.25rem 0' }}>
                    <strong>核心差异：</strong>
                    {item.major_differences}
                  </p>
                )}
                {item.emerging_or_shifting && (
                  <p className="small" style={{ margin: '0.25rem 0' }}>
                    <strong>新兴 / 变化叙事：</strong>
                    {item.emerging_or_shifting}
                  </p>
                )}
                {(item.country_frames || []).length > 0 && (
                  <div className="gni-event-interp-grid">
                    {(item.country_frames || []).map((cf) => (
                      <div key={cf.country_id} className="gni-kv-box">
                        <div className="gni-kv-label">
                          <Link to={`/countries?c=${encodeURIComponent(cf.country_id)}`}>
                            {cf.country_id} 监测媒体框架 →
                          </Link>
                        </div>
                        {cf.main_frame && <div>主框架：{cf.main_frame}</div>}
                        {cf.unique_angle && <div className="muted small">独有视角：{cf.unique_angle}</div>}
                        {cf.sample_note && <div className="muted small">{cf.sample_note}</div>}
                        <EvidenceChips refs={cf.evidence_refs} />
                      </div>
                    ))}
                  </div>
                )}
                {(item.insufficient_sample_countries || []).length > 0 && (
                  <p className="gni-c-warn small" style={{ margin: '0.35rem 0' }}>
                    样本不足（未作叙事外推）：{(item.insufficient_sample_countries || []).join(', ')}
                  </p>
                )}
                <EvidenceChips refs={item.evidence_refs} />
              </div>
            ))}
          </div>
        ) : undefined
      }
      evidenceSlot={
        assessment?.key_findings?.length || assessment?.limitations?.length ? (
          <>
            <FindingsGrid findings={assessment.key_findings} />
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
          </>
        ) : undefined
      }
      dataSlot={dataSlot}
      drilldownLinks={[{ label: '进入国家对比分析页', to: '/countries' }]}
    />
  )
}

export function StanceAnalysisBlock({
  assessment,
  dataSlot,
  title = '对华立场变化解读（Stance Analysis）',
}: {
  assessment?: CanonicalAssessment
  dataSlot?: ReactNode
  title?: string
}) {
  if (!assessment && !dataSlot) return null
  const items = ((assessment?.details?.stance_observations || []) as StanceInterpretationItem[])

  return (
    <AnalysisSectionShell
      title={title}
      subtitle="严格使用程序计算的 V1.0 Positive/Neutral/Negative 比例与覆盖率，区分比例变化与绝对篇数变化"
      conclusion={
        assessment ? (
          <div>
            {assessment.executive_summary && <p className="gni-intel-summary">{assessment.executive_summary}</p>}
            {items.length > 0 && (
              <div className="gni-findings-grid">
                {items.map((s, idx) => (
                  <div key={`${s.scope_id || idx}`} className="gni-finding-card">
                    <div className="gni-finding-top">
                      <strong>{s.scope_label || s.scope_id}</strong>
                      <span className="gni-tag">{s.scope_type}</span>
                      <span className="gni-tag">置信度: {s.confidence || 'medium'}</span>
                      {s.needs_review && <span className="gni-pill gni-pill-warn">需复核</span>}
                    </div>
                    {s.rate_vs_count_note && <div className="small">{s.rate_vs_count_note}</div>}
                    {(s.drivers || []).length > 0 && (
                      <div className="muted small">推动因素：{(s.drivers || []).join('；')}</div>
                    )}
                    {s.coverage_limitation && (
                      <div className="muted small">覆盖率与样本局限：{s.coverage_limitation}</div>
                    )}
                    <EvidenceChips refs={s.evidence_refs} />
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : undefined
      }
      evidenceSlot={
        assessment?.key_findings?.length || assessment?.limitations?.length ? (
          <>
            <FindingsGrid findings={assessment.key_findings} />
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
          </>
        ) : undefined
      }
      dataSlot={dataSlot}
      drilldownLinks={[
        { label: '查看国家维度', to: '/countries' },
        { label: '查看趋势维度', to: '/trends' },
      ]}
    />
  )
}
