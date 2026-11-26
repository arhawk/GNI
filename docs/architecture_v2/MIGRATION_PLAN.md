# GNI V2.0 分阶段迁移与实施路线（MIGRATION_PLAN）

> 本迁移计划覆盖 **Phase 2 至 Phase 8**，坚持“**P0 日报可追溯闭环先行 → P1 事件/叙事/周报深度 → P2 月报战略/人工反馈/质量评估**”的渐进式演进策略。每阶段均明确具体修改文件、函数、Schema 变更、兼容策略与可量化验收测试。

---

## 1. 阶段总览与优先级排期

| 阶段 | 优先级 | 核心里程碑 | 涉及数据库表变更 |
|---|---|---|---|
| **Phase 2：数据契约统一** | **P0** | 统一 7 大 Pydantic v2 逻辑契约与版本常量，建立跨层依赖测试守护 | **0 张新表**（纯 Pydantic / JSON 契约 + 版本常量） |
| **Phase 3：文章级情报分析完善** | **P0 + P1** | P0：`expression_owner`、原文引句偏移校验、跨字段质量检查、历史 `v0.1` 增量重跑 CLI；P1：`narratives[]`/`entities[]`/`event_candidates[]` | **0 张新表**（`structured_result` 升级 `article_analysis_v1.1`） |
| **Phase 4：监测与聚合完善** | **P0 + P1** | 确定性 `changes.py`（变化检测+小样本保护）、`alerts/rules.py` 切 V1.0 口径；P1：事件多语言抽取/地理/7态状态、叙事聚类写入 `narrative_clusters` | 仅 P1 对 `narrative_clusters`/`event_narrative_evidence` 做最小增量列扩展 |
| **Phase 5：研判引擎完善** | **P0 + P1** | 抽离 `src/gni/assessment/`（保留兼容 re-export）、补齐 `package_id`/`limitations[]`/替代解释、Stage 1 并发 + Stage 2 依赖调度、5 层 Validator、P1 新增 `narrative_analysis` 任务 | **0 张新表**（复用 `report_narrative_tasks`） |
| **Phase 6：报告引擎改造** | **P0 + P1** | 抽离共享 `src/gni/reports/builder.py`、输出兼容的统一 `ReportPackage`、先完成日报闭环再迁移周/月报、加固 `validate.py` 顶层一致性校验 | **0 张新表**（复用 `report_snapshots`） |
| **Phase 7：API 与前端改造** | **P0 + P1** | 扩展 `/api/articles/trace` 返回 spans + `expression_owner`；前端收敛消费 `ReportPackage`，补齐 `rule_only` 显式区分、`NarrativeAnalysisBlock`、时间轴、样本量与替代情景 | **0 张新表** |
| **Phase 8：质量验证与 P2 治理** | **P0 + P2** | 建立第 12 节 10 项全链路端到端测试；P2 落地 `analysis_feedback` 人工修订表与抽样质量评估脚本 | 仅 P2 新增 1 张轻量表 `analysis_feedback` |

---

## 2. 分阶段详细工程方案

### Phase 2：数据契约统一（P0）

- **修改 / 新增文件**：
  - 新增 `src/gni/contracts.py`（或 `src/gni/core/contracts.py`）：集中定义 `ArticleIntelligenceV2`、`EventIntelligenceV2`、`NarrativeIntelligenceV2`、`MetricSnapshotV2`、`EvidencePackageV2`、`AssessmentResultV2`、`ReportPackageV2` 与统一版本常量（`ASSESSMENT_SCHEMA_VERSION = "assessment_v2.0"`、`REPORT_PACKAGE_VERSION = "report_package_v2.0"`）。
  - 修改 `src/gni/reports/narrative/schemas.py`：使 `Finding` 兼容 `Outlook` 分类并新增可选字段 `supporting_metrics`、`counter_evidence`；使 `OutlookSignal` 新增可选字段 `observation_object`、`trigger_metrics`、`alternative_explanation`、`alternative_scenario`（全设默认值保证 100% 向后兼容）。
  - 修改 `tests/unit/test_imports.py`：增加静态模块依赖方向守护（确保 `metrics`/`events`/`analysis` 不导入 `reports`/`api`）。
