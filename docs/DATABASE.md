# 数据库设计（DATABASE）

**版本：** 0.2（数据五层 + 核心 Schema）  
**引擎：** PostgreSQL 16+（Docker 建议 16）  
**向量：** pgvector 为 Phase 2 扩展  
**数据分层权威：** [DATA_LAYERS.md](DATA_LAYERS.md)  
**字段级现状：** [DATA_SCHEMA.md](DATA_SCHEMA.md)

---

## 1. 设计原则

1. 逻辑表清单 ≠ 一次建全字段；按迁移迭代  
2. **不预建**大量空表；L4 子表 / reports* 可后置  
3. 分析与筛选结果**追加版本**，禁止无记录覆盖  
4. 时间戳统一 UTC（`timestamptz`）  
5. 灵活枚举与分布可用 JSONB，外键关系保持规范化  
6. **同一 PostgreSQL** 内按五层组织；大文件可用 `object_key` 指对象存储（R2 后置）

---

## 2. 按数据五层的表说明

### 2.0 编排（跨层）

| 表 | 作用 |
|----|------|
| collection_tasks | 统一任务 lineage：`task_type`=ingest/process/analyze/backfill；status/stats/error |
| ingestion_jobs / processing_jobs / analysis_runs | **保留**；与 collection_tasks **双写过渡** |

### 2.1 Layer 1 — Raw

| 表 | 作用 |
|----|------|
| raw_documents | 原始 RSS 条目 / API / HTML 截断文本；payload_hash；object_key 预留 |
| discovered_articles | 发现的 URL/标题/时间；晋升后回填 article_id；status=discovered/promoted/rejected |

### 2.2 Layer 2 — Normalized + 来源治理

| 表 | 作用 |
|----|------|
| countries / organizations / sources / source_* | 来源治理（见 SOURCE_REGISTRY） |
| articles | 稳定文章身份；**pipeline_state**；兼容 processing_status / analysis_status / quality_status |
| article_versions | 正文提取版本（追加）；raw_html_excerpt 截断 |

唯一性：`(source_id, url)`；业务层 content_hash 去重。

### 2.3 Layer 3 — Screening & Extraction

| 表 | 作用 |
|----|------|
| article_screenings | 标题/正文筛选运行记录（stage=title\|fulltext）；不覆盖 |
| article_china_spans | 涉华片段 + 原文定位 |
| article_relevance_assessments | 相关度等级/权重 |

### 2.4 Layer 4 — AI Analysis

| 表 | 作用 |
|----|------|
| analysis_runs | 分析批次与预算 |
| article_analyses | 六维结果 `structured_result` JSON（追加行；model/prompt 版本字段） |

独立 sentiment/stance/topic/evidence 关系表：**后置**（仍见规划清单）。

### 2.5 Layer 5 — Intelligence

| 表 | 作用 |
|----|------|
| metric_runs | 窗口指标快照 |
| events / event_* / narrative_clusters / event_narrative_evidence | 事件与叙事 |
| reports* | **后置**；MVP 日报见 `data/daily_report_*.md` |

### 2.6 Taxonomy / 模型注册（规划，未全建）

taxonomy_versions、topics、stance_targets、model_versions、prompt_versions、metric_definitions — 版本字符串现写在分析/指标行上。

---

## 3. Phase 2+ 规划（节选）

story_clusters、article_story_relations、event_embeddings、event_relations、event_analyses、event_metrics、event_corrections、reports / report_claims / report_evidence  

---

## 4. ERD

见 [ERD.mmd](ERD.mmd)。

---

## 5. 迁移策略

- Alembic；生产变更必须有 Migration  
- 五层核心：`alembic/versions/20261124_0006_data_layers_core.py`（raw / discovered / collection_tasks / pipeline_state）
