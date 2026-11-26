import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  fetchDailyReportMarkdown,
  type GenericEvidenceRef,
  type ReportListItem,
  type ReportPackage,
  type ReportSection,
} from '../apiV2'
import { useEvidenceDrawer } from './EvidenceContext'
import { ClassificationBadge, fmtDateTime, PartialDataBanner } from './StateBlocks'
import './intel.css'

const SOURCE_KIND_ZH: Record<string, string> = {
  hybrid: '确定性指标 + LLM 研判',
  deterministic_metrics: '确定性统计（零 LLM 编造）',
  llm_assessment: '受校验 LLM 研判',
}

function EvidenceRefButtons({ refs }: { refs?: GenericEvidenceRef[] }) {
  const { openEvidence } = useEvidenceDrawer()
  if (!refs || refs.length === 0) return null
  return (
    <div className="intel-chip-row">
      {refs.slice(0, 8).map((r, idx) => {
        const rid = r.evidence_id || r.article_id || r.ref_id
        if (!rid) return null
        if (r.type === 'event') {
          return (
            <Link key={idx} to={`/events/${rid}`} className="intel-ev-btn">
              事件: {r.label || rid.slice(0, 12)}
            </Link>
          )
        }
        if (r.type === 'metric') {
          return (
            <span key={idx} className="intel-badge">
              指标: {r.label || rid.replace(/^metric:/, '')}
            </span>
          )
        }
        return (
          <button
            key={idx}
            type="button"
            className="intel-ev-btn"
            onClick={() => openEvidence(rid)}
            title={`定位原文证据: ${rid}`}
          >
            证据: {r.label || rid.slice(0, 14)}
          </button>
        )
      })}
    </div>
  )
}

function ChapterCard({ section, defaultOpen }: { section: ReportSection; defaultOpen: boolean }) {
  const [expanded, setExpanded] = useState(defaultOpen)
  return (
    <article className="intel-chapter">
      <div className="intel-chapter-head">
        <div>
          <h3 style={{ margin: 0 }}>{section.title}</h3>
          <div className="muted small" style={{ marginTop: '0.2rem' }}>
            {SOURCE_KIND_ZH[section.source_kind] || section.source_kind} · 状态：{section.status}
            {section.assessment_task_types.length > 0 &&
              ` · 研判任务：${section.assessment_task_types.join(', ')}`}
          </div>
        </div>
        <button type="button" className="intel-btn" onClick={() => setExpanded((v) => !v)}>
          {expanded ? '收起详情' : '展开详情'}
        </button>
      </div>

      {/* 1. Conclusion / Summary */}
      <p style={{ marginTop: '0.7rem', lineHeight: 1.65 }}>
        {section.summary || '本章节暂无摘要内容。'}
      </p>

      {/* 2. Key Findings & Interpretation */}
      {section.findings.length > 0 && (
        <div style={{ marginTop: '0.6rem' }}>
          {(expanded ? section.findings : section.findings.slice(0, 3)).map((f, idx) => (
            <div key={idx} className="intel-finding-item">
              <div className="intel-header-row">
                <strong>{f.title || `要点 ${idx + 1}`}</strong>
                <ClassificationBadge kind={f.classification} />
              </div>
              <p className="small" style={{ margin: '0.3rem 0 0' }}>
                {f.statement || f.summary}
              </p>
              <EvidenceRefButtons refs={f.evidence_refs} />
            </div>
          ))}
        </div>
      )}

      {/* 3. Evidence */}
      <EvidenceRefButtons refs={section.evidence_refs} />

      {/* 4. Expanded Statistics & Limitations */}
      {expanded && (
        <div style={{ marginTop: '0.8rem' }}>
          {section.metrics.length > 0 && (
            <details open>
              <summary className="muted small" style={{ cursor: 'pointer' }}>
                关联确定性指标快照（{section.metrics.length} 项）
              </summary>
              <div className="intel-grid-3" style={{ marginTop: '0.45rem' }}>
                {section.metrics.slice(0, 9).map((m, idx) => (
                  <div key={idx} className="intel-card" style={{ padding: '0.55rem 0.7rem' }}>
                    <div className="muted small">
                      {String(m.label_zh || m.scope_id || m.label || `指标 ${idx + 1}`)}
                    </div>
                    <strong>
                      {m.article_count != null
                        ? `${m.article_count} 篇`
                        : m.value != null
                          ? String(m.value)
                          : '—'}
                    </strong>
                  </div>
                ))}
              </div>
            </details>
          )}
          {section.limitations.length > 0 && (
            <div className="intel-banner intel-banner-warn" style={{ marginTop: '0.6rem' }}>
              <strong>章节局限：</strong> {section.limitations.join(' ')}
            </div>
          )}
        </div>
      )}
    </article>
  )
}

