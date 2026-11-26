# GNI 现状与 V2.0 目标架构差距分析（GAP_ANALYSIS）

> 本清单基于 Phase 0 真实源码与本地数据库审查汇总，严格区分 **已实现 / 部分实现 / 缺失 / 重复实现 / 需重构**，并为每个差距标注 **P0 / P1 / P2** 优先级与精确的代码/表位置。

---

## 1. 全栈差距总览矩阵

### 1.1 P0 级差距（必须优先保证：可靠、可追溯的日报与核心数据闭环）

| 编号 | 领域 | 差距类型 | 现状真实位置 | 具体问题描述 | 目标动作（对应阶段） |
|---|---|---|---|---|---|
| **GAP-01** | Article Intelligence · Stance | **部分实现** | `src/gni/analysis/deepseek.py:181-227`、`heuristic.py`、`stance_util.py` | `china_stance` 仅在 Prompt 文本中提醒区分媒体与引述，**无结构化 `expression_owner`（`media\|quoted_actor\|unclear`）字段与显式 `target` 字段**，程序无法确定性过滤纯引述立场 | Phase 2/3：在 `article_analysis_v1.1` 中将 `expression_owner` 与 `target` 设为必填字段，并由 `stance_util.py` 做确定性守门 |
| **GAP-02** | Article Intelligence · Evidence 校验 | **缺失** | `src/gni/analysis/deepseek.py:215`、`analysis/service.py` | DeepSeek 返回的 `stance_evidence[].quote` 未对照 `ArticleVersion.content_clean` 校验是否存在、无 `evidence_id` 与字符偏移定位，存在引文幻觉风险 | Phase 2/3：复用 `l3_spans.py:validate_span_quote()` 在入库前执行原文对齐与跨字段校验，失败项标 `needs_review=True` |
| **GAP-03** | 数据质量 · 历史存量 | **存量瓶颈** | 本地 DB `article_analyses`（573/676 = **84.8%** 为 `v0.1`/`l2_gate_v1`） | 严格 V1.0 统计下旧版分析全归 `Unclassified`，导致当前实库大部分周期 `stance_coverage_rate` 偏低，制约研判有效样本 | Phase 3：提供增量重跑 CLI（按窗口/优先级重跑历史涉华文章至 `v1.1`），并在报告覆盖率中显式透出 V1.0 分析覆盖率 |
| **GAP-04** | 数据契约 · Assessment / Report 版本与契约 | **部分实现** | `src/gni/reports/narrative/schemas.py`、`evidence.py`、`daily.py` | 缺少显式 `assessment_schema_version`、`package_id`、`Finding.supporting_metrics`、`Finding.counter_evidence`、`OutlookSignal.alternative_explanation`；报告顶层 `sections` 字典在日/周/月报间异构 | Phase 2：先统一 7 大 Pydantic v2 逻辑契约与版本常量，保持向后兼容，配齐 Schema Validation 单测 |
| **GAP-05** | 报告顶层校验 | **部分实现** | `src/gni/reports/validate.py` | 未在报告顶层校验 `article_count == v1_stats.global.article_count`、正/中/负比例之和与 `classified_count` 分母一致、`country_scope` 合法性 | Phase 6：补齐 V2.0 第 8.3 节全部确定性一致性校验项 |
| **GAP-06** | 证据追溯链路 · API | **部分实现** | `src/gni/api/app.py:320-356`、`web/src/components/narrative/EvidenceChips.tsx` | `POST /api/articles/trace` 未返回 `ArticleChinaSpan` 正文段落/偏移量与 `expression_owner`；前端无法从 Finding 追溯到任务 `package_id` 与输入证据包覆盖情况 | Phase 7：扩展 `/api/articles/trace` 载荷与 `EvidenceTraceTable`，在 `Finding` 卡片支持展开证据包元信息 |
| **GAP-07** | 报告展示 · 规则与 LLM 边界 | **部分实现** | `web/src/pages/Reports.tsx` | 当处于 `rule_only`（未运行 LLM）时，规则 `judgment_text` / `overview_text` 仍无显眼徽章区分，存在被误读为 LLM 研判的风险 | Phase 7：为所有 `rule_only` 规则基线文本加显式状态标识，并逐步转向统一 `ReportPackage.sections[]` 驱动渲染 |

### 1.2 P1 级差距（显著提升周报、事件、叙事与跨国分析深度）

