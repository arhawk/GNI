# GNI 数据对象与数据契约映射（DATA_MODEL_MAPPING）

> 本文件将 **V2.0 规范第 2 节**定义的 6 大逻辑数据对象逐字段映射到 `src/gni/infrastructure/models.py`（36 张 ORM 表）及 `ArticleAnalysis.structured_result` / `ReportNarrativeTask.validated_output` JSON 契约，并给出**复用优先、最小增量**的目标数据契约设计。

---

## 1. 六大逻辑对象映射总览

| V2.0 逻辑对象 | 现有物理载体（ORM 表 / JSON） | 实现状态 | 核心差距摘要 |
|---|---|---|---|
| **2.1 Article** | `articles` + `article_versions` + `raw_documents` + `discovered_articles` + `sources` | **已实现（95%）** | 具备 `id`/`title`/`content_clean`/`url`/`source_id`/`published_at`/`first_seen_at`/`language`/`content_hash`/`processing_status`/`pipeline_state`；`source_country` 通过 `sources.country_id` 关联获得；缺少跨源全局去重持久化标记 |
| **2.2 Article Intelligence** | `article_analyses.structured_result` + `article_screenings` + `article_relevance_assessments` + `article_china_spans` | **部分实现（60%）** | Relevance/Spans/Topics_v1/China_Stance/Sentiment 已落地；**缺失**独立 `expression_owner` 强制字段（V1.0 `china_stance` 未拆出）、结构化 `narratives`（仅单标签 `framing.primary`）、正文级 `entities` 与 `event_relation`、规范化 `quality` 对象 |
| **2.3 Event Intelligence** | `events` + `article_event_candidates` + `event_articles` + `event_locations` + `event_participants` + `event_metric_snapshots` + `event_revisions` | **部分实现（65%）** | Schema 完备，严守 `event_time` 不回退 `published_at`；但 `status` 仅 `proto/active/closed/locked`（缺 V2.0 演化状态枚举）、`event_locations` 实库为 0 行、缺事件级 `evidence_refs` 与自动时间线节点结构 |
| **2.4 Narrative Intelligence** | `narrative_clusters` + `event_narrative_evidence` | **仅建表、未实现（10%）** | 两张表已在 `models.py:579-600` 定义并被 `events/service.py` 与 `evidence.py` 查询，但**全仓无任何写入逻辑（0 行）**；缺跨事件全局叙事聚类、`canonical_claim`、`supporting_evidence`/`counter_evidence`、`trend_status` |
| **2.5 Metric Snapshot** | `stat_snapshots`（V1.0）+ `metric_runs`（旧 v0.4）+ `event_metric_snapshots` + `country_china_attitude_snapshots` | **已实现但双轨并存（80%）** | `stat_snapshots` 严格执行 V1.0 口径（4 板块×15 议题 + Stance Coverage + `article_ids` 溯源）；但缺 `granularity`、`comparison_value` 与 `media` 维度快照，且与旧 `metric_runs` 双轨并存 |
| **2.6 Signal Record** | `alerts` + `alert_events` + `alert_evidence` + `alert_rules`；以及 LLM `OutlookSignal` | **部分实现（45%）** | `alerts` 承载规则异常预警，`OutlookSignal` 承载 LLM 条件性展望信号，两者尚未统一为规范 `SignalRecord`（缺 `observation`/`trigger_metrics`/`alternative_explanation`/`review_status` 闭环） |

---

## 2. 逐对象字段级映射明细

### 2.1 Article（文章基础对象）

| V2.0 字段 | 现有字段与位置 | 状态 | 说明 |
|---|---|---|---|
| `article_id` | `Article.id` (`models.py:232`) | 已实现 | PortableUUID 字符串 |
| `title` / `content` | `Article.title`、`Article.content_original`、`Article.content_clean` + `ArticleVersion.content_clean` | 已实现 | 保留原始抓取 `raw_documents.payload_text` 与多版本 `article_versions`，满足不可篡改与回溯要求 |
| `url` | `Article.url`、`Article.canonical_url` | 已实现 | `(source_id, url)` 唯一约束 |
| `source_id` / `source_country` | `Article.source_id` → `Source.country_id` | 已实现 | 严格按媒体所属国家归属 |
| `published_at` / `first_seen_at` | `Article.published_at`、`Article.first_seen_at` | 已实现 | V1.0 统计严格仅使用 `published_at` |
| `language` / `content_hash` | `Article.language`、`Article.content_hash`、`Article.title_hash` | 已实现 | 同源去重通过 `duplicate_of_article_id` 与 `exclude_from_metrics` 标记 |
| `processing_status` / `created_at` | `Article.processing_status`、`Article.pipeline_state`、`Article.first_seen_at`/`updated_at` | 已实现 | `pipeline_state.py` 维护 10 阶段状态机 |

