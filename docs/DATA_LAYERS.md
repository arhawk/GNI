# 数据五层架构（DATA_LAYERS）

**版本：** 0.1  
**范围：** 逻辑数据层（同一 PostgreSQL；原始大文件可后置对象存储）  
**权威对齐：** 本文件定义「新闻加工厂」数据链；与 [BLUEPRINT_V4.md](BLUEPRINT_V4.md) §14.3 系统分层、筛选 L1/L2/L3 并存，术语不得混用。

---

## 1. 术语消歧

| 名称 | 含义 |
|------|------|
| **数据五层** Data Layers | Raw → Normalized → Screening & Extraction → AI Analysis → Intelligence & Analytics |
| **系统分层** Blueprint §14.3 | Source / Ingestion / Processing / Intelligence / Storage / Application（运行时模块） |
| **筛选 L1 / L2 / L3** | 标题初筛 / 正文筛选 / 涉华片段提取（**落在数据层 Layer 3**） |

原则：**每一层产生新数据，不覆盖上一层。** 换模型/Prompt 追加分析版本；同 URL + 同正文 Hash 复用，不强制重跑 LLM。

---

## 2. 五层一览

| 层 | 名称 | 存什么 | 覆盖规则 |
|----|------|--------|----------|
| L1 | Raw Data | RSS/API/HTML 原始载荷、发现记录、抓取时间 | 追加；不改写历史 raw |
| L2 | Normalized | 统一 Article + ArticleVersion（标题/正文/时间/语言/Hash） | 可再生成新 version |
| L3 | Screening & Extraction | 标题/正文筛选、涉华片段、相关度、实体候选 | 追加历史结果 |
| L4 | AI Analysis | Sentiment / Stance / Topic / Frame / Evidence / Summary | 追加；保留 model/prompt 版本 |
| L5 | Intelligence & Analytics | Event、叙事簇、metric_runs、报告（报告表后置） | 可重算 |

```text
发现 → RAW → 标准化/去重 → 涉华筛选提取 → AI 分析 → 事件/指标/报告
```

---

## 3. 表映射（当前实现）

| 层 | 表 |
|----|-----|
| L1 | `raw_documents`, `discovered_articles`；编排：`collection_tasks`（与 `ingestion_jobs` 等双写过渡） |
| L2 | `articles`, `article_versions`；`articles.pipeline_state` |
| L3 | `article_screenings`, `article_china_spans`, `article_relevance_assessments` |
| L4 | `article_analyses`, `analysis_runs`（情感/立场等暂在 `structured_result` JSON） |
| L5 | `events*`（含 fingerprint 字段）、`article_event_candidates`、`event_metric_snapshots`、`country_china_attitude_snapshots`、`narrative_*`、`metric_runs`；指纹规范见 [EVENT_FINGERPRINT.md](EVENT_FINGERPRINT.md) |
| 治理 | `countries`, `organizations`, `sources`, `source_*` |

对象存储：`raw_documents.object_key` 预留（R2 后置）；MVP 用 `payload_text` 截断保存。

---

## 4. `pipeline_state`（文章生命周期）

权威对外状态在 `articles.pipeline_state`。兼容字段 `processing_status` / `analysis_status` / `quality_status` 仍由流水线同步。

| 状态 | 含义 |
|------|------|
| `DISCOVERED` | 已发现 URL/元数据 |
| `RAW_STORED` | 已写 raw + 晋升/写入 article 行 |
| `NORMALIZED` | 正文抽取与规范化完成（MVP 常合并进后续态） |
| `DEDUPLICATED` | 判定重复（可停在此；`exclude_from_metrics`） |
| `TITLE_SCREENED` | 标题初筛完成 |
| `FULLTEXT_SCREENED` | 正文涉华筛选完成（非涉华可停） |
| `EXTRACTION_COMPLETED` | 版本抽取完成（process 成功终点之一） |
| `ANALYSIS_COMPLETED` | AI 分析完成 |
| `EVENT_LINKED` | 已关联事件（可选推进） |
| `AVAILABLE_FOR_ANALYTICS` | 达到进指标门槛（相关度等） |

MVP：`process_article` 单次调用内可合并步进，**最终态**写入 `pipeline_state`（见 [DATA_SCHEMA.md](DATA_SCHEMA.md)）。

非涉华：停在 `FULLTEXT_SCREENED`，不进入深度分析强制路径。

---

## 5. 生命周期与复用

1. Ingest：`collection_tasks` → `raw_documents` → `discovered_articles` → upsert `articles`（`RAW_STORED`）  
2. Process：version + L1 标题筛选 → `EXTRACTION_COMPLETED` 或 `DEDUPLICATED`  
3. Analyze：L2/L3 + `article_analyses` → `ANALYSIS_COMPLETED`；相关度达标 → `AVAILABLE_FOR_ANALYTICS`  
4. Events/Metrics：读 L4/L5；事件关联可标 `EVENT_LINKED`

同 URL 再采：若正文 Hash 未变，不新建 version、不强制 `reanalyze`。

---

## 6. 后置（明确不做于本轮）

- Cloudflare R2 / GitHub Actions 调度实装  
- L4 拆成独立 sentiment/stance/topic 关系表  
- `reports` / `report_claims` / `report_evidence` 物理表  

详见 [DATABASE.md](DATABASE.md)、[ARCHITECTURE.md](ARCHITECTURE.md)、[ERD.mmd](ERD.mmd)。
