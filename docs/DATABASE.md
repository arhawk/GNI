# 数据库设计（DATABASE）

**版本：** 0.1  
**引擎：** PostgreSQL 16+（Docker 建议 16）  
**向量：** pgvector 为 Phase 2 扩展，Phase 0/1 MVP 表可不启用  

---

## 1. 设计原则

1. 逻辑表清单 ≠ 一次建全字段；Phase 1 按迁移迭代  
2. **不预建**大量 Phase 2 空表  
3. 分析与指标结果追加版本，禁止无记录覆盖  
4. 时间戳统一 UTC（`timestamptz`）  
5. 灵活枚举与分布可用 JSONB，但外键关系保持规范化  

---

## 2. MVP 表说明

### 2.1 来源治理

| 表 | 作用 |
|----|------|
| countries | id, code, name |
| organizations | id, country_id, name, organization_type, ownership_type, government_control_level |
| sources | 见 SOURCE_REGISTRY 字段；config JSONB |
| source_reviews | source_id, reviewer, decision, notes, reviewed_at |
| source_attribute_history | source_id, field, old_value, new_value, reason, changed_at, changed_by |
| source_health | source_id PK, last_success_at, last_failure_at, success_rate, error_message, updated_at |

### 2.2 文章

| 表 | 作用 |
|----|------|
| articles | source_id, title, content_original, content_clean, language, published_at, first_seen_at, updated_at, url, canonical_url, content_hash, title_hash, quality_status, source_timezone, time_precision |
| article_versions | article_id, title, content, version, captured_at |
| article_entities | article_id, entity_text, entity_type, normalized_id, confidence, analysis_id |
| article_topics | article_id, topic_id, role (primary/secondary), confidence, analysis_id |

唯一性建议：`(source_id, url)` 与/或 `content_hash` 在业务层去重。

### 2.3 Taxonomy

| 表 | 作用 |
|----|------|
| taxonomy_versions | version, effective_from, notes |
| topics | topic_id, parent_id, labels JSONB, status, taxonomy_version |
| topic_relations | parent/child 或 related |
| stance_targets | target_id, labels JSONB, status, taxonomy_version |

### 2.4 分析

| 表 | 作用 |
|----|------|
| model_versions | name, version, provider, meta |
| prompt_versions | name, version, content_hash, meta |
| analysis_runs | task_type, model, prompt_version, status, cost, duration, created_at |
| article_analyses | article_id, analysis_version, model_*, prompt_version, schema_version, taxonomy_version, sentiment, stance JSONB, framing JSONB, confidence, structured_result JSONB, token_usage, status, analyzed_at |
| article_evidence | id, analysis_id, article_id, field_path, quote, start_offset, end_offset, evidence_type, confidence |

### 2.5 指标与报告

| 表 | 作用 |
|----|------|
| metric_definitions | key, version, formula_doc_ref, meta |
| metric_runs | definition_version, window, timezone, scopes, numerator, denominator, excluded_count, missing_count, deduplication_method, value JSONB, computed_at |
| reports | type, period, timezone, scopes, content, versions, created_at |
| report_claims | report_id, claim_type, text, validation_status |
| report_evidence | report_id, claim_id, article_id, evidence_id, metric_run_id, source_id, evidence_type |

### 2.6 作业

| 表 | 作用 |
|----|------|
| ingestion_jobs | source_id, status, started_at, finished_at, error, stats JSONB |

---

## 3. Phase 2 表（仅规划）

story_clusters、article_story_relations、events、event_articles、event_embeddings、event_relations、event_analyses、event_metrics、event_corrections  

`event_embeddings`：多代表性向量（representation_type + 可选 country/topic/source/article），**不为每国硬编码列**。

---

## 4. ERD

见 [ERD.mmd](ERD.mmd)（Mermaid）。

---

## 5. 迁移策略

- 使用 Alembic（Phase 1 引入；Phase 0 骨架可先占位 `migrations/`）  
- 所有生产库变更必须有 Migration  