### 2.2 Article Intelligence（文章级情报对象）

现有实现分散在 4 张表 + `ArticleAnalysis.structured_result` JSON（`schema_version="article_analysis_v1.0"`）：

| V2.0 子模块 | 现有存储位置与字段 | 现状评价与具体缺口 |
|---|---|---|
| **A. Relevance** | `ArticleRelevanceAssessment`（`relevance_level`, `relevance_weight`, `content_share_estimate`, `headline_prominence`, `reasoning_summary`）+ `ArticleChinaSpan`（`paragraph_index`, `char_start`, `char_end`, `text_original`, `validation_status`） | **已较好实现**。支持正文级定位与原文切片校验（`l3_spans.py:validate_span_quote()`）。缺口：`char_start`/`char_end` 针对 `ArticleVersion.content_clean` 计算，需在 Evidence 中显式携带 `article_version_id` |
| **B. Topic** | `structured_result.topics_v1`（list[str]）+ `boards_v1`（派生）+ 旧字段 `topics.primary/secondary` | **部分实现**。已支持 4 板块×15 议题多标签且严格基于正文/spans；缺口：未在每个 topic 上附带 `relevance` 分级与独立 `evidence_refs`，且旧 `topics.primary` 仍残留在 `heuristic.py` 与 `alerts/rules.py` |
| **C. Sentiment** | `structured_result.sentiment`（`label`, `score`, `intensity`, `status`） | **部分实现**。已与 Stance 分离；缺口：DeepSeek Prompt 未强制要求 `sentiment_target`、`confidence`、`reasoning` 与 `evidence_refs` |
| **D. Stance** | V1.0：`structured_result.china_stance`（`stance_label`, `stance_confidence`, `stance_evidence`, `analysis_status`）；旧：`structured_result.stances[]`（`target_id`, `stance`, `speaker_type`） | **关键缺口（P0）**。`china_stance` 实现了 3 类 + `Unclassified` 与原文 `stance_evidence`，但**未把 `expression_owner`（`media`/`quoted_actor`/`unclear`）显式结构化为字段**（仅在 Prompt 文字中提示）；`target` 隐式绑定中国大陆而非显式字段 |
| **E. Narrative** | `structured_result.framing`（`primary`, `secondary`, `status`）+ `claims`（空列表 `[]`） | **重大缺口（P1）**。`heuristic.py:454` 将 `claims` 写死为 `[]`，`deepseek.py:187` 仅请求 `framing` 摘要；**无** `frame`/`claim`/`actor`/`target`/`attribution`（mention/quote/support/refute）/`tone`/`evidence_refs` 结构 |
| **F. Entity** | `ArticleScreening.matched_entities`（L2 字典命中）+ `structured_result.entities`（仅 Heuristic 从 L2 派生） | **部分实现（P1）**。仅覆盖中国实体字典命中，未抽取非中国关键实体（外国政府机构、政治人物、国际组织、企业）及其 `roles` |
| **G. Event** | `ArticleEventCandidate` 表（`fingerprint`, `evidence`, `confidence`, `prompt_version`） | **部分实现（P1）**。事件候选独立在 `events/extract.py` 用英文标题正则提取，未纳入文章级统一输出，且缺 `event_relation`（`new_event_candidate`/`existing_event_update`/`background_reference`/`unrelated`） |
| **H. Evidence** | `ArticleChinaSpan` + `structured_result.evidence[]` + `china_stance.stance_evidence[]` | **部分实现（P0）**。`ArticleChinaSpan` 有精确 `char_start`/`char_end`，但 DeepSeek 返回的 `stance_evidence` 仅含 `quote` 字符串，无 `evidence_id`、未做原文 offset 对齐校验 |
| **I. Quality** | `Article.quality_status` + `ArticleScreening.requires_human_review` + `structured_result.field_status` | **部分实现（P0）**。分散在多表，缺统一的 `quality` 块（`completeness`/`extraction_quality`/`classification_quality`/`needs_review`/`quality_flags`） |
| **J. Metadata** | `ArticleAnalysis` 列（`provider`, `model_name`, `prompt_version`, `schema_version`, `taxonomy_version`, `relevance_weight_version`, `token_usage`, `estimated_cost_usd`, `analysis_status`, `created_at`） | **已实现**。字段齐备，需在查询层严格隔离 `v1.0` 与历史 `v0.1` |

