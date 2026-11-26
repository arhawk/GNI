# GNI API 与前端组件映射及逐项审计（API_FRONTEND_MAPPING）

> 本文件逐接口梳理 `src/gni/api/app.py` 与 `web/src/api.ts`，并严格按 **V2.0 规范第 9.3 节 6 条标准**对所有报告与叙事展示组件进行实证审计，给出完整证据追溯链路与 Phase 7 改造清单。

---

## 1. FastAPI 端点与前端调用映射

| 后端路由（`src/gni/api/app.py`） | 后端处理器 | 前端调用（`web/src/api.ts`） | 消费页面 / 组件 | 数据本质（确定性 / LLM） |
|---|---|---|---|---|
| `GET /health` | `health()` | — | 运维探活 | 确定性 |
| `GET /api/overview` | `events/service.py:overview_payload()` | `fetchOverview()` | `Overview.tsx` | 确定性（混合旧 `MetricRun` + 事件地图 + 国家态度） |
| `GET /api/events` / `GET /api/events/{id}` | `events/service.py:list_events()` / `get_event_detail()` | `fetchEvents()` / `fetchEventDetail()` | `Events.tsx`、`EventDetail.tsx` | 确定性（含 `EventMetricSnapshot`、参与方、地理、关联文章） |
| `POST /api/events/rebuild` / `lock` / `merge` | `events/service.py` | `rebuildEvents()` / `lockEvent()` / `mergeEvents()` | `Events.tsx`、`EventDetail.tsx` | 确定性 + 人工修订写 `EventRevision` |
| `GET /api/countries` / `/{id}` / `/{id}/china-attitude` | `dashboard/pages_api.py` / `events/service.py` | `fetchCountries()` / `fetchCountryDetail()` / `fetchCountryAttitude()` | `Countries.tsx`、`DualMap.tsx` | 确定性（部分使用旧情感计数，未全部统一 V1.0） |
| `GET /api/trends` | `dashboard/pages_api.py:trends_payload()` | `fetchTrends()` | `Trends.tsx` | 确定性（含旧趋势与 V1.0 数据） |
| `GET /api/alerts` + `POST /run\|acknowledge\|resolve\|close` | `alerts/service.py` | `fetchAlerts()` / `transitionAlert()` | `Alerts.tsx` | 确定性规则告警 + 人工状态流转 |
| `GET /api/reports/daily` | `reports/daily.py:build_daily_report(analyze=False)` | `fetchDailyReport()` | `Reports.tsx:DailyBrief` | 确定性规则/V1.0 统计 + **读取缓存的 `intelligence`** |
| `GET /api/reports/weekly` | `reports/weekly.py:build_weekly_report(analyze=False)` | `fetchWeeklyReport()` | `Reports.tsx:PeriodBrief` | 同上 |
| `GET /api/reports/monthly` | `reports/monthly.py:build_monthly_report(analyze=False)` | `fetchMonthlyReport()` | `Reports.tsx:PeriodBrief` | 同上 |
| `POST /api/reports/{type}/analyze` | `api_analyze_report()` → `build_*_report(analyze=True, tasks=..., force=...)` | `analyzeReport()` | `Reports.tsx`（`IntelligenceHeader` 触发/重试按钮） | **触发 LLM 研判层**并返回含最新 `intelligence` 的完整报告 |
| `POST /api/articles/trace` | `api_articles_trace()` | `fetchArticleTrace()` | `EvidenceChips.tsx` → `EvidenceTraceTable.tsx` | 确定性（返回文章元信息 + V1.0 `stance_label`/`stance_confidence`/`stance_evidence`/`topics_v1`） |
| `GET /api/search` | `search/service.py:search_all()` | `searchAll()` | `TopSearch.tsx`、`CommandPalette.tsx` | 确定性（Meilisearch 或 Postgres `ILIKE`） |
| `GET /api/system/status` | `dashboard/pages_api.py:system_status_payload()` | `fetchSystemStatus()` | `System.tsx` | 确定性（源健康、任务状态、预算快照） |

---

## 2. 前端报告与叙事组件逐项审计（V2.0 第 9.3 节 6 条标准）

以下逐一核查每个组件的真实代码实现（不以组件名臆断功能已实现）：