| 编号 | 领域 | 差距类型 | 现状真实位置 | 具体问题描述 | 目标动作（对应阶段） |
|---|---|---|---|---|---|
| **GAP-08** | Monitoring · 叙事聚合 | **完全缺失（仅建表）** | `models.py:579-600`（`narrative_clusters=0`、`event_narrative_evidence=0`） | 两张表全仓无任何写入代码；文章级也无结构化 `narratives[]` 提取（`claims=[]`），导致周/月报无法做真实叙事演变与冲突分析 | Phase 3/4/5：文章级增加 `narratives[]` 提取 → 新增叙事聚类写入 `narrative_clusters`（含支持/反例）→ 周/月报新增 `narrative_analysis` 任务 |
| **GAP-09** | Monitoring · 事件聚合与地理 | **部分实现（质量偏弱）** | `src/gni/events/extract.py`、`geo.py`、`match.py`、`models.py` | 实库 1,799 篇文章仅产出 32 事件且基本 1 对 1（`event_articles=32`），`event_locations=0`；正则抽取仅偏英文标题，缺 `event_relation` 与 7 态演化状态 | Phase 3/4：将事件候选纳入文章级结构化分析（支持多语言与 `event_relation`），强化地点抽取与演化状态判定 |
| **GAP-10** | Monitoring · 变化检测与口径统一 | **重复实现 / 口径分裂** | `src/gni/alerts/rules.py`、`metrics/compute.py`、`reports/daily.py`/`weekly.py`/`monthly.py` | `alerts/rules.py` 仍读旧 `topics.primary` / 旧 `stances` 且时间回退 `first_seen_at`；变化率检测分散在多处且缺小样本保护与采集覆盖变动甄别 | Phase 4：新增确定性 `src/gni/metrics/changes.py`（基于 `v1_stats`，含历史基线、小样本门槛、覆盖变动标记）；改造 `alerts/rules.py` 统一消费 V1.0 口径 |
| **GAP-11** | Architecture · 研判层与报告层耦合 | **需重构** | `src/gni/reports/narrative/`、`reports/daily.py`/`weekly.py`/`monthly.py` | 研判引擎嵌在 `reports/narrative/` 内；日/周/月报存在大量重复的文章加载、统计汇总和事件拼装代码；串行 6 任务耗时 ~45s 接近 60s 网关超时线 | Phase 5/6：提升 `src/gni/assessment/`（保留兼容 re-export），实现 Stage 1 并发 + Stage 2 依赖调度；抽取共享 `src/gni/reports/builder.py` |
| **GAP-12** | Article Intelligence · Entity & Sentiment | **部分实现** | `src/gni/analysis/deepseek.py`、`heuristic.py` | DeepSeek 未输出正文级非中国关键实体及角色；Sentiment 缺 `sentiment_target`/`reasoning`/`evidence_refs` | Phase 3：在 `article_analysis_v1.1` Prompt 与 Schema 中补齐结构化 `entities[]` 与 `sentiment` 目标/理由 |
| **GAP-13** | Evidence Package · 细粒度反例与局限 | **部分实现** | `src/gni/reports/narrative/evidence.py` | `counter_examples` 目前仅按全局主导立场抽取，未按重点事件/重点议题局部抽反例；`limitations[]` 未标准化注入 Prompt | Phase 5：扩展按事件/议题级别反例抽取，确定性生成标准 `limitations[]` 与 `change_candidates[]` 注入证据包 |
| **GAP-14** | Frontend · 周/月报深化组件 | **部分实现** | `web/src/components/narrative/`、`Reports.tsx` | 缺独立 `NarrativeAnalysisBlock`、`EventInterpretationCards` 未渲染结构化时间轴、`CrossCountryAnalysisBlock` 未内联国家样本量 `n`、`OutlookSignalsPanel` 缺替代解释/替代情景 | Phase 7：增量升级现有 `narrative/` 组件并补齐 `NarrativeAnalysisBlock` |

### 1.3 P2 级差距（长期治理、月报深化与质量评估闭环）

| 编号 | 领域 | 差距类型 | 现状真实位置 | 具体问题描述 | 目标动作（对应阶段） |
|---|---|---|---|---|---|
| **GAP-15** | Governance · 人工反馈闭环 | **缺失** | 仅 `EventRevision`、`SourceReview` 存在 | 无法对 Topic、Sentiment、Stance、Narrative、Finding、Signal 提交人工修订与保留原始模型输出对照 | Phase 8 / P2：新增轻量 `analysis_feedback` 表与 `/api/feedback` 接口，前端提供纠偏入口 |
| **GAP-16** | Governance · 离线质量评估体系 | **缺失** | 无评测集与指标计算脚本 | 缺乏人工抽样标注集上的 Precision/Recall/F1、Stance 准确率、事件误合并率、证据覆盖率与人工认可度统计 | P2：建立 `src/gni/governance/eval.py` 与抽样评测 CLI |
| **GAP-17** | Processing · 跨源去重持久化 | **部分实现** | `processing/service.py:_find_duplicate()`（仅同源）vs `v1_stats.py`（统计期全局去重） | 跨源完全相同正文/规范 URL 未在入库处理期持久化关联，导致 `articles` 列表与 `v1_stats` 总量需二次去重 | P2：在不破坏同源原始采集留存前提下，增加跨源重复链接关系标记 |
| **GAP-18** | Legacy 清理 | **重复实现** | `src/gni/reports/polish.py`、`metrics/compute.py` 旧 7 议题、`tests/unit/test_editorial_focus.py` | `polish.py` 与 `intelligence` 研判层重叠；`test_editorial_focus.py` 有 2 个因 `sources.yaml` 扩源导致的既有单测失败 | Phase 6/8：下线或标记弃用 `polish.py`；同步修正 `test_editorial_focus.py` 或源元数据 |

---

## 2. 已有高复用资产清单（严禁重复建设）

以下能力经实证已达较高工程水准，后续改造必须直接复用而非重写：
1. `src/gni/metrics/v1_stats.py` + `configs/taxonomy_v1.yaml`：严格遵守 V1.0 统计口径（4 板块×15 议题、3 类立场+Unclassified、覆盖率、`article_ids` 溯源），零 DB 耦合，单测完备。
2. `src/gni/analysis/l2_fulltext.py` + `l3_spans.py` + `relevance.py`：完整的 L2 门控、L3 段落偏移定位与原文切片校验机制。
3. `src/gni/analysis/deepseek.py:DeepSeekLLMProvider.generate_json()` + `analysis/budget.py`：带重试、Token 成本估算与独立报告预算守卫的统一 LLM 调用底座。
4. `src/gni/reports/narrative/runner.py` + `validator.py` + `ReportNarrativeTask` 表：已具备 `(report_type, period, task_type, prompt_version)` 任务级缓存、`evidence_hash` 过期检测、结构化 JSON 瘦身（无硬截断）与 3 层确定性校验。
5. `src/gni/infrastructure/models.py` 现有 36 张 ORM 表（含 `events`/`event_revisions`/`narrative_clusters`/`stat_snapshots`/`report_narrative_tasks`）与 `web/src/components/narrative/*`、`components/tables/*`。