### 2.3 Event Intelligence（事件对象）

| V2.0 字段 | 现有字段与位置 | 状态 | 说明 |
|---|---|---|---|
| `event_id` / `canonical_title` / `description` | `Event.id`、`Event.title`、`Event.summary` | 已实现 | `id` 使用基于 `fingerprint_hash` 的确定性 UUID5 |
| `actors` / `action` / `object` / `event_type` | `Event.actor_key`、`action_key`、`object_key`、`event_type` + `EventParticipant` | 部分实现 | `actor_key` 仅单值，参与方明细存于 `event_participants`（实库 35 行） |
| `event_time` | `Event.event_time`（`models.py:465`） | 已实现 | `match.py:44` 严格仅取真实事件时间，不以 `published_at` 填充 |
| `location` | `EventLocation` + `Event.has_physical_location` | 弱实现 | `event_locations` 当前实库 0 行（`geo.py` 关键词匹配率极低） |
| `status` | `Event.status`（`proto\|active\|closed\|locked`） | 缺演化态 | 缺少 `emerging`/`ongoing`/`escalating`/`de_escalating`/`resolved`/`dormant`/`uncertain` |
| `article_ids` / `evidence_refs` / `confidence` | `EventArticle`、`Event.importance_score` | 部分实现 | 缺独立事件级 `confidence` 与关键 `evidence_refs` 列表 |
| 修订历史 | `EventRevision`（`merge\|split\|correct\|lock`） | 已建表 | 已支持 `lock_event`、`merge_events` 写审计日志；`split`/`correct` API 尚未实现 |

### 2.4 Narrative Intelligence（叙事对象）

- **现状**：`NarrativeCluster`（`id`, `event_id`, `label`, `frame_id`, `summary`, `created_at`）强制外键绑定 `event_id`（`nullable=False`），无法表达**跨事件/议题级全局叙事**；`EventNarrativeEvidence` 仅有 `quote` 而无支撑/反例区分；两张表目前均无写入器。
- **目标复用方案（不盲目推翻表结构）**：
  - Phase 2/4 优先在现有 `narrative_clusters` 上通过最小增量扩展（允许 `event_id` 可空，或新增逻辑 JSON 聚合字段/轻量扩展列 `canonical_claim`, `trend_status`, `confidence`, `related_countries`, `first_observed_at`, `last_observed_at`）并在 `event_narrative_evidence` 增加 `stance_role`（`supporting|counter`）即可承接 V2.0 叙事对象，无需新建多张冗余表。

### 2.5 Metric Snapshot（指标快照）

- **现状双轨**：
  1. `StatSnapshot`（`models.py:686`）：严格符合 V1.0 统计口径，包含 `period_start/end`, `scope_type`（`GLOBAL|COUNTRY|BOARD|TOPIC`）, `scope_id`, `article_count`, `positive/neutral/negative/unclassified_count`, `positive/neutral/negative_rate`, `stance_coverage_rate`, `methodology_version`, `taxonomy_version`, `analysis_version`, `article_ids`。
  2. `MetricRun`（`models.py:420`）：旧版 `metrics_v0.4` 多维汇总，含 `weighted_article_volume`、旧 7 议题、旧情感均值，目前仍被 Overview/Trends 和部分旧日报辅助区块使用。
- **目标统一策略**：以 `StatSnapshot` 为主指标快照基准，在 JSON 契约层补齐 `metric_run_id`、`granularity`（`daily|weekly|monthly`）、`comparison_value`（环比/历史基线）与可选 `MEDIA` 维度；`MetricRun` 收敛为辅助指标（如 `weighted_article_volume`、采集健康度）的承载体，不再向核心报告 KPI 输出冲突口径。

### 2.6 Signal Record（信号对象）