| 组件（文件路径） | 1. 接收什么数据 | 2. 数据来源 API | 3. 是否真实消费 Assessment Result | 4. 是否含规则拼装文字 | 5. 是否有证据引用与下钻 | 6. 是否存在静态占位/模板 |
|---|---|---|---|---|---|---|
| **`DailyBrief`** (`web/src/pages/Reports.tsx:560`) | `DailyReport`（`sections.*` + `intelligence`） | `GET /api/reports/daily` & `POST /api/reports/daily/analyze` | **是**。消费 `intelligence.tasks.executive_analysis`、`event_analysis`、`emerging_signals` | **混合（已收敛）**。无 LLM 时展示规则 `judgment_text`/`top_changes`；有 LLM 时规则文字已折叠到 `<details>` 基线参考区 | **是**。LLM 结论经 `EvidenceChips` 下钻原文；规则事件带外链 | **否**（空数据时显示提示与生成按钮，不虚构） |
| **`PeriodBrief`** (`web/src/pages/Reports.tsx:158`) | `PeriodReport`（周/月报共用，`sections.*` + `intelligence`） | `GET /api/reports/{weekly\|monthly}` & `POST .../analyze` | **是**。消费全部 6 类 `intelligence.tasks.*` 并与确定性表格组合成 4 步结构 | **混合（已收敛）**。有 LLM 研判时隐藏重复的规则 `overview_text` 与 `summary.outlook`；无 LLM 时仅作规则基线提示 | **是**。每块均带 `EvidenceChips` + 表格下钻链接 | **局部残留**：无 LLM 时规则 `summary.outlook` 仍偏模板化，需在 Phase 7 明确标为「未执行 LLM 研判」 |
| **`IntelligenceHeader`** (`web/src/components/narrative/IntelligenceHeader.tsx`) | `intelligence` 块、`loading`、回调 `onGenerate`/`onRetryTask` | `/api/reports/{type}` 与 `/analyze` | **是**。真实展示整体状态、6 任务各自状态/Prompt 版本/模型/Token/耗时、可展开查看 `validation` 具体问题（数字/证据/推理） | **否** | **间接**（展示校验丢弃/降级明细） | **否** |
| **`FindingsGrid`** (`IntelligenceHeader.tsx`) | `Finding[]` | `intelligence.tasks.*.findings` | **是**。展示标题、结论、`Fact/Inference/Hypothesis` 徽章、置信度、推理过程、局限、`needs_review` 与 `validation_notes` | **否** | **是**（嵌入 `EvidenceChips`） | **否** |
| **`AnalysisSectionShell`** (`AnalysisSectionShell.tsx:12`) | `title`, `subtitle`, `conclusion`, `evidenceSlot`, `dataSlot`, `drilldownLinks` | 容器壳组件（由调用方传入） | **是**（强制按「1结论→2证据→3确定性数据→4下钻」顺序渲染） | 取决于调用方 | 取决于调用方 | **否** |
| **`EventInterpretationCards`** (`EventInterpretationCards.tsx:7`) | `task?: NarrativeTaskOutput` (`event_analysis`) | `intelligence.tasks.event_analysis` | **是**。渲染背景、发生了什么、事件实际进展、媒体关注度变化、各国跟进时间、各国报道差异、媒体观点、后续观察、局限、`uncertainties`/`follow_up_questions` | **否** | **是**（事件详情链接 + `EvidenceChips`） | **否**。缺口：未将 `timeline[]` 渲染为结构化时间轴 |
| **`TopicTrendAnalysisBlock`** (`AnalysisSectionShell.tsx:73`) | `task` (`topic_trend_analysis`) + `dataSlot`（V1.0 15 议题统计表） | `intelligence.tasks.topic_trend_analysis` + `sections.v1_stats.topics` | **是**。展示关注度/立场/结构三区分、驱动因素、`persistence` 徽章与 `needs_review` | **否**（`dataSlot` 为纯确定性统计表） | **是**（`EvidenceChips` + 下钻 `/trends`） | **否** |
| **`CrossCountryAnalysisBlock`** (`AnalysisSectionShell.tsx`) | `task` (`cross_country_analysis`) + `dataSlot`（分国统计/叙事表） | `intelligence.tasks.cross_country_analysis` + `sections.cross_country_narrative` | **是**。展示共同关注、各国框架（`country_frames`）、主要差异、样本不足国家、`confidence`、`needs_review` | **否** | **是**（`EvidenceChips` + 下钻 `/countries`） | **否**。缺口：国家卡片未内联显示精确样本量 `n` |
| **`StanceAnalysisBlock`** (`AnalysisSectionShell.tsx`) | `task` (`stance_analysis`) + `dataSlot`（V1.0 立场分布表） | `intelligence.tasks.stance_analysis` + `sections.v1_stats` | **是**。展示比例与数量区分说明、驱动因素、覆盖率局限、`needs_review` | **否** | **是**（`EvidenceChips`） | **否**。缺口：未将 `Sentiment` 与 `Stance` 双轨对比可视化并列展示 |
| **`OutlookSignalsPanel`** (`OutlookSignalsPanel.tsx:6`) | `task` (`emerging_signals`) | `intelligence.tasks.emerging_signals` | **是**。展示条件性信号、依据、触发条件、监测指标、不确定性、`uncertainties`、`follow_up_questions` | **否** | **是**（`EvidenceChips`） | **否**。缺口：尚缺 `alternative_explanation` 与 `alternative_scenario` 渲染 |
| **`EvidenceChips`** (`EvidenceChips.tsx:22`) | `EvidenceRef[]` | 点击文章芯片时异步调用 `POST /api/articles/trace` | **是**。将 `metric`/`event`/`alert`/`article` 四类引用转为可交互跳转与原文证据抽屉 | **否** | **是（核心溯源枢纽）** | **否**。缺口：抽屉展示 `stance_evidence` 原文引句，但尚未展示 `ArticleChinaSpan` 段落高亮与 `expression_owner` 徽章 |
| **`V1StatsBlock` & `tables/*`** (`Reports.tsx:861` & `components/tables/`) | `V1StatsByScope` / 表格行 | `sections.v1_stats` / `/api/articles/trace` / `/api/events` | N/A（纯确定性统计表格组件） | **否**（严格 V1.0 数值，含 `Unclassified` 与覆盖率） | `EvidenceTraceTable` 承载文章原文下钻 | **否** |

