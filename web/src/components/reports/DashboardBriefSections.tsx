import { Link } from 'react-router-dom'
import type { DashboardPayload } from '../../apiV2'
import { useEvidenceDrawer } from '../EvidenceContext'
import {
  ClassificationBadge,
  fmtDateTime,
  fmtPct,
  SampleSizeBadge,
  SectionCard,
  StanceBar,
} from '../StateBlocks'
import '../intel.css'

export function DashboardBriefSections({
  data,
  trendDays = 14,
}: {
  data: DashboardPayload
  trendDays?: number
}) {
  const { openEvidence } = useEvidenceDrawer()
  const ov = data.executive_overview
  const st = ov.stance_distribution
  const assess = data.executive_assessment
  const att = data.global_attention
  const maxTrend = Math.max(1, ...att.volume_trend.map((d) => d.china_articles))
  const maxTopic = Math.max(1, ...att.topics.map((t) => t.article_count))

  return (
    <div className="intel-page" style={{ gap: '0.9rem', marginBottom: '1.25rem' }}>
      {/* A. Executive Overview */}
      <SectionCard
        title="A · Executive Overview"
        subtitle="基于确定性 V1.0 统计快照（Unique Article Count，严格按 published_at 与信源国家归属）"
      >
        <div className="intel-kpi-row">
          <div className="intel-kpi-card primary">
            <div className="intel-kpi-label">今日涉华唯一文章总量 (Article Count)</div>
            <div className="intel-kpi-value">{ov.article_count}</div>
            <div className="intel-kpi-sub">
              较昨日 {ov.vs_yesterday ? `${ov.vs_yesterday.delta >= 0 ? '+' : ''}${ov.vs_yesterday.delta}` : '—'} ·
              较7日均 {ov.vs_7d_avg ? `${ov.vs_7d_avg.delta >= 0 ? '+' : ''}${ov.vs_7d_avg.delta}` : '—'}
            </div>
          </div>
          <div className="intel-kpi-card">
            <div className="intel-kpi-label">高重要事件数</div>
            <div className="intel-kpi-value">{ov.major_events ?? 0}</div>
            <div className="intel-kpi-sub">重要度 ≥ 0.7 · 新发现 {ov.new_events ?? 0} 个</div>
          </div>
          <div className="intel-kpi-card">
            <div className="intel-kpi-label">报道媒体 / 活跃信源</div>
            <div className="intel-kpi-value">
              {ov.reporting_sources}
              <span className="muted small"> / {ov.active_sources ?? '—'}</span>
            </div>
            <div className="intel-kpi-sub">当期涉华发稿信源</div>
          </div>
          <div className="intel-kpi-card">
            <div className="intel-kpi-label">Stance Coverage Rate</div>
            <div className="intel-kpi-value">{fmtPct(ov.stance_coverage_rate)}</div>
            <div className="intel-kpi-sub">
              已分类 {st.classified_count} · Unclassified {st.unclassified_count}
            </div>
          </div>
        </div>

        <div style={{ marginTop: '0.9rem' }}>
          <div className="intel-header-row" style={{ marginBottom: '0.35rem' }}>
            <strong style={{ fontSize: '0.88rem' }}>
              整体对华立场分布（target: {st.target}）
            </strong>
            <Link to="/stance" className="muted small">
              进入情感与立场分析 →
            </Link>
          </div>
          <StanceBar
            positiveRate={st.positive_rate}
            neutralRate={st.neutral_rate}
            negativeRate={st.negative_rate}
          />
          {st.denominator_note && <p className="muted small">{st.denominator_note}</p>}
        </div>
      </SectionCard>

      {/* B. Executive Assessment */}
      <SectionCard
        title="B · Executive Assessment（核心研判结论）"
        subtitle={`来源：日报第一章 / overall_situation_assessment · 状态：${assess.status}`}
      >
        <div className="intel-banner" style={{ marginBottom: '0.8rem' }}>
          <div className="muted small" style={{ marginBottom: '0.25rem' }}>
            Overall Situation
          </div>
          <p style={{ margin: 0, lineHeight: 1.6 }}>
            {assess.overall_situation || '当前周期尚未运行 LLM 研判，已展示确定性统计概览；可在下方触发研判。'}
          </p>
        </div>

        <div className="intel-grid-2">
          <div>
            <h4>Key Findings</h4>
            {assess.key_findings.length === 0 ? (
              <p className="muted small">暂无结构化核心发现（可点击下方「生成研判」）。</p>
            ) : (
              assess.key_findings.slice(0, 5).map((f, idx) => (
                <div key={idx} className="intel-finding-item">
                  <div className="intel-header-row">
                    <strong>{f.title || `发现 ${idx + 1}`}</strong>
                    <ClassificationBadge kind={f.classification} />
                  </div>
                  <p className="small" style={{ margin: '0.35rem 0 0' }}>
                    {f.statement || f.summary}
                  </p>
                  {Array.isArray(f.evidence_refs) && f.evidence_refs.length > 0 && (
                    <div className="intel-chip-row">
                      {f.evidence_refs.slice(0, 3).map((ref, rIdx) => {
                        const rid = ref.evidence_id || ref.article_id || ref.ref_id
                        if (!rid || ref.type === 'metric') return null
                        return (
                          <button
                            key={rIdx}
                            type="button"
                            className="intel-ev-btn"
                            onClick={() => openEvidence(rid)}
                          >
                            证据: {ref.label || rid.slice(0, 12)}
                          </button>
                        )
                      })}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>

          <div>
            <h4>Most Important Changes &amp; Watch Items</h4>
            {assess.most_important_changes.length > 0 && (
              <ul className="event-list">
                {assess.most_important_changes.slice(0, 4).map((c, idx) => (
                  <li key={idx}>
                    <strong>{c.title}</strong>
                    <div className="muted small">{c.summary}</div>
                  </li>
                ))}
              </ul>
            )}
            {assess.watch_items.length > 0 && (
              <>
                <h4 style={{ marginTop: '0.75rem' }}>Important Watch Items</h4>
                <ul className="event-list">
                  {assess.watch_items.slice(0, 4).map((w, idx) => (
                    <li key={idx}>
                      {typeof w === 'string' ? (
                        w
                      ) : (
                        <>
                          <strong>{String(w.observation_object || w.title || w.item || '观察项')}</strong>
                          {w.trigger_condition ? (
                            <div className="muted small">触发条件：{String(w.trigger_condition)}</div>
                          ) : null}
                        </>
                      )}
                    </li>
                  ))}
                </ul>
              </>
            )}
            <div style={{ marginTop: '0.5rem' }}>
              <Link to="/outlook" className="muted small">
                查看完整展望与观察清单 →
              </Link>
            </div>
          </div>
        </div>
      </SectionCard>

      {/* C. Global Attention */}
      <SectionCard
        title="C · Global Attention（全球关注格局）"
        subtitle={att.topic_overlap_note}
      >
        <div className="intel-grid-2">
          <div>
            <h4>近 {trendDays} 日全球涉华报道量趋势</h4>
            {att.volume_trend.length === 0 ? (
              <p className="muted small">暂无历史趋势样本</p>
            ) : (
              <div className="bars">
                {att.volume_trend.map((d) => (
                  <div className="bar-row" key={d.date}>
                    <span className="bar-label">{d.date.slice(5)}</span>
                    <div className="bar-track">
                      <div
                        className="bar-fill"
                        style={{ width: `${Math.round((d.china_articles / maxTrend) * 100)}%` }}
                      />
                    </div>
                    <span className="bar-n">{d.china_articles}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div>
            <div className="intel-header-row">
              <h4>国家报道量分布（按信源所属国）</h4>
              <Link to="/countries" className="muted small">
                多国对比 →
              </Link>
            </div>
            {att.countries.length === 0 ? (
              <p className="muted small">当期无国家样本</p>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>国家</th>
                    <th>文章数</th>
                    <th>立场覆盖率</th>
                    <th>样本</th>
                  </tr>
                </thead>
                <tbody>
                  {att.countries.map((c) => (
                    <tr key={c.scope_id}>
                      <td>
                        <Link to={`/countries?c=${encodeURIComponent(c.scope_id)}`}>
                          <strong>{c.scope_id}</strong>
                        </Link>
                      </td>
                      <td>{c.article_count}</td>
                      <td>{fmtPct(c.stance_coverage_rate)}</td>
                      <td>
                        <SampleSizeBadge count={c.article_count} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        <div className="intel-grid-2" style={{ marginTop: '1rem' }}>
          <div>
            <h4>四大板块分布</h4>
            <ul className="event-list">
              {att.boards.map((b) => (
                <li key={b.scope_id}>
                  <span>{b.label_zh || b.scope_id}</span>
                  <span className="meta">{b.article_count} 篇</span>
                </li>
              ))}
            </ul>
          </div>
          <div>
            <div className="intel-header-row">
              <h4>十五个固定议题分布（允许重叠）</h4>
              <Link to="/topics" className="muted small">
                进入议题分析 →
              </Link>
            </div>
            <div className="bars">
              {att.topics
                .slice()
                .sort((a, b) => b.article_count - a.article_count)
                .slice(0, 10)
                .map((t) => (
                  <div className="bar-row" key={t.scope_id}>
                    <span className="bar-label" style={{ width: '130px' }}>
                      <Link to={`/topics?t=${encodeURIComponent(t.scope_id)}`}>
                        {t.label_zh || t.scope_id}
                      </Link>
                    </span>
                    <div className="bar-track">
                      <div
                        className="bar-fill"
                        style={{ width: `${Math.round((t.article_count / maxTopic) * 100)}%` }}
                      />
                    </div>
                    <span className="bar-n">{t.article_count}</span>
                  </div>
                ))}
            </div>
          </div>
        </div>
      </SectionCard>

      {/* D. Key Developments */}
      <SectionCard
        title="D · Key Developments（重点事件）"
        subtitle="点击事件查看事件时间线 (event_time)、跨国差异与 7 维事件研判"
        right={
          <Link to="/events" className="muted small">
            全部事件 →
          </Link>
        }
      >
        {data.key_developments.length === 0 ? (
          <p className="muted small">当前周期暂无聚合重点事件。</p>
        ) : (
          <div className="intel-grid-2">
            {data.key_developments.slice(0, 6).map((ev) => (
              <div key={ev.event_id} className="intel-card">
                <div className="intel-header-row">
                  <Link to={`/events/${ev.event_id}`}>
                    <strong>{ev.title}</strong>
                  </Link>
                  <span className="intel-badge">{ev.event_type || 'event'}</span>
                </div>
                <div className="muted small" style={{ marginTop: '0.25rem' }}>
                  事件时间：{ev.event_time ? fmtDateTime(ev.event_time) : '时间未知'} · {ev.article_count} 篇 ·{' '}
                  {ev.country_count} 国 ({ev.countries.join(', ') || '—'}) · {ev.source_count} 家媒体
                </div>
                {ev.overview_text && <p className="small">{ev.overview_text}</p>}
                {ev.representative_articles.length > 0 && (
                  <div className="intel-chip-row">
                    {ev.representative_articles.map((a) => (
                      <button
                        key={a.article_id}
                        type="button"
                        className="intel-ev-btn"
                        onClick={() => openEvidence(a.article_id)}
                      >
                        代表文章: {(a.title || a.article_id).slice(0, 26)}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </SectionCard>

      {/* E. Emerging Signals */}
      <SectionCard
        title="E · Emerging Signals（新兴信号：严格区分事实与分析推断）"
        right={
          <Link to="/narratives" className="muted small">
            叙事追踪 →
          </Link>
        }
      >
        <div className="intel-grid-2">
          <div>
            <h4>
              <ClassificationBadge kind="Fact" /> 已观察到的事实与规则信号
            </h4>
            {data.emerging_signals.observed_facts.length === 0 ? (
              <p className="muted small">当期无新增规则异常事实。</p>
            ) : (
              data.emerging_signals.observed_facts.slice(0, 5).map((s, idx) => (
                <div key={idx} className="intel-finding-item">
                  <strong>{String(s.title || s.statement || '信号')}</strong>
                  <div className="muted small">{String(s.summary || '')}</div>
                </div>
              ))
            )}
          </div>
          <div>
            <h4>
              <ClassificationBadge kind="Inference" /> 分析推断与待验证风险信号
            </h4>
            {data.emerging_signals.analytical_inferences.length === 0 ? (
              <p className="muted small">暂无模型推断信号（运行研判后自动展示）。</p>
            ) : (
              data.emerging_signals.analytical_inferences.slice(0, 5).map((s, idx) => (
                <div key={idx} className="intel-finding-item">
                  <strong>{String(s.title || s.statement || '推断')}</strong>
                  <div className="muted small">{String(s.summary || '')}</div>
                </div>
              ))
            )}
          </div>
        </div>
      </SectionCard>
    </div>
  )
}
