# 数据 Schema 总览（DATA_SCHEMA）

**版本：** 0.5（P1-B + Addendum A1）  
**查询路径：** Country × Source × Topic × Target × Time  
**详见：** [DATABASE.md](DATABASE.md)、[ARTICLE_ANALYSIS_SCHEMA.json](ARTICLE_ANALYSIS_SCHEMA.json)、[BLUEPRINT_V4_ADDENDUM_A1.md](BLUEPRINT_V4_ADDENDUM_A1.md)

---

## 1. MVP 既有对象

countries、organizations、sources、source_reviews、source_attribute_history、source_health、  
articles、ingestion_jobs、…

## 2. P1-B 新增

| 表 | 用途 |
|----|------|
| `article_versions` | 正文提取/清洗版本（raw 截断、clean text、hash、extracted_at） |
| `article_screenings` | L1（及后续 L2）筛选运行记录；不覆盖旧结果 |

`articles` 扩展字段：`duplicate_of_article_id`、`processing_status`、`canonical_url` 规范化后写回。

## 3. P1-C 预告（本轮不建强制依赖）

`article_relevance_assessments`、`article_china_spans`、`china_entity_dictionary`（文件版词典先用 YAML）、`screening_reviews`

## 4. 分析 JSON

`article_analysis_v0.2`：`china_relevance.level` = core/substantial/secondary/incidental/none/uncertain。
