# DATA_CONTRACTS_IMPLEMENTATION.md — Phase 2 数据契约统一实施报告

> 分支：`cursor/data-trust-batch1` | 日期：2026-11-26 | 依据：GNI Architecture & Implementation Specification V2.0（Phase 2）

## 1. 实施原则与数据库迁移结论

- **零平行系统、零新增表**：不新建平行表结构，全部复用现有 36 张 ORM 表（`Article`、`ArticleVersion`、`ArticleAnalysis`、`ArticleChinaSpan`、`ArticleRelevanceAssessment`、`StatSnapshot`、`Event`、`ArticleEventCandidate`、`EventRevision`、`NarrativeCluster`、`EventNarrativeEvidence`、`AlertEvent` 等）。
- **数据库迁移**：**无需破坏性 DDL 迁移**（0 张新增表，0 列删除）；结构化文章情报完整落库在 `ArticleAnalysis.structured_result` JSON 中（含 `article_intelligence` 规范投影与 `article_intelligence_version = "article_intel_v2.0"`），100% 兼容历史 `article_analysis_v1.0` 与旧版读取器。
- **原始文章 / 模型分析 / 人工修订三层区分**：
  - 原始文章与清洗文本版本：`Article` + `ArticleVersion`（`article_version_id` 绑定）。
  - 模型分析结果：`ArticleAnalysis` + `ArticleAnalysisMetadataContract.record_source = "model"`。
  - 人工修订预留：`ArticleAnalysisMetadataContract.record_source ∈ {"model", "human_override", "hybrid"}`、`human_reviewed_by`、`human_reviewed_at`，事件层由 `EventRevision(action ∈ {merge, split, correct, lock})` 审计追踪。

## 2. 七大逻辑数据契约状态清单

| 逻辑契约 | 实现位置 | 版本常量 | 状态 | 说明 |
|---|---|---|---|---|
| 1. `ArticleIntelligenceContract` | `src/gni/core/contracts.py` + `src/gni/analysis/service.py` | `article_intel_v2.0` | `implemented` | 覆盖 Relevance / Topics / Sentiment / Stance(`target`+`expression_owner`) / Narratives / Entities / Events / Evidence(`article_version_id`+offset+`validated`) / Quality / Metadata，已接入分析主链路落库与 Pydantic v2 校验 |
| 2. `EventIntelligenceContract` | `src/gni/core/contracts.py` + `src/gni/events/` | `event_intel_v2.0` | `implemented` | 明确 `event_time: datetime \| None`（严禁 `published_at` 替代）、7 态生命周期与 `record_source`；事件提取/聚合/合并/拆分已落地 |
| 3. `NarrativeIntelligenceContract` | `src/gni/core/contracts.py` + `src/gni/events/narratives.py` | `narrative_intel_v2.0` | `implemented` | 包含 `supporting_evidence` / `counter_evidence`、`trend_status`、`related_countries`，已接入 `cluster_narratives()` 与 `NarrativeCluster`/`EventNarrativeEvidence` 落库 |
| 4. `MetricSnapshotContract` | `src/gni/core/contracts.py` + `src/gni/metrics/v1_stats.py` | `methodology_v1.0` | `implemented` | 与 `StatSnapshotRow` / `StatSnapshot` 对齐，支持 `GLOBAL`/`COUNTRY`/`BOARD`/`TOPIC`/`SOURCE` 与独立 `sentiment_counts` |
| 5. `SignalRecordContract` | `src/gni/core/contracts.py` + `src/gni/metrics/changes.py` | `evidence_v2.0` | `implemented` | 8 类信号类型，已由 `detect_volume_change` / `detect_stance_shift` / `detect_cross_country_divergence` 实际产出 |
| 6. `EvidencePackageContract` | `src/gni/core/contracts.py` | `evidence_v2.0` | `partially_implemented` | 仅完成统一 Pydantic v2 接口契约定义；Phase 5 才会将 `reports/narrative/evidence.py` 迁移至统一证据包构建器 |
| 7. `ReportPackageContract` & `NarrativeTaskOutput` | `src/gni/core/contracts.py` + `src/gni/reports/narrative/schemas.py` | `report_package_v2.0` | `partially_implemented` | 完成接口契约定义与 `Finding.classification="Outlook"` / `supporting_metrics` / `counter_evidence` / `OutlookSignal` 兼容扩展；Phase 6 接入统一报告组装器 |

## 3. 跨层依赖守护与兼容性验证

- `tests/unit/test_imports.py::test_layer_dependency_direction` 通过 AST 静态扫描确保底层模块（`core`/`infrastructure`/`ingestion`/`processing`/`analysis`/`metrics`/`events`）不得反向导入上层（`reports`/`api`/`dashboard`）。
- 已知存量遗留耦合 `events/service.py -> gni.dashboard.data` 已列入白名单并在 `UPDATED_GAP_ANALYSIS.md` 登记待后续清理，严禁新增任何反向依赖。
- 兼容性校验：`tests/unit/test_v2_contracts_and_article_intel.py` 与既有 `test_metrics_v1_spec.py`、`test_report_narrative_layer.py` 全量通过。
