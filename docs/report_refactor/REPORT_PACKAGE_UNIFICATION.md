# Report Package 与 Assessment Result 契约统一方案

> 依据：`src/gni/core/contracts.py`（`AssessmentResultContract`, `ReportPackageContract`, `ReportSectionContract`）、`src/gni/reports/daily_package.py`、`web/src/api.ts`

## 1. 当前契约碎片化现状

1. **Daily**：同时返回两套结构：
   - 顶层 `sections`（V4 统计明细）+ `intelligence.tasks`（Legacy 3 任务）
   - 顶层 `report_package`（`ReportPackageContract`，6 章 + 附录，支持 JSON/Markdown 导出）
2. **Weekly / Monthly**：仅返回 `sections` + `intelligence.tasks`（Legacy 6 任务），**没有** `report_package` 字段，也**没有**统一章节契约和 Markdown 导出端点。
3. **证据链结构不均**：`AssessmentResultContract` 已将 `observations`（Fact）、`interpretations`（Inference）、`hypotheses`（Hypothesis/Outlook）、`evidence_refs`、`limitations`、`watch_items` 显式分离；但 Legacy `NarrativeTaskOutput` 将三类混在 `findings` 列表中，且缺少强制的 `counter_evidence` 槽位。

## 2. 统一 `AssessmentResultContract` 建议（最小增量演进）

保持 `src/gni/core/contracts.py:458` 现有字段向后兼容，补充以下元信息与治理字段：
- `report_type: Literal["daily", "weekly", "monthly"]`
- `period: str`
- `evidence_hash: str`
- `prompt_version: str`、`model_version: str | None`、`methodology_version: str`、`taxonomy_version: str`
- `counter_evidence: list[dict[str, Any]]`（将反证从 `findings` 内部提升为显式一等字段，便于校验器检查）
- `validation_summary: dict[str, Any]`（记录三层校验结果，支撑 `needs_review` 溯源）

## 3. 统一 `ReportPackageContract`（扩展至 Weekly / Monthly）

所有三类报告统一产出 `report_package: ReportPackageContract`，并按报告定位定义章节模板：

| 报告类型 | 统一章节 ID 规范 | 确定性图表/表格数据槽位 |
|---|---|---|
| **Daily** | `chapter_1_executive_judgment` ～ `chapter_6_outlook_watchlist` + `appendix`（沿用 `daily_package.py:41-49`） | KPI 条（Article Count / 昨日 / 环比 / 国家数 / 重点事件数）、V1.0 立场矩阵、重点事件风险表 |
| **Weekly** | `weekly_1_executive_summary`、`weekly_2_trend_series`、`weekly_3_event_evolution`、`weekly_4_topic_trends`、`weekly_5_cross_country`、`weekly_6_stance_changes`、`weekly_7_signals_outlook` | 近 4 周文章级趋势图、15 议题增量表（量变/立场变分离）、事件周度演化表、V1.0 立场矩阵 |
| **Monthly** | `monthly_1_strategic_assessment`、`monthly_2_historical_series`、`monthly_3_event_retrospective`、`monthly_4_topic_structure`、`monthly_5_country_narrative`、`monthly_6_long_term_stance`、`monthly_7_signals_outlook` | 近 6 个月文章级趋势图（显式标注不完整月）、国别媒体画像表、叙事格局表、V1.0 立场矩阵 |

## 4. 向后兼容策略

- **API 兼容**：`GET /api/reports/{daily|weekly|monthly}` 保留现有 `sections` 与 `intelligence` 字段，新增/完善 `report_package` 字段；新增 `GET /api/reports/{weekly|monthly}/package?format=json|markdown`。
- **前端渐进切换**：Task 5 前端逐步改为直接消费 `report_package.sections` 与确定性 `charts` 数据，彻底清理 `Reports.tsx` 中针对 Daily 与 PeriodBrief 的重复适配代码。
- **统计口径不变**：`ReportPackageContract` 中所有数字、比例、覆盖率均由确定性程序写入 `section.metrics` / `section.charts`，LLM 不得改写。
