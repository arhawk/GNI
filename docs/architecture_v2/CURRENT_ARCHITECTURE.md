# GNI 当前系统架构审查（CURRENT_ARCHITECTURE）

> **审查基线**：Git 分支 `cursor/data-trust-batch1`，最新提交 `64222ba`（`fix(reports): align report intelligence pipeline, evidence bundle, validator, and UI`）。  
> **审查原则**：全部结论均直接提取自真实源码、ORM 定义与本地 PostgreSQL 实例（`postgresql+psycopg://gni:gni@localhost:5432/gni`），不依据历史文档推断。

---

## 1. 仓库形态与技术栈总览

GNI 当前是一个**模块化单体（Modular Monolith）**全栈应用：

- **后端**：Python + SQLAlchemy 2.0 + FastAPI + Pydantic v2 + httpx + PyYAML，位于 `src/gni/`（共 71 个 `.py` 文件），CLI 入口 `src/gni/cli.py`，API 入口 `src/gni/api/app.py`。
- **存储**：PostgreSQL（开发/测试兼容 SQLite，通过 `PortableUUID` / `PortableJSON` 适配），共 **36 张 ORM 表**定义于 `src/gni/infrastructure/models.py`；可选 Meilisearch 全文索引（`src/gni/search/meili.py`，不可用时降级到 PostgreSQL `ILIKE`）。
- **LLM 接入**：`src/gni/analysis/deepseek.py`（`DeepSeekLLMProvider` 继承 `BaseLLMProvider`），默认模型 `deepseek-chat`，通过 `GNI_LLM_API_KEY` 配置；用于文章级分析与报告级情报研判。
- **前端**：React + TypeScript + Vite + MapLibre GL，位于 `web/src/`（共 30 个 `.ts/.tsx` 文件），通过 `web/src/api.ts` 调用 FastAPI `/api/*`。
- **测试**：`tests/` 共 27 个测试文件（25 个 `tests/unit/`、1 个 `tests/integration/`、1 个 `tests/e2e/` Playwright 端到端测试）。当前单元套件 109 passed（`test_editorial_focus.py` 存在 2 个与 `sources.yaml` 扩源相关的既有失败）。

---

## 2. 实际目录与六逻辑层映射

