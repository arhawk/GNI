# 数据 Schema 总览（DATA_SCHEMA）

**版本：** 0.8（Event Intelligence 预留 + P1-F proto-Event）  
**查询路径：** Country × Source × Topic × Target × Time；事件层见 [EVENT_INTELLIGENCE_IA.md](EVENT_INTELLIGENCE_IA.md)  
**详见：** [DATABASE.md](DATABASE.md)、[ARTICLE_ANALYSIS_SCHEMA.json](ARTICLE_ANALYSIS_SCHEMA.json)、[BLUEPRINT_V4_ADDENDUM_A1.md](BLUEPRINT_V4_ADDENDUM_A1.md)

---

## 1. MVP 既有对象

countries、organizations、sources、source_reviews、source_attribute_history、source_health、  
articles、ingestion_jobs、…

## 2. P1-B 新增

| 表 | 用途 |
|----|------|
| `article_versions` | 正文提取/清洗版本（raw 截断、clean text、hash、extracted_at） |
| `article_screenings` | L1 / L2 筛选运行记录；不覆盖旧结果 |

`articles` 扩展字段：`duplicate_of_article_id`、`processing_status`、`canonical_url` 规范化后写回。

## 3. P1-C 新增

| 表 | 用途 |
|----|------|
| `article_relevance_assessments` | Relevance Level / Weight 与特征 |
| `article_china_spans` | L3 涉华片段 + 原文定位 / validation_status |
| `analysis_runs` | 分析批次与预算统计 |
| `article_analyses` | 六维结构化结果（`structured_result`） |

`articles` 扩展：`analysis_status`、`fulltext_screening_label`、`china_relevance_level`、`china_relevance_weight`、`analyzed_at`。  
实体词典仍为 YAML（`configs/china_entity_dictionary_v0.1.yaml`）。

## 4. P1-D 新增

| 表 | 用途 |
|----|------|
| `metric_runs` | 窗口/范围/版本 + `results`（研究核心 / 加权 / 运营；raw+weighted 双视图） |

## 5. Event Intelligence（P1-F proto / Phase 2 完善）

| 表 | 用途 |
|----|------|
| `events` | 唯一事件（proto 或正式）；可选 `parent_event_id` |
| `event_locations` | 分类型地点（可无坐标） |
| `event_participants` | 参与方 |
| `event_articles` | 事件↔文章 |
| `narrative_clusters` | 事件内叙事主题（非国家一对一） |
| `event_narrative_evidence` | 叙事↔文章/证据 |

**禁止**在 `events` 上存单一「国家观点」字段。

## 6. 分析 JSON

`article_analysis_v0.2`：`china_relevance.level` = core/substantial/secondary/incidental/none/uncertain。