- **测试与验收**：
  - 新增 `tests/unit/test_v2_contracts.py`：覆盖全部 7 个契约的序列化/反序列化、必填与选填校验、`NULL`/`Unclassified` 语义、新旧字段向后兼容。

### Phase 3：文章级情报分析完善（P0 先行，P1 增量）

- **修改文件与函数**：
  - `src/gni/analysis/deepseek.py`（`DeepSeekLLMProvider.analyze()`）：
    - **P0**：升级 Prompt（`deepseek_analyze_v1.1`），强制 `china_stance` 输出 `target="china_mainland"`、`expression_owner`（`media|quoted_actor|unclear`）、`reasoning`；返回 `sentiment` 的 `sentiment_target`/`confidence`/`reasoning`。
    - **P1**：在同一次文章 LLM 调用中增量输出精简 `narratives[]`（`frame`, `claim`, `actor`, `target`, `attribution`, `tone`, `quote`）、`entities[]`（含 `roles`）与 `event_candidates[]`（含 `event_relation`），**避免把单篇文章拆成 6 次串行 LLM 调用导致成本暴涨**。
  - `src/gni/analysis/heuristic.py`（`build_structured_analysis()`）：同步输出 `expression_owner`、`quality` 块与兼容 `v1.1` Schema。
  - `src/gni/analysis/service.py`（`analyze_article()`）：新增确定性 `_validate_article_intelligence()` 跨字段校验——使用 `l3_spans.py:validate_span_quote()` 核验 `stance_evidence[].quote` 并反查 `char_start`/`char_end` 与 `article_version_id`；若 `expression_owner == "quoted_actor"` 则禁止直接作为媒体自身立场计入，或置 `needs_review=True`；生成规范 `quality` 对象。
  - `src/gni/analysis/stance_util.py`（`extract_v1_china_stance()`）：接受 `schema_version in {"article_analysis_v1.0", "article_analysis_v1.1"}`，并严格拦截 `expression_owner == "quoted_actor"` 误计为媒体立场。
  - `src/gni/cli.py`：为 `gni analyze run` 增加 `--reanalyze-legacy` 参数，支持按时间窗分批重跑存量 `v0.1` 涉华文章（不删除旧记录，append-only 写新 `ArticleAnalysis`）。
- **测试与验收**：
  - 扩展 `tests/unit/test_analyze_service.py` 与 `tests/unit/test_metrics_v1_spec.py`：验证被引用对象观点不污染媒体对华立场、编造引句被校验拦截、`Unclassified` 与缺失正文处理正确、`v1.0` 与 `v1.1` 混合读取无回归。

### Phase 4：监测与聚合完善（P0 + P1）

- **修改 / 新增文件与函数**：
  - **P0** 新增 `src/gni/metrics/changes.py`（`detect_deterministic_changes()`）：纯确定性模块，基于当前与历史 `StatSnapshot` 计算 `Growth Rate`、`Topic/Country Share`、`Negative Share Delta`、`Historical Baseline`、`Concentration` 与**小样本保护标志**（如 `sample_too_small: count < 5`）及**采集覆盖变动提示**（结合 `SourceHealth`），产出标准 `ChangeCandidate[]`。
  - **P0** 修改 `src/gni/alerts/rules.py`（`generate_intelligence_alerts()`）：将 `_article_time()` 严格收敛为 `published_at`（停止回退 `first_seen_at`）；将 `stance_shift` / `narrative_shift` 切换为读取 V1.0 `topics_v1` 与 `extract_v1_china_stance()`；复用 `changes.py` 消除重复计算。
  - **P1** 修改 `src/gni/events/extract.py`、`match.py`、`service.py`：优先消费文章级 `event_candidates[]`（保留正则兜底）；增强事件地理抽取（结合文章实体与地点映射写入 `event_locations`）；新增事件演化状态计算（`emerging|ongoing|escalating|de_escalating|resolved|dormant|uncertain`）；继续严格守卫 `event_time` 不被 `published_at` 替代。
  - **P1** 新增 `src/gni/narratives/service.py`（`rebuild_narrative_clusters()`）：聚合文章级 `narratives[]`，基于语义框架+论点归并写入 `narrative_clusters` 与 `event_narrative_evidence`（区分 `supporting` 与 `counter` 证据，标注 `trend_status` 与 `related_countries`）。
