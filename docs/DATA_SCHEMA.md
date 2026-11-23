# 数据 Schema 总览（DATA_SCHEMA）

**版本：** 0.1  
**详见：** [DATABASE.md](DATABASE.md)、[ARTICLE_ANALYSIS_SCHEMA.json](ARTICLE_ANALYSIS_SCHEMA.json)、[ERD.mmd](ERD.mmd)

---

## 1. MVP 必须对象

countries、organizations、sources、source_reviews、source_attribute_history、source_health、  
articles、article_versions、article_analyses、article_evidence、article_entities、article_topics、  
topics、topic_relations、stance_targets、taxonomy_versions、  
analysis_runs、model_versions、prompt_versions、  
metric_definitions、metric_runs、  
reports、report_claims、report_evidence、  
ingestion_jobs

## 2. Phase 2 规划（Phase 0 不建空表）

story_clusters、article_story_relations、events、event_articles、event_embeddings、  
event_relations、event_analyses、event_metrics、event_corrections

## 3. 分析 JSON 要点

见 `ARTICLE_ANALYSIS_SCHEMA.json`：强制 `schema_version`、`taxonomy_version`；立场为数组且含 `target_id`；证据含 `quote` 与定位字段。