| 目录 | 文件数 | 实际承担的逻辑层职责 | 关键入口文件与函数 |
|---|---:|---|---|
| `src/gni/core/` | 3 | 配置（`Settings`）、日志 | `config.py:get_settings()` |
| `src/gni/infrastructure/` | 3 | 36 张 ORM 模型、DB 会话、文章生命周期状态机 | `models.py`、`db.py:session_scope()`、`pipeline_state.py:set_pipeline_state()` |
| `src/gni/sources/` | 3 | 国家/机构/媒体种子导入与编辑聚焦规则 | `seed.py:seed_sources()`、`editorial_focus.py` |
| `src/gni/ingestion/` | 4 | **Layer 1 数据采集**：RSS 拉取、原始文档留存、发现记录、文章 Upsert、源健康追踪 | `service.py:run_ingestion()`、`upsert_article()`、`rss_adapter.py:RssAdapter` |
| `src/gni/processing/` | 7 | **Layer 1 清洗与初筛**：URL/正文规范化、HTML 抓取与正文提取、语言检测、同源去重、L1 标题规则初筛 | `service.py:run_processing()`、`process_article()`、`title_l1.py:screen_title()` |
| `src/gni/analysis/` | 10 | **Layer 2 文章级情报处理**：L2 全文规则筛查、L3 涉华段落提取、相关性定级与权重、DeepSeek/Heuristic 六维结构化分析、立场读取与预算守卫 | `service.py:analyze_article()`、`l2_fulltext.py:screen_fulltext()`、`l3_spans.py:extract_china_spans()`、`relevance.py:assess_relevance()`、`deepseek.py:DeepSeekLLMProvider`、`heuristic.py:build_structured_analysis()`、`stance_util.py`、`budget.py` |
| `src/gni/events/` | 7 | **Layer 3b 事件聚合**：事件指纹候选提取、贪心聚类、地理打点、事件/国家态度 Rollup、人工锁定/合并 | `extract.py:extract_for_articles()`、`fingerprint.py:resolve_relation()`、`match.py:cluster_fingerprints()`、`rollup.py:rollup_event_metrics()`、`service.py:rebuild_proto_events()`、`list_events()` |
| `src/gni/metrics/` | 6 | **Layer 3a 确定性统计监测**：V1.0 统计快照引擎（4 板块×15 议题 + 3 类立场 + Unclassified）、旧版多维指标计算（`metrics_v0.4`） | `v1_stats.py:compute_v1_stat_snapshots()`、`service.py:run_v1_stat_snapshots()`、`run_metrics()`、`compute.py:compute_metrics()`、`taxonomy_v1.py` |
| `src/gni/alerts/` | 3 | **Layer 3 规则信号/预警**：5 类情报异常规则 + 5 类系统运维告警、状态流转 | `rules.py:generate_intelligence_alerts()`、`generate_system_alerts()`、`service.py:run_alert_engine()` |
| `src/gni/reports/narrative/` | 6 | **Layer 4 研判引擎（当前挂在 `reports/` 下）**：证据包构建、任务 Prompt 注册、任务编排与缓存、Pydantic Schema、3-Layer 校验器 | `evidence.py:prepare_evidence_bundle()`、`prompts.py:list_report_tasks()`、`runner.py:run_report_intelligence()`、`schemas.py:NarrativeTaskOutput`、`validator.py:validate_task_output()` |
| `src/gni/reports/` | 7 | **Layer 5 报告引擎**：日报 v4、周报 v1、月报 v1、顶层报告校验、风险/板块关键词标注、旧版润色 | `daily.py:build_daily_report()`、`weekly.py:build_weekly_report()`、`monthly.py:build_monthly_report()`、`validate.py`、`risk_tagging.py`、`polish.py` |
| `src/gni/dashboard/` & `src/gni/search/` & `src/gni/api/` | 7 | **Layer 6 API 与检索**：FastAPI 路由、Dashboard 聚合读模型、全文检索 | `api/app.py`、`dashboard/pages_api.py`、`dashboard/data.py`、`search/service.py` |
| `web/src/` | 30 | **Layer 6 前端展示**：总览地图、事件页、国家页、趋势页、预警页、报告页、系统页、叙事研判组件与 5 类可复用表格 | `pages/Reports.tsx`、`components/narrative/*`、`components/tables/*`、`api.ts` |

---

## 3. 单篇文章端到端数据流（从采集到报告展示）

```mermaid
flowchart LR
    RSS["RSS Feed\nrss_adapter.py"] --> Ingest["run_ingestion()\ningestion/service.py"]
    Ingest --> RawDB["raw_documents\ndiscovered_articles\narticles(RAW_STORED)"]
    RawDB --> Proc["process_article()\nprocessing/service.py"]
    Proc --> CleanDB["article_versions\narticle_screenings(title)\narticles(DEDUPLICATED)"]
    CleanDB --> Analyze["analyze_article()\nanalysis/service.py"]
    Analyze --> IntelDB["article_screenings(fulltext)\narticle_china_spans\narticle_relevance_assessments\narticle_analyses"]
    IntelDB --> V1Stats["run_v1_stat_snapshots()\nmetrics/service.py"]
    IntelDB --> EvPipe["rebuild_proto_events()\nevents/service.py"]
    IntelDB --> AlertPipe["run_alert_engine()\nalerts/service.py"]
    V1Stats --> RepBuild["build_daily/weekly/monthly_report()\nreports/*.py"]
    EvPipe --> RepBuild
    AlertPipe --> RepBuild
    RepBuild --> EvBundle["prepare_evidence_bundle()\nreports/narrative/evidence.py"]
    EvBundle --> LLMRunner["run_report_intelligence()\nreports/narrative/runner.py"]
    LLMRunner --> Val3["validate_task_output()\nreports/narrative/validator.py"]
    Val3 --> API["FastAPI /api/reports/*\napi/app.py"]
    API --> UI["Reports.tsx + narrative/*\nweb/src/"]
```

逐步链路说明：

