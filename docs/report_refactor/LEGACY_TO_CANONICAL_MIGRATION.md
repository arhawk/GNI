# Legacy Report Narrative Layer → Canonical Assessment Engine 迁移映射

> 依据：`src/gni/reports/narrative/prompts.py`、`src/gni/reports/narrative/runner.py`、`src/gni/reports/narrative/assessment.py`、`src/gni/reports/daily_package.py`

## 1. 架构判定：单引擎可复用任务，非多 Agent 堆砌

审计 `src/gni/reports/narrative/assessment.py` 确认：9 类 Canonical Assessment 均通过统一的数据类注册表 `_build_assessment_registry()` (L68-250) 与单一执行入口 `run_assessment_task()` (L540-690) 运行，复用同一套 `build_task_evidence_package()`、`DeepSeekLLMProvider`、`validate_task_output()`、预算守卫与 `ReportNarrativeTask` 缓存表。**不存在 9 个互相独立重复执行的 Agent**，设计方向正确，无需拆分为多 Agent。

## 2. 逐项映射表（Legacy vs Canonical 9 任务）

| # | Canonical Task Type (`assessment.py`) | Legacy Task Type (`prompts.py`) | 输入证据 (`required_evidence_kinds`) | 核心输出字段 (`AssessmentResultContract`) | 当前调用报告 | 迁移状态 | 重复能力与迁移风险 |
|---|---|---|---|---|---|---|---|
| 1 | `overall_situation_assessment` (`assess_overall_v2.0`) | `executive_analysis` (`daily/weekly/monthly_exec_v1.0`) | `metrics`, `events`, `representative_evidence`, `counter_evidence` | `executive_summary`, `key_findings`, `observations/interpretations/hypotheses`, `details.important_changes`, `details.main_drivers` | Daily V2（通过 `legacy_alias="executive_analysis"` 兼容） | Daily 部分迁移；Weekly/Monthly 未迁移 | 与 `executive_analysis` 高度重叠；迁移需保留 `tasks.executive_analysis` 前端兼容投影。 |
| 2 | `change_detection_assessment` (`assess_change_v2.0`) | 无独立任务（分散在 `executive_analysis` 与 `topic_trend_analysis`） | `metrics`, `historical_comparison`, `representative_evidence` | `executive_summary`, `key_findings`, `details.important_changes`, `details.main_drivers` | 仅 Daily V2 | 未覆盖 Weekly/Monthly | 需明确与 `overall_situation_assessment` 的边界：前者专注周期增量与小样本异动，后者专注全局格局综合。 |
| 3 | `event_analysis` (`assess_event_v2.0`) | `event_analysis` (`daily/weekly/monthly_event_v1.0`) | `events`, `representative_evidence`, `counter_evidence` | `details.event_interpretations`（七维：背景/发生了什么/关键进展/媒体报道/跨国差异/可能影响/后续观察） | Daily V2；Daily/Weekly/Monthly Legacy | **存在同名冲突** | `task_type` 完全同名，仅靠 `prompt_version` 区分缓存；`load_cached_intelligence` 与 `_load_cached_v2_assessments` 读同一张表需防串读。 |
| 4 | `topic_analysis` (`assess_topic_v2.0`) | `topic_trend_analysis` (`weekly/monthly_topic_v1.0`) | `metrics(BOARD/TOPIC)`, `representative_evidence`, `events` | `details.topic_deep_dives`（Legacy 为 `topic_trends`） | Daily V2；Weekly/Monthly 用 Legacy | 字段名不统一 | Legacy 输出 `topic_trends`（含 `attention_change/stance_change/topic_structure_change`），Canonical 输出 `topic_deep_dives`，迁移需在契约层统一字段。 |
| 5 | `country_comparison` (`assess_country_v2.0`) | `cross_country_analysis` (`weekly/monthly_cross_country_v1.0`) | `metrics(COUNTRY)`, `current_articles`, `representative_evidence`, `counter_evidence` | `details.country_comparisons`（Legacy 为 `cross_country`） | Daily V2；Weekly/Monthly 用 Legacy | 字段名不统一 | Legacy 侧重同事件跨国叙事对比，Canonical 侧重国别画像；需保留 `insufficient_sample_countries` 披露。 |
| 6 | `narrative_analysis` (`assess_narrative_v2.0`) | 无独立任务（部分混在 `cross_country_analysis`） | `narratives`, `representative_evidence`, `counter_evidence` | `details.narrative_shifts`（主导/新兴/衰退/分化叙事） | 仅 Daily V2 | Weekly/Monthly 未迁移 | 依赖 `events/narratives.py` 产出的 `narratives` 证据包；若周/月报未注入该证据会退化。 |
| 7 | `sentiment_stance_analysis` (`assess_stance_v2.0`) | `stance_analysis` (`weekly/monthly_stance_v1.0`) | `metrics(GLOBAL/COUNTRY/BOARD/TOPIC)`, `representative_evidence`, `counter_evidence` | `key_findings`, `limitations`（Legacy 为 `stance_analyses` 含 `rate_vs_count_note`） | Daily V2；Weekly/Monthly 用 Legacy | 结构需对齐 | 必须保留 Legacy 的 `rate_vs_count_note`（比例变化 vs 绝对篇数变化）与 `stance_coverage_rate` 硬约束。 |
| 8 | `risk_signal_assessment` (`assess_risk_v2.0`) | 无独立任务（混在 `emerging_signals`） | `alerts`, `events`, `representative_evidence` | `key_findings`, `watch_items` | 仅 Daily V2 | Weekly/Monthly 未迁移 | 需与 `outlook_assessment` 明确分工：风险信号聚焦当期已观测异常，展望聚焦条件性推演。 |
| 9 | `outlook_assessment` (`assess_outlook_v2.0`) | `emerging_signals` (`daily/weekly/monthly_signals_v1.0`, `monthly_outlook_v1.0`) | `events`, `alerts`, `metrics`, `narratives` | `watch_items`, `details.outlook_signals` | Daily V2（`legacy_alias="emerging_signals"`）；Weekly/Monthly 用 Legacy | Daily 部分迁移；Weekly/Monthly 未迁移 | 需保持所有预测性表述使用条件语言（potential_trigger + uncertainty）。 |

## 3. 兼容与平滑迁移策略（零破坏）

1. **统一写通道，保留读兼容投影**：
   - Task 2 将 `run_assessment_task()` 升级为唯一 LLM 执行入口；移除 Weekly/Monthly 对 `runner.py:run_report_intelligence()` 的直接依赖。
   - 在输出层提供确定性适配函数（`project_canonical_to_legacy_intelligence()`），继续填充 `payload["intelligence"]["tasks"]` 中的旧键名，确保现有前端 `Reports.tsx` 与旧测试在前端升级（Task 5）前零回归。
2. **消除 `event_analysis` 同名冲突**：
   - 在 `ReportNarrativeTask` 缓存键中引入 `engine_version` 或统一升级所有 `prompt_version` 为 `v2.*`，禁止 Legacy 与 Canonical 混写同一 `(report_type, period, task_type)`。
3. **周期感知 Prompt 参数化**：
   - Canonical 的 9 个 `AssessmentTaskSpec` 当前 prompt 偏日报语境（如 `overall_situation_assessment` 写着“输出当日全局涉华态势”）。迁移时应通过 `report_type` 注入周期定位指令（Daily=当日监测与异动、Weekly=周度变化解释、Monthly=长期格局与持续性），而不是复制 27 份重复代码。