- **测试与验收**：
  - 新增 `tests/unit/test_metrics_changes.py`：验证小样本波动（如 2 篇→4 篇 +100%）不会误触发重大异常、重复文章/多议题/Unclassified 口径 100% 守恒。
  - 扩展 `tests/unit/test_events_service.py` 与新增 `tests/unit/test_narratives_service.py`：验证 `event_time=None` 绝不被 `published_at` 填充、叙事聚类正反证据正确落库。

### Phase 5：研判引擎完善（P0 + P1）

- **修改 / 新增文件与函数**：
  - 创建 `src/gni/assessment/`（`evidence.py`、`schemas.py`、`prompts.py`、`runner.py`、`validator.py`），并将 `src/gni/reports/narrative/` 改为薄 re-export 兼容层（零破坏既有 import）。
  - `evidence.py`（`prepare_evidence_bundle()`）：
    - 解耦对 `reports/*.py` 私有字典结构的依赖，直接消费 `StatSnapshot` + `ChangeCandidate[]` + `Event` + `NarrativeCluster` + `Alert`；
    - 为每个任务切片生成可追溯 `package_id`，扩展按事件/按议题级别反例抽取，确定性注入标准 `limitations[]`。
  - `runner.py`（`run_report_intelligence()`）：
    - 实现 Stage 1（并发 `ThreadPoolExecutor(max_workers=3)` 调用 HTTP LLM）→ Stage 2（`emerging_signals` 消费 Stage 1 摘要 + `ChangeCandidate[]`）→ 主线程统一持久化 `ReportNarrativeTask`；
    - 将 `package_id`、`assessment_schema_version`、`evidence_trim_stats` 写入任务元数据。
  - `prompts.py`：
    - 更新 `emerging_signals` Prompt 要求输出 `alternative_explanation`、`alternative_scenario`、`trigger_metrics`；
    - **P1** 为周/月报新增 `narrative_analysis` 任务（消费真实 `NarrativeCluster` 与正反证据）。
  - `validator.py`：升级为 5 层校验（Schema / Evidence / Metric Consistency / Cross-field / Completeness），校验 `alternative_explanation` 与 `limitations` 完整性。
- **测试与验收**：
  - 扩展 `tests/unit/test_report_narrative_layer.py`：Mock LLM 验证两阶段并发执行、单任务失败局部重试、5 层 Validator 检出率、周/月报 `narrative_analysis` 输出与耗时回归测试。

### Phase 6：报告引擎改造（P0 日报先行 → P1 周/月报迁移）

- **修改 / 新增文件与函数**：
  - 新增 `src/gni/reports/builder.py`（`build_report_package()`）：抽取日/周/月报公共时间窗解析、V1.0 统计快照读取、`ChangeCandidate` 加载、事件时间窗加载、Assessment 调用与统一 `ReportPackage` 装配。
  - 修改 `src/gni/reports/daily.py`（优先完成日报 P0 闭环）：基于 `builder.py` 重组，同步保留旧 `sections` 键兼容，标记 `polish.py` 为 deprecated。
  - 修改 `src/gni/reports/weekly.py`、`monthly.py`：迁移至共享 `builder.py`，周/月报接入 `narrative_analysis` 与真实 `NarrativeCluster`，确保月报继续基于月度文章级重算而非日/周平均。
  - 修改 `src/gni/reports/validate.py`：补齐 V2.0 第 8.3 节缺失项——顶层 `article_count` 与 `v1_stats.global.article_count` 一致、正/中/负比例之和与 `classified_count` 分母一致、`country_scope` 合法性、引用 `article_id` 存在性核验。