export function DailyReportPackageView({
  pkg,
  snapshots,
  selectedPeriod,
  onSelectPeriod,
  analyzing,
  analyzeError,
  onRunV2,
}: {
  pkg: ReportPackage
  snapshots: ReportListItem[]
  selectedPeriod: string | undefined
  onSelectPeriod: (period: string) => void
  analyzing: boolean
  analyzeError: string | null
  onRunV2: (force: boolean) => void
}) {
  const [markdown, setMarkdown] = useState<string | null>(null)
  const [mdError, setMdError] = useState<string | null>(null)

  async function toggleMarkdown() {
    if (markdown !== null) {
      setMarkdown(null)
      return
    }
    setMdError(null)
    try {
      const text = await fetchDailyReportMarkdown(selectedPeriod)
      setMarkdown(text)
    } catch (e) {
      setMdError(e instanceof Error ? e.message : String(e))
    }
  }

  return (
    <div className="intel-page">
      <div className="intel-banner">
        <div className="intel-header-row">
          <div>
            <h2 style={{ margin: 0 }}>Daily Intelligence Brief · {pkg.report_id}</h2>
            <div className="muted small" style={{ marginTop: '0.25rem' }}>
              窗口：{fmtDateTime(pkg.period_start)} → {fmtDateTime(pkg.period_end)} UTC · 生成状态：
              <strong>{pkg.generation_status}</strong> · 校验状态：
              <strong>{pkg.validation_status}</strong> · 章节：{pkg.sections.length}
            </div>
          </div>
          <div className="intel-chip-row">
            {snapshots.length > 0 && (
              <select
                value={selectedPeriod || ''}
                onChange={(e) => onSelectPeriod(e.target.value)}
                aria-label="选择已保存日报快照"
                className="intel-btn"
              >
                <option value="">最新实时日报</option>
                {snapshots.map((s) => (
                  <option key={s.id} value={s.period}>
                    快照 {s.period} ({s.generation_status || 'saved'})
                  </option>
                ))}
              </select>
            )}
            <button
              type="button"
              className="intel-btn primary"
              disabled={analyzing}
              onClick={() => onRunV2(false)}
            >
              {analyzing ? '运行 V2 研判中…' : '运行 V2 研判并保存快照'}
            </button>
            <button
              type="button"
              className="intel-btn"
              disabled={analyzing}
              onClick={() => onRunV2(true)}
            >
              强制重生成
            </button>
            <button type="button" className="intel-btn" onClick={toggleMarkdown}>
              {markdown !== null ? '隐藏 Markdown' : '查看 Markdown'}
            </button>
          </div>
        </div>
        <p className="muted small" style={{ margin: '0.5rem 0 0' }}>
          阅读顺序：结论 (Conclusion) → 关键发现 (Findings) → 解释研判 (Interpretation) → 证据追溯 (Evidence) → 统计附录 (Statistics)
        </p>
      </div>

      {analyzeError && <p className="error">研判触发失败：{analyzeError}</p>}
      {mdError && <p className="error">Markdown 导出失败：{mdError}</p>}

      {pkg.validation_notes.length > 0 && (
        <PartialDataBanner message={`报告校验提示：${pkg.validation_notes.join(' · ')}`} />
      )}

      {markdown !== null && (
        <div className="intel-card">
          <h4>Daily Intelligence Brief (Markdown)</h4>
          <pre className="intel-excerpt">{markdown}</pre>
        </div>
      )}

      {pkg.sections.map((sec, idx) => (
        <ChapterCard key={sec.section_id} section={sec} defaultOpen={idx < 2} />
      ))}

      {pkg.limitations.length > 0 && (
        <div className="intel-banner intel-banner-warn">
          <strong>报告级数据局限与方法论声明：</strong>
          <ul style={{ margin: '0.35rem 0 0 1.2rem' }}>
            {pkg.limitations.map((l, i) => (
              <li key={i}>{l}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