- **现状分裂**：规则侧存于 `Alert`（`category='intelligence'`, `subcategory`, `severity`, `status`, `deduplication_key`, `evidence_snapshot`）+ `AlertEvidence`；LLM 侧存于 `ReportNarrativeTask.validated_output.outlook_signals[]`（`signal`, `reasoning`, `potential_trigger`, `what_to_monitor`, `uncertainty`, `evidence_refs`）。
- **目标统一策略**：复用 `alerts` + `alert_evidence` 作为持久化信号表，在 `evidence_snapshot` 契约中标准化 `signal_type`（对齐 V2.0 8 类枚举）、`observation`、`trigger_metrics`、`alternative_explanation`、`confidence`、`review_status`，打通规则候选信号 → Assessment 研判信号 → 前端展示与人工状态流转。

---

## 3. 目标数据契约总览（Phase 2 统一标准，复用优先）

在 **Phase 2** 不大规模重建数据库表，而是先在 Pydantic v2 层统一 7 个标准逻辑契约（建议统一收敛/暴露版本常量）：

1. **`ArticleIntelligenceV2`（落库于 `ArticleAnalysis.structured_result`，`schema_version="article_analysis_v1.1"`，向后兼容 `v1.0` 读取器）**：
   - 保留 `topics_v1`、`boards_v1`、`china_stance`（确保 `v1_stats.py` 零破坏），在 `china_stance` 内补充 `target: "china_mainland"`、`expression_owner: Literal["media", "quoted_actor", "unclear"]`、`reasoning: str`；
   - 补充可选结构化块：`narratives[]`（`frame`, `claim`, `actor`, `target`, `attribution`, `tone`, `evidence_refs`, `confidence`）、`entities[]`（含 `roles`）、`event_candidates[]`（含 `event_relation`）、`evidence[]`（带 `evidence_id`, `article_version_id`, `start_offset`, `end_offset`）、`quality`（`completeness`, `needs_review`, `quality_flags`）。
2. **`EventIntelligenceV2`**：基于 `Event` + `EventArticle` + `EventParticipant` + `EventLocation` + `EventMetricSnapshot` 投影，明确 `event_time: datetime | None`（禁止用 `published_at` 填充）、`lifecycle_status`（7 态枚举）与 `timeline[]`。
3. **`NarrativeIntelligenceV2`**：基于 `NarrativeCluster` + `EventNarrativeEvidence` 投影，支持 `canonical_frame`、`canonical_claim`、`supporting_evidence[]`、`counter_evidence[]`、`trend_status`、`related_countries[]`。
4. **`MetricSnapshotV2`**：基于 `StatSnapshotRow`（`v1_stats.py`），补充 `granularity`、`comparison_value`、`sample_size_warning` 与 `calculation_version`。
5. **`EvidencePackageV2`**：基于 `EvidenceBundle`（`reports/narrative/evidence.py`），增加 `package_id`、`task_type`、`coverage`、`limitations`、`token_budget_report`，保持 `counter_evidence` 必留。
6. **`AssessmentResultV2`**：基于 `NarrativeTaskOutput`（`reports/narrative/schemas.py`），升级 `finding_type` 兼容 `Fact|Inference|Hypothesis|Outlook`（映射规范 4 类），每条 Finding 显式分离 `supporting_metrics[]` 与 `counter_evidence[]`，增加 `assessment_schema_version`。
7. **`ReportPackageV2`**：统一 Daily / Weekly / Monthly 顶层包结构（见 `REPORTING_MAPPING.md`），保持现有 `sections` 字段向后兼容并逐步收敛到统一 `sections[]` 契约。

### 跨层版本字段规范

| 版本字段 | 现状载体 | V2.0 规范要求 |
|---|---|---|
| `article_analysis_version` | `ArticleAnalysis.schema_version` (`article_analysis_v1.0`) | 升级至 `v1.1` 时保持 V1.0 读取器兼容，明确隔离 `v0.1/v0.2` 旧存量 |
| `prompt_version` | `ArticleAnalysis.prompt_version`、`ReportNarrativeTask.prompt_version` | 缓存键强制包含 `prompt_version`（已完成） |
| `model_version` | `ArticleAnalysis.model_name`、`ReportNarrativeTask.model_version` | 记录服务端返回的真实模型版本号 |
| `metric_calculation_version` | `StatSnapshot.methodology_version` (`methodology_v1.0`) | 锁定 V1.0 不可篡改 |
| `assessment_schema_version` | 缺失（隐式跟随 `NarrativeTaskOutput`） | **Phase 2 新增**显式常量（如 `assessment_v2.0`）写入 `ReportNarrativeTask` 元数据 |
| `report_schema_version` | `ReportSnapshot.schema_version`（`daily_report_schema_v4` 等） | 统一纳入 `generation_metadata` |