- **测试与验收**：
  - 扩展 `tests/unit/test_daily_intel_fix.py` 与 `tests/unit/test_report_narrative_layer.py`：验证日/周/月报共用底座、失败任务不产生伪造结论、顶层校验全部生效。

### Phase 7：API 与前端改造（P0 + P1）

- **修改文件与函数**：
  - `src/gni/api/app.py`（`api_articles_trace()`）：扩展返回 `spans[]`（`paragraph_index`/`char_start`/`char_end`/`text_original`）、`expression_owner`、`sentiment`、`article_analysis_version`。
  - `web/src/api.ts`：同步 TypeScript 类型定义（`ReportPackage`、`TraceArticle`、`OutlookSignal` 新增字段）。
  - `web/src/pages/Reports.tsx` 与 `web/src/components/narrative/`：
    - 显式区分 `rule_only` 规则基线与真实 LLM 研判徽章；
    - 新增 `NarrativeAnalysisBlock`（消费 `narrative_analysis`）；
    - `EventInterpretationCards.tsx` 渲染结构化事件时间轴；
    - `CrossCountryAnalysisBlock` 卡片头部内联精确样本量 `n` 与覆盖率；
    - `OutlookSignalsPanel.tsx` 渲染 `alternative_explanation` / `alternative_scenario`；
    - `EvidenceChips.tsx` + `EvidenceTraceTable.tsx` 展示原文 Span 段落与 `expression_owner`（媒体自身 vs 引述对象）徽章。
- **测试与验收**：
  - `cd web && npm run build`（`tsc -b && vite build` 零错误）+ `tests/e2e/test_web_react_playwright.py` 验证报告渲染与证据抽屉下钻交互。

### Phase 8：全链路端到端质量验证与 P2 治理闭环

- **端到端验收测试套件**（新增 `tests/integration/test_v2_end_to_end.py`，逐条覆盖 V2.0 第 12 节全部 10 项验收标准）：
  1. 单篇文章入库 → 清洗 → L2/L3 → `ArticleIntelligenceV2` 完整落库；
  2. 一篇文章命中多议题时同板块去重、跨议题允许重叠、全球总量不重复；
  3. 重复采集文章不会增加全球文章总量；
  4. `Unclassified` 保留总量但不进入正/中/负比例分母，且 `stance_coverage_rate` 正确；
  5. 多国媒体文章严格按 `Source.country_id` 归属；
  6. `event_time` 不明确时保持 `NULL`，绝不被 `published_at` 替代；
  7. 报告 Finding → `EvidenceChips` → `/api/articles/trace` 可追溯至原文 Span 与 `expression_owner`；
  8. LLM 输出的统计数字经 Validator 校验与确定性 `StatSnapshot` 一致；
  9. LLM 失败/超时/无 Key 时报告明确标记 `failed`/`partial`/`rule_only`，绝不伪造结论；
  10. 日报（单日）、周报（7 日）、月报（自然月重算）周期统计口径严格一致。
- **P2 长期治理增量**：
  - 新增 `analysis_feedback` 表与 `POST /api/feedback`、`GET /api/feedback`（保留原始模型输出 + 人工修订 + 原因 + 操作者 + 分析版本）；
  - 新增 `src/gni/governance/eval.py` 基于抽样标注集计算 Precision/Recall/F1、Stance 准确率与证据覆盖率；
  - 修正既有 `tests/unit/test_editorial_focus.py` 2 项源配置单测。
