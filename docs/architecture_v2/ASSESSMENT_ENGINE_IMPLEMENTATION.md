# ASSESSMENT_ENGINE_IMPLEMENTATION.md — Phase 5 统一研判引擎实施报告

> 分支：`cursor/data-trust-batch1` | 日期：2026-11-26 | 依据：GNI Architecture & Implementation Specification V2.0（Phase 5）

## 1. 架构设计与模块复用

- **统一任务执行框架（非 9 个独立 Agent）**：在 [src/gni/reports/narrative/assessment.py](src/gni/reports/narrative/assessment.py) 中建立单一注册表 `ASSESSMENT_TASK_SPECS` 与统一执行入口 `run_assessment_task()` / `run_assessment_suite()`，复用了既有：
  - 证据包与白名单校验基座：[src/gni/reports/narrative/evidence.py](src/gni/reports/narrative/evidence.py)
  - 三层校验器（Numeric / Evidence / Reasoning）：[src/gni/reports/narrative/validator.py](src/gni/reports/narrative/validator.py)
  - DeepSeek JSON 客户端与预算守卫：[src/gni/analysis/deepseek.py](src/gni/analysis/deepseek.py)、[src/gni/analysis/budget.py](src/gni/analysis/budget.py)
  - 数据库任务缓存表：`ReportNarrativeTask`（`src/gni/infrastructure/models.py`，0 新增表）

## 2. 九类研判任务实现状态

| # | `task_type` | 中文名称 | Prompt 版本 | 状态 | 专项约束落实 |
|---|---|---|---|---|---|
| 1 | `overall_situation_assessment` | 全局涉华态势综合研判 | `assess_overall_v2.0` | `implemented` | 禁止数字拼接；综合解释关注格局、变化、驱动与反证；兼容旧别名 `executive_analysis` |
| 2 | `change_detection_assessment` | 周期变化与异常检测研判 | `assess_change_v2.0` | `implemented` | 消费 `metrics/changes.py` 多因素变化信号，区分真实变化与小样本波动 |
| 3 | `event_analysis` | 重点事件七维深度研判 | `assess_event_v2.0` | `implemented` | 按背景、发生了什么、关键进展、媒体报道、跨国差异、可能影响、后续观察 7 维结构化输出 |
| 4 | `topic_analysis` | 议题格局与持续性研判 | `assess_topic_v2.0` | `implemented` | 锁定 4 大板块 × 15 议题，保留多议题重叠口径 |
| 5 | `country_comparison` | 国别媒体报道对比研判 | `assess_country_v2.0` | `implemented` | 按 `Source.country_id` 对比，强制披露样本量与立场覆盖率限制 |
| 6 | `narrative_analysis` | 叙事结构与演化扩散研判 | `assess_narrative_v2.0` | `implemented` | 消费 `NarrativeCluster` 正反例，规则拦截「由多国同时报道推断协调传播」 |
| 7 | `sentiment_stance_analysis` | 情感与对华立场独立研判 | `assess_sentiment_stance_v2.0` | `implemented` | 严格分离 Sentiment 与 Stance，绑定 `target="china_mainland"`，隔离 `media` vs `quoted_actor` |
| 8 | `risk_signal_assessment` | 风险信号与关注度分离研判 | `assess_risk_signal_v2.0` | `implemented` | 规则拦截「负面报道数量增加直接等同现实风险上升」，要求提供 `alternative_explanation` |
| 9 | `outlook_assessment` | 条件性展望与观察清单 | `assess_outlook_v2.0` | `implemented` | 强制条件性表述与 `observation_object`/`potential_trigger`/`alternative_scenario`/`uncertainty`；兼容旧别名 `emerging_signals` |

## 3. 统一研判结果 Schema（`AssessmentResultContract`）

定义在 [src/gni/core/contracts.py](src/gni/core/contracts.py) 中，由 `to_unified_assessment_result()` 投影生成，严格分离：
- `observations`（仅 `classification="Fact"`，必须附 `>= 1` 条真实 `evidence_refs`）
- `interpretations`（仅 `classification="Inference"`）
- `hypotheses`（`classification ∈ {"Hypothesis", "Outlook"}`）
- `evidence_refs`、`supporting_metrics`、`counter_evidence`、`limitations`、`watch_items`
- `confidence`（`high|medium|low`）并固定携带 `confidence_note = "Subjective model confidence only; must not be interpreted as empirical accuracy."`
- `status ∈ {"completed", "needs_review", "insufficient_data", "degraded", "failed"}`

## 4. 校验增强与失败处理机制

- **三层校验器新增红线**（[src/gni/reports/narrative/validator.py](src/gni/reports/narrative/validator.py)）：
  - `coordinated_propagation_overclaim`：拦截无直接证据的「协调传播/协同炒作」断言并降级。
  - `volume_as_real_risk`：拦截将「负面报道量增加」直接等同「现实/战略风险上升」的表述并降级。
  - 既有数字白名单校验、证据引用存在性校验与无证据 `Fact` 自动降级保持全量生效。
- **失败与证据不足处理**：
  - 零数据窗口（`global_article_count == 0`）：直接短路返回 `status="insufficient_data"`，不调用 LLM。
  - 无 API Key / 预算耗尽：返回 `status="degraded"`，保留确定性统计快照与原文证据引用。
  - LLM 超时 / 异常 / 非法 JSON：捕获异常并落库 `ReportNarrativeTask(status="failed", error_message=...)`，在 `allow_fallback=True` 时返回确定性降级结果，绝不编造数字。
