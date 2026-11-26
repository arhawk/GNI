# REPORT_PACKAGE_SCHEMA.md — 统一 Report Package 契约说明

> 定义位置：[src/gni/core/contracts.py](src/gni/core/contracts.py) | 版本常量：`REPORT_PACKAGE_VERSION = "report_package_v2.0"`

## 1. `ReportPackageContract` 顶层字段

| 字段 | 类型 | 必填 | 语义说明 |
|---|---|---|---|
| `report_id` | `str` | 是 | 规范报告标识，例如 `daily:2026-11-26` |
| `report_type` | `"daily" \| "weekly" \| "monthly"` | 是 | 报告周期类型（本批次 Daily 已全量落地，Weekly/Monthly 为预留接口） |
| `period` | `dict[str, Any]` | 否 | 周期标签与时区信息 |
| `period_start` | `str \| None` | 否 | 统计窗口起点（ISO-8601 UTC，按 `published_at`） |
| `period_end` | `str \| None` | 否 | 统计窗口终点（左闭右开 `[start, end)`） |
| `generated_at` | `str \| None` | 否 | 报告包生成时间（ISO-8601 UTC） |
| `metric_run_id` | `str \| None` | 否 | 关联统计批次 ID（可选） |
| `metric_snapshot_refs` | `list[str]` | 否 | 引用的确定性指标 ID（如 `metric:GLOBAL:ALL`、`metric:COUNTRY:US`、`metric:TOPIC:...`） |
| `assessment_refs` | `list[dict]` | 否 | 参与本报告的研判任务摘要引用（`task_type`/`status`/`prompt_version`/`model_version`/`evidence_package_id`） |
| `assessment_results` | `list[dict]` | 否 | 完整的 `AssessmentResultContract` 列表 |
| `sections` | `list[ReportSectionContract]` | 否 | 有序报告章节（Daily 固定 6 章 + `appendix` 共 7 个 section） |
| `evidence_refs` | `list[dict]` | 否 | 报告级去重证据引用集合（文章、事件、指标） |
| `methodology` | `dict[str, Any]` | 否 | 锁定 V1.0 统计口径声明（`methodology_version`、`taxonomy_version`、`core_kpi`、`time_basis_articles`、`time_basis_events`、`country_attribution`、`stance_denominator`） |
| `coverage` | `dict[str, Any]` | 否 | 当期文章量、报道国家/信源数、立场覆盖率、小样本维度清单 |
| `limitations` | `list[str]` | 否 | 报告级数据覆盖与方法论局限声明 |
| `generation_status` | `"completed" \| "partial" \| "needs_review" \| "rule_only" \| "insufficient_data" \| "failed"` | 否 | 报告生成整体状态 |
| `validation_status` | `"passed" \| "needs_review" \| "failed"` | 否 | `validate_report_package()` 确定性校验状态 |
| `validation_notes` | `list[str]` | 否 | 校验提示或错误编码（如 `missing_chapters`、`metric_mismatch`、`ungrounded_fact_findings`） |
| `generation_metadata` | `dict[str, Any]` | 否 | 包含 `report_schema_version`、`generator`、`evidence_hash` |

## 2. `ReportSectionContract` 章节字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `section_id` | `str` | 稳定章节 ID（如 `chapter_1_executive_judgment` ... `appendix`） |
| `title` | `str` | 章节标题 |
| `source_kind` | `"llm_assessment" \| "deterministic_metrics" \| "hybrid"` | 明确标注章节中确定性程序与 LLM 的职责边界 |
| `summary` | `str` | 章节主摘要 |
| `findings` | `list[dict]` | 章节发现条目（保留 `classification`、`evidence_refs`、`confidence`） |
| `evidence_refs` | `list[dict]` | 章节级可追溯证据引用 |
| `metrics` | `list[dict]` | 章节级确定性统计数据 |
| `visualizations` | `list[dict]` | 面向前端图表的结构化数据载荷 |
| `limitations` | `list[str]` | 章节局限声明 |
| `assessment_task_types` | `list[str]` | 为该章节供稿的研判 `task_type` 列表 |
| `status` | `"completed" \| "partial" \| "needs_review" \| "rule_only" \| "insufficient_data" \| "failed"` | 章节独立状态，支持局部降级 |
