# 数据 Schema 总览（DATA_SCHEMA）

**版本：** 0.9（数据五层核心表）  
**数据分层：** [DATA_LAYERS.md](DATA_LAYERS.md)  
**查询路径：** Country × Source × Topic × Target × Time；事件层见 [EVENT_INTELLIGENCE_IA.md](EVENT_INTELLIGENCE_IA.md)  
**详见：** [DATABASE.md](DATABASE.md)、[ARTICLE_ANALYSIS_SCHEMA.json](ARTICLE_ANALYSIS_SCHEMA.json)、[BLUEPRINT_V4_ADDENDUM_A1.md](BLUEPRINT_V4_ADDENDUM_A1.md)

---

## 0. 数据五层核心（本轮）

| 表 / 字段 | 用途 |
|-----------|------|
| `collection_tasks` | 跨层任务 lineage（ingest/process/analyze/backfill） |
| `raw_documents` | L1 原始载荷（截断 text + hash；`object_key` 预留） |
| `discovered_articles` | L1 发现记录；`article_id` 晋升回填 |
| `articles.pipeline_state` | 权威生命周期状态（见 DATA_LAYERS） |
| `articles.latest_raw_document_id` | 可选指针 |
| `articles.latest_article_version_id` | 可选指针 |

与 `ingestion_jobs` / `processing_jobs` / `analysis_runs` **双写过渡**。

---

## 1. MVP 既有对象

countries、organizations、sources、source_reviews、source_attribute_history、source_health、  
articles、ingestion_jobs、…

## 2. P1-B 新增

| 表 | 用途 |
|----|------|
| `article_versions` | 正文提取/清洗版本（raw 截断、clean text、hash、extracted_at） |
| `article_screenings` | 筛选运行记录（stage=title\|fulltext）；**筛选 L1/L2**；不覆盖旧结果 |
| `processing_jobs` | 处理批次 |

`articles`：`duplicate_of_article_id`、`processing_status`、`canonical_url` 等。

## 3. P1-C 新增

| 表 | 用途 |
|----|------|
| `article_relevance_assessments` | Relevance Level / Weight |
| `article_china_spans` | **筛选 L3** 涉华片段 |
| `analysis_runs` | 分析批次与预算 |
| `article_analyses` | 六维 `structured_result`（追加） |

`articles`：`analysis_status`、`fulltext_screening_label`、`china_relevance_*`、`analyzed_at`。

## 4. P1-D 新增

| 表 | 用途 |
|----|------|
| `metric_runs` | 窗口指标（研究 / 加权 / 运营） |

## 5. Event Intelligence（P1-F proto / Fingerprint MVP）

| 表 | 用途 |
|----|------|
| `events` | 唯一事件；MVP 含 `actor_key`/`action_key`/`object_key`/`event_time`/`fingerprint_hash`/`qualifiers` |
| `article_event_candidates` | 文章事件候选指纹（追加） |
| `event_metric_snapshots` | 事件级上卷指标 |
| `country_china_attitude_snapshots` | 国家对华态度汇总（地图） |
| `event_locations` / `event_participants` / `event_articles` | 地点 / 参与方 / 关联 |
| `narrative_clusters` / `event_narrative_evidence` | 叙事与证据 |

**禁止**在 `events` 上存单一「国家观点」字段。详见 [EVENT_FINGERPRINT.md](EVENT_FINGERPRINT.md)。

## 6. 分析 JSON

`article_analysis_v0.2`：`china_relevance.level` = core/substantial/secondary/incidental/none/uncertain。

## 7. pipeline_state 取值

`DISCOVERED` | `RAW_STORED` | `NORMALIZED` | `DEDUPLICATED` | `TITLE_SCREENED` | `FULLTEXT_SCREENED` | `EXTRACTION_COMPLETED` | `ANALYSIS_COMPLETED` | `EVENT_LINKED` | `AVAILABLE_FOR_ANALYTICS`