---

## 3. 证据追溯链路现状 vs V2.0 第 11.1 节要求

当前已打通的追溯路径：

```text
Report Page (DailyBrief / PeriodBrief)
  -> Finding / EventInterpretation / TopicTrend / CrossCountry / OutlookSignal
  -> EvidenceChips (type: article | event | metric | alert)
  -> POST /api/articles/trace (article_ids)
  -> EvidenceTraceTable (title, url, source_country, stance_label, stance_confidence, stance_evidence[].quote)
```

**尚未打通的断点（Phase 7 补齐目标）**：
1. **Task & Evidence Package 级溯源断层**：前端无法从某条 Finding 查看它对应的 `package_id`、`evidence_hash` 或输入证据包覆盖快照（目前仅在 `IntelligenceHeader` 展示了 `task_statuses` 级别元数据）；
2. **原文 Span 与 `expression_owner` 断层**：`POST /api/articles/trace` 仅返回 `stance_evidence` 摘要，未返回 `ArticleChinaSpan` 的精确段落/偏移量与 `expression_owner`（媒体自身 vs 被引用对象），用户无法一键核验“这条立场是否是记者引述第三方发言”；
3. **无人工反馈入口**：前端目前对报告 Finding、Topic、Stance、Narrative 无「标记误判 / 提交人工修订」交互，仅有事件锁定/合并和预警状态流转。

---

## 4. Phase 7 前端与 API 增量改造清单（高复用、不推翻重做）

1. **API 兼容演进（`src/gni/api/app.py`）**：
   - 保持现有 `/api/reports/{daily|weekly|monthly}` 与 `/analyze` 路由向后兼容；在载荷中新增标准化 `report_package` 字段（或通过 `schema_version` 平滑过渡），不破坏既有字段。
   - 扩展 `POST /api/articles/trace` 返回 `spans[]`（来自 `ArticleChinaSpan`）、`expression_owner`、`sentiment` 与 `article_analysis_version`，补齐正文级溯源。
   - 新增 P2 人工反馈接口（如 `POST /api/feedback`）写入修订日志而不覆盖原始模型输出。
2. **前端组件升级（`web/src/`）**：
   - 将 `DailyBrief` 与 `PeriodBrief` 逐步收敛为基于统一 `ReportPackage.sections[]` 驱动的渲染框架，保留日/周/月差异化展示，消除两套硬编码排版重复；
   - 在 `Reports.tsx` 中补齐独立的 `NarrativeAnalysisBlock`（消费 Phase 5 新增的 `narrative_analysis` 任务，展示主导/新兴/衰退/冲突叙事及正反证据）；
   - 在 `OutlookSignalsPanel.tsx` 补充 `alternative_explanation` / `alternative_scenario` 渲染；在 `EventInterpretationCards.tsx` 补充结构化时间线渲染；在 `CrossCountryAnalysisBlock` 卡片头部内联显示精确样本量 `n`；
   - 在 `Reports.tsx` 显式区分 `rule_only`（未执行 LLM 研判）与真实 LLM 结论，杜绝规则基线摘要被误读为深度研判。