1. **采集（`gni ingest run`）**：`src/gni/ingestion/service.py:run_ingestion()` 通过 `RssAdapter` 拉取活跃源，append-only 写入 `raw_documents`，写入 `discovered_articles`，按 `(source_id, url)` 去重 Upsert `articles`（状态 `RAW_STORED`），更新 `source_health`、`ingestion_jobs`、`collection_tasks`。
2. **清洗与 L1 初筛（`gni process run`）**：`src/gni/processing/service.py:process_article()` 规范化 URL，调用 `title_l1.py:screen_title()` 写入 `article_screenings(stage='title')`，抓取/提取正文生成 `article_versions` 并更新 `articles.content_clean`，计算 `content_hash`/`title_hash` 并执行同源去重（重复项置 `exclude_from_metrics=True` 与 `duplicate_of_article_id`），语言检测后推进至 `DEDUPLICATED`。
3. **文章级情报分析（`gni analyze run`）**：`src/gni/analysis/service.py:analyze_article()` 顺序执行：
   - L2 全文规则筛查 `screen_fulltext()` → `article_screenings(stage='fulltext')`；
   - L3 段落提取 `extract_china_spans()` → `article_china_spans`（含 `paragraph_index`、`char_start`/`char_end` 与 `validation_status`）；
   - 相关性定级 `assess_relevance()` → `article_relevance_assessments`（`core`/`substantial`/`secondary`/`incidental`/`none`/`uncertain` 及权重）；
   - 若 L2 为 `not_china_related`，由门控写入 `provider='gate'`、`analysis_status='skipped_not_china'` 并短路；
   - 否则调用 `analyze_with_fallback()`（优先 `DeepSeekLLMProvider.analyze()`，无 Key/超预算/异常时降级 `heuristic.py:build_structured_analysis()`）写入 `article_analyses.structured_result`，合格文章推进至 `AVAILABLE_FOR_ANALYTICS`。
4. **监测统计、事件聚类与预警**：
   - **V1.0 统计**：`metrics/service.py:run_v1_stat_snapshots()` 调用纯确定性函数 `v1_stats.py:compute_v1_stat_snapshots()`，按 `published_at`、去重规则（`canonical_url` / `content_hash` / `title_hash`）、4 板块×15 议题、3 类立场+`Unclassified` 计算并可选落库 `stat_snapshots`。
   - **旧版指标**：`metrics/service.py:run_metrics()` 仍为总览/趋势/部分旧日报区块提供 `metric_runs`（`metrics_v0.4`）。
   - **事件聚合**：`events/service.py:rebuild_proto_events()` 执行 `extract_for_articles()`（正则+规则提取 `ArticleEventCandidate`）→ `cluster_fingerprints()`（规则+可选 LLM 判断 `SAME_EVENT`）→ Upsert `events`/`event_articles`/`event_participants`/`event_locations` → `rollup_event_metrics()` & `rollup_country_china_attitude()`。
   - **预警规则**：`alerts/service.py:run_alert_engine()` 运行 `alerts/rules.py` 中 5 类情报异常与 5 类系统告警，Upsert `alerts`/`alert_events`/`alert_evidence`。
5. **报告构建与 LLM 研判**：
   - `build_daily_report()` / `build_weekly_report()` / `build_monthly_report()` 先装配全部确定性统计、事件、预警与数据覆盖字段，写入 `report_snapshots`。
   - **读取路径**（`GET /api/reports/{daily|weekly|monthly}`）：调用 `load_cached_intelligence()` 读取已缓存的 `report_narrative_tasks` 挂载到 `payload["intelligence"]`，不阻塞触发 LLM。
   - **触发路径**（`POST /api/reports/{daily|weekly|monthly}/analyze`）：调用 `run_report_intelligence()` 构建 `EvidenceBundle`，逐任务构造结构化瘦身后的 Prompt 调用 `DeepSeekLLMProvider.generate_json()`，经 `validate_task_output()` 3 层校验后缓存至 `report_narrative_tasks`，并执行顶层 `validate_*_report()`。
6. **前端消费与溯源**：
   - `web/src/pages/Reports.tsx` 请求 `/api/reports/{type}` 渲染报告，通过 `IntelligenceHeader`、`EventInterpretationCards`、`TopicTrendAnalysisBlock`、`CrossCountryAnalysisBlock`、`StanceAnalysisBlock`、`OutlookSignalsPanel` 呈现 LLM 研判；点击 `EvidenceChips` 时调用 `POST /api/articles/trace` 下钻展示代表文章标题、发布时间、国家、立场标签与原文 `stance_evidence`。

---

## 4. 确定性程序 vs LLM 职责现状

