# 数据 Schema 总览（DATA_SCHEMA）

**版本：** 0.4（对齐 V4；文档级，不自动触发 Migration）  
**查询路径：** Country × Source × Topic × Target × Time  
**详见：** [DATABASE.md](DATABASE.md)、[ARTICLE_ANALYSIS_SCHEMA.json](ARTICLE_ANALYSIS_SCHEMA.json)、[ERD.mmd](ERD.mmd)、[BLUEPRINT_V4.md](BLUEPRINT_V4.md)

---

## 1. MVP 必须对象（既有）

countries、organizations、sources、source_reviews、source_attribute_history、source_health、  
articles、article_versions、article_analyses、article_evidence、article_entities、article_topics、  
topics、topic_relations、stance_targets、taxonomy_versions、  
analysis_runs、model_versions、prompt_versions、  
metric_definitions、metric_runs、  
reports、report_claims、report_evidence、  
ingestion_jobs

## 2. V4 增补（业务实体清单；可归并建表）

| 组 | 实体 | 阶段 |
|----|------|------|
| 相关度 | article_relevance_assessments、relevance_weight_versions、可选 article_segments | P1-C |
| 情感/立场 | article_sentiments、article_stances、sentiment_scale_versions | P1-C |
| 框架/主张 | article_frames、article_claims、article_analysis_feedback | P1-C |
| 监测 | news_candidates、news_candidate_articles | P1-F |
| 预警 | alert_rules、alerts、alert_feedback | P1-F |
| 编排（可选） | agent_tasks、agent_tool_calls、monitoring_runs | P1 轻量 / P3 深化 |
| 事件 | events、event_articles… | **Phase 2** |

## 3. Phase 2 规划（Phase 0/1 不建空表强依赖）

story_clusters、article_story_relations、events、event_articles、event_embeddings、  
event_relations、event_analyses、event_metrics、event_corrections

## 4. 分析 JSON 要点

见 `ARTICLE_ANALYSIS_SCHEMA.json`（`article_analysis_v0.2`）：强制 `schema_version`、`taxonomy_version`、`china_relevance.level` / `weight`；立场数组含 `target_id`；证据含 `quote` 与定位；可选 `sentiment.score`、`claims`。
