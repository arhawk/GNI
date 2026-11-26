# EVIDENCE_PACKAGE_IMPLEMENTATION.md — Phase 5.3 统一证据包实施报告

> 分支：`cursor/data-trust-batch1` | 日期：2026-11-26 | 实现位置：[src/gni/reports/narrative/evidence.py](src/gni/reports/narrative/evidence.py)

## 1. 实现概览

在既有 `prepare_evidence_bundle()` 与 `EvidenceBundle`（数据库白名单与数字防编造集合）基础上，新增统一入口 **`build_task_evidence_package()`**，输出经 Pydantic v2 验证的 **`EvidencePackageContract`**，并与 `EvidenceBundle` 配套供研判任务与三层校验器消费。

## 2. 按任务裁剪与 Batch 1–2 数据接入

`build_task_evidence_package()` **绝不向 LLM 倾倒文章全文**（单测断言 `content_original`/`content_clean` 不出现在 `current_articles` 中），而是按 `task_type` 通过 `_TASK_LIMITS` 与任务排序策略裁剪并组装以下结构化材料：

1. **确定性统计指标（`metrics`）**：来自 `v1_stats`（`GLOBAL` / `COUNTRY` / `BOARD` / `TOPIC`），保留 `metric_ref_id`、`article_count`、`positive/neutral/negative_rate`、`unclassified_count` 与 `stance_coverage_rate`。
2. **历史对比与多因素变化信号（`historical_comparison`）**：接入昨日/近 7 日基线、规则告警，以及 Phase 4 [src/gni/metrics/changes.py](src/gni/metrics/changes.py) 确定性 `detect_volume_change()` 信号（带小样本保护）。
3. **事件证据（`events`）**：来自 `Event` + `EventArticle`，严格区分 `event_time`（未知保持 `null`）与 `published_at` / `first_seen_at`，包含各国首次报道时间与跨国文章分布。
4. **叙事证据（`narratives`）**：优先读取 Phase 4 已落库的 `NarrativeCluster` + `EventNarrativeEvidence`；若尚未聚簇，则实时调用 `cluster_narratives()` 对 Phase 3 文章级 `narratives[]` 做确定性聚类（保留正反证分离）。
5. **可追溯原文证据（`representative_evidence` & `counter_evidence`）**：
   - 从 `ArticleAnalysis.structured_result["article_intelligence"]["evidence"]` 读取经 Phase 3 原文核验的片段；
   - 每条证据均携带：`evidence_id`、`article_id`、`article_version_id`、`text_span`、`start_offset`、`end_offset`、`validated`、`source_name`、`source_country`、`published_at`、`stance_label`、`expression_owner`、`related_topics`、`related_event_id`、`analysis_task`。
6. **数据覆盖与局限声明（`coverage` & `limitations`）**：自动汇总 `global_article_count`、`countries_reporting`、`sources_reporting`、`stance_coverage_rate`、`low_sample_scopes`、`quoted_actor_articles`、`is_insufficient_data`，并自动注入「引述不等于媒体立场」「多国同时报道不构成协调传播」与小样本披露。

## 3. 状态评估

- 任务级 `EvidencePackageContract` 构建与原文偏移追溯：`implemented`
- 与 `NarrativeCluster`、`metrics/changes.py` 及 `article_intelligence` 联调：`implemented`
- 跨周/跨月历史 `StatSnapshot` 深度趋势包（面向 Weekly/Monthly）：`partially_implemented`（接口已预留，待后续周报/月报批次扩展）