| 阶段 | 确定性程序实际承担 | LLM（DeepSeek）实际承担 | 风险/越界点 |
|---|---|---|---|
| 采集与清洗 | 100%（RSS、HTML 抽取、去重、L1 标题规则） | 无 | 同源去重未做跨源去重；`v1_stats` 额外做了窗口内全局 URL/Hash 去重 |
| 文章级分析 | L2 全文规则、L3 段落定位、相关性定级/权重、Heuristic 兜底 | 议题（`topics_v1`）、对华立场（`china_stance`）、情感、传统 `stances`/`framing`、摘要 | DeepSeek `analyze()` 未要求提取结构化 `narratives`、`entities`、`event_candidates` 或 `expression_owner`；且 `v0.1` 存量占 84.8% |
| 监测与聚合 | 100% 指标计算（`v1_stats.py`、`compute.py`）、Rollup、规则预警 | 仅 `events/fingerprint.py:resolve_relation()` 可选调用 LLM 判定边界事件归属 | `narrative_clusters` / `event_narrative_evidence` 表存在但**无任何写入代码**（0 行） |
| 报告研判 | `prepare_evidence_bundle()` 选文/反例/时间线/历史序列、3-Layer Validator | 6 类任务（日报 3 任务、周/月报 6 任务）结构化研判 JSON | 研判模块目前嵌套在 `src/gni/reports/narrative/`，与报告层未做包级解耦 |
| 报告组装与展示 | 统计表、时间窗、覆盖率、顶层校验、Markdown 渲染 | 挂载 `intelligence.tasks` 到正文；旧 `polish=True` 仍并存于日报 | 周/月报部分旧规则块与 V1.0 并存；`MetricRun` 与 `StatSnapshot` 双轨并存 |

---

## 5. 本地数据库实测状态与运维机制

在当前本地 PostgreSQL（`2026-11-26` 实测）中，36 张表的实际数据分布如下：

- **源与采集**：`countries=5`、`organizations=36`、`sources=50`、`source_health=50`、`raw_documents=1152`、`discovered_articles=1102`、`articles=1799`、`article_versions=895`。
- **文章分析**：`article_screenings=1575`、`article_china_spans=1429`、`article_relevance_assessments=680`、`article_analyses=676`、`analysis_runs=136`。
  - 其中 `prompt_version` 分布：`deepseek_analyze_v0.1=310`（45.9%）、`heuristic_v0.1=151`（22.3%）、`l2_gate_v1=112`（16.6%）、`deepseek_analyze_v1.0=89`（13.2%）、`heuristic_v1.0=14`（2.1%）。**非 V1.0 历史分析占比达 84.8%（573/676）**，在严格 V1.0 统计下全部降为 `Unclassified`。
  - 来源类型分布：`public_service=352`（52.1%）、`state_controlled=208`（30.8%）、`gov_comms=116`（17.2%）。
- **事件、叙事与统计**：`article_event_candidates=347`、`events=32`、`event_articles=32`、`event_participants=35`、`event_metric_snapshots=32`、`country_china_attitude_snapshots=5`、`metric_runs=42`、`stat_snapshots=50`。
  - **空表警示**：`event_locations=0`、`narrative_clusters=0`、`event_narrative_evidence=0`、`event_revisions=0`、`alert_rules=0`、`source_attribute_history=0`。
- **报告与任务缓存**：`report_snapshots=3`、`report_narrative_tasks=18`。
- **预算与缓存机制**：
  - `src/gni/analysis/budget.py:snapshot_budget()` 统计当日 `ArticleAnalysis` 篇数、`AnalysisRun.estimated_cost_usd` 与 `ReportNarrativeTask.estimated_cost_usd`；报告研判通过 `llm_allowed(..., ignore_article_limit=True)` 避开文章日限额误杀。
  - `ReportNarrativeTask` 通过 `(report_type, period, task_type, prompt_version)` 唯一约束做任务级缓存，并利用 `evidence_hash` 判断缓存是否 `stale`。
  - **版本管理现状**：已有 `prompt_version`、`schema_version`、`taxonomy_version`、`methodology_version`、`relevance_weight_version`、`metric_definition_version`，但缺少统一的 `assessment_schema_version` 与系统化人工反馈/修订闭环表（目前仅 `events` 有 `EventRevision`、`sources` 有 `SourceReview`）。
