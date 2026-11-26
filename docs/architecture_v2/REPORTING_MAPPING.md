# GNI 报告引擎映射与目标 Report Package 契约（REPORTING_MAPPING）

> 本文件映射 `src/gni/reports/`（`daily.py`、`weekly.py`、`monthly.py`、`validate.py`、`polish.py`、`risk_tagging.py`）到 **V2.0 规范第 7、8 节**（Reporting Engine 与 Report Package），明确三类报告的底层复用现状、规则/LLM 边界、失败降级策略与目标统一契约。

---

## 1. 三类报告真实实现对比

| 维度 | Daily（`src/gni/reports/daily.py`） | Weekly（`src/gni/reports/weekly.py`） | Monthly（`src/gni/reports/monthly.py`） |
|---|---|---|---|
| **主构建函数** | `build_daily_report(session, day=..., polish=False, analyze=False, ...)` | `build_weekly_report(session, end_day=..., analyze=False, ...)` | `build_monthly_report(session, month=..., analyze=False, ...)` |
| **Schema 版本** | `daily_report_schema_v4` | `weekly_report_schema_v1` | `monthly_report_schema_v1` |
| **时间口径** | 单自然日（`Asia/Shanghai` 转 UTC），对比昨日 + 7日基线 | 7 天滚动自然日窗口（`end_day - 6d` 至 `end_day`），对比上一周 + 4周历史序列 | 完整自然月（基于月度文章级原始数据重新计算，**非日/周平均**），对比上月 + 6月历史序列 |
| **底层指标复用** | `run_v1_stat_snapshots()`（V1.0）+ `run_metrics()`（旧 v0.4 辅助） | `run_v1_stat_snapshots()`（本周+上周+4周）+ 自写旧统计辅助函数 | `run_v1_stat_snapshots()`（本月+上月+6月）+ 自写旧统计辅助函数 |
| **事件查询** | `list_events(session, limit=40, window_start=..., window_end=...)` + 综合条件切分 `primary`/`secondary` | `list_events(..., window_start=..., window_end=...)` + `event_evolution` | `list_events(..., window_start=..., window_end=...)` + 跨月阶段事件 |
| **LLM 研判任务** | 3 任务：`executive_analysis`、`event_analysis`、`emerging_signals` | 6 任务：`executive_analysis`、`event_analysis`、`topic_trend_analysis`、`cross_country_analysis`、`stance_analysis`、`emerging_signals` | 6 任务（同周报结构，独立月度 Prompt 版本 `monthly_*_v1.0`） |
| **顶层校验** | `validate.py:validate_daily_report()` | `validate.py:validate_weekly_report()` | `validate.py:validate_monthly_report()` |
| **Markdown 导出** | `render_daily_markdown()`（LLM 结论前置） | `render_weekly_markdown()`（LLM 结论前置） | `render_monthly_markdown()`（LLM 结论前置） |
| **持久化缓存** | `ReportSnapshot(report_type='daily', period=YYYY-MM-DD)` + `ReportNarrativeTask` | `ReportSnapshot(report_type='weekly', period=...)` + `ReportNarrativeTask` | `ReportSnapshot(report_type='monthly', period=YYYY-MM)` + `ReportNarrativeTask` |

---

## 2. V2.0 建议章节 vs 现有 `sections` 映射

### 2.1 Daily Intelligence Brief

| V2.0 规范建议章节 | 现有 `daily.py` 数据来源 | 现状匹配度与差距 |
|---|---|---|
| **1. Executive Judgment** | `intelligence.tasks.executive_analysis`（LLM 主体）+ `sections.summary`（规则基线，前端已折叠） | **高匹配**；日报 `daily_exec_v1.0` 已覆盖整体态势与重点事件变化 |
| **2. Key Developments** | `intelligence.tasks.event_analysis` + `sections.major_events` + `sections.secondary_events` | **高匹配**；已解除 `china_signal_score >= 2.0` 单一越权门槛 |
| **3. Global Situation** | `sections.v1_stats`（全球/国家/4板块/15议题/立场分布）+ `sections.coverage` + `sections.tone` | **中匹配**；存在 `v1_stats` 与旧 `sections.tone`/`overview_stats` 口径并存，需在 Phase 6 彻底收敛 |
| **4. Key Changes & Anomalies** | `sections.anomalies` + `sections.summary.top_changes` + `executive_analysis.important_changes` | **中匹配**；规则异常仍依赖旧 `MetricRun` 与阈值比较，缺确定性小样本保护说明 |
| **5. Emerging Signals** | `intelligence.tasks.emerging_signals` + `sections.signals` + `sections.orphan_headlines` | **高匹配**；已将孤儿高价值文章注入 `emerging_signals` 证据包 |
| **6. Outlook & Watchlist** | `intelligence.tasks.emerging_signals.outlook_signals` + `follow_up_questions` + `uncertainties` | **中匹配**；缺 `alternative_explanation` 与 `alternative_scenario` 结构化字段 |
| **附录（统计/代表文章/覆盖/方法论）** | `sections.quality` + `sections.ops` + `disclaimer` + `validation` | **高匹配** |

### 2.2 Weekly Intelligence Report & Monthly Strategic Review

- **已覆盖部分**：`Weekly` 已具备 4 周 `historical_v1_stats`、`event_evolution`、`cross_country_narrative` 与 6 类 LLM 研判；`Monthly` 已具备月度重算（非日/周平均）、6 月 `historical_v1_stats`、`narrative_landscape`（基于 `framing.primary`）与 6 类 LLM 研判。
- **核心差距**：
  1. **代码重复（P1）**：`daily.py`、`weekly.py`、`monthly.py` 各自维护了一套文章加载、旧分国统计、事件格式化与摘要拼接逻辑（合计约 1,800+ 行），未抽离公共 `ReportBuilder` 底座；
  2. **非统一顶层 `sections` 契约（P0）**：当前 `sections` 是异构字典（日报有 `overview_stats`/`coverage`/`tone`/`anomalies`/`ops`，周/月报有 `topic_trends`/`cross_country_narrative`/`sentiment_stance`），且 `intelligence.tasks` 与 `sections` 平行挂载，前端不得不在 `Reports.tsx` 中硬编码两套独立组件（`DailyBrief` vs `PeriodBrief`）手工拼装；
  3. **Narrative 章节空心化（P1）**：周报与月报均缺少基于真实 `NarrativeCluster` 的独立 `narrative_analysis` 研判任务；
  4. **历史 `polish.py` 残留（P2）**：`daily.py` 仍保留 `polish=True` 路径调用 `polish.py:polish_daily_narratives()`，与新 `intelligence` 研判层功能重叠，应标记 deprecated 并在 Phase 6 下线。

---

## 3. 报告验证与失败降级审查

### 3.1 现有验证覆盖（`src/gni/reports/validate.py`）

- **已覆盖**：`report_type`、`schema_version`、`disclaimer`、必填 `sections` 键、`v1_stats` 四范围结构、`events_unique`（日/周/月报均已补齐）、`event_facts_bound`（日报）、`no_composite_score_field`、`no_forbidden_claims`（日/周/月报均已补齐）、`intelligence_status`、`intelligence_facts_evidenced`（校验所有 `Fact` 必须带 `evidence_refs`）。
- **未覆盖（对齐 V2.0 第 8.3 节缺口）**：
  1. 未校验顶层 `article_count` 与 `v1_stats.global.article_count` 严格一致；
  2. 未校验统计比例（`positive_rate + neutral_rate + negative_rate ≈ 1.0`）与 `classified_count` 分母一致；
  3. 未校验 `country_scope` 与数据源实际存在国家一致；
  4. 未校验结论引用的 `article_id` 在数据库/快照中真实存在（目前该检查在任务级 `validator.py` 中，报告顶层未做汇总核验）。

### 3.2 失败降级与“不伪造研判”检查

- **已达标**：当 `GNI_LLM_API_KEY` 未配置、预算耗尽或部分任务失败时，`runner.py` 返回 `intelligence.status` 为 `rule_only` / `partial` / `failed`，明确记录 `task_statuses[k].error_message`，整份报告仍可正常返回确定性统计与事件数据；周/月报在 `Reports.tsx` 中不会用模板句伪装成已完成研判。
- **残余隐患**：`daily.py` 的规则 `sections.summary.judgment_text` 与 `weekly.py`/`monthly.py` 的 `sections.summary.overview_text` 在 `rule_only` 状态下仍会展示给用户，需在前端明确标注「规则基线摘要（尚未执行 LLM 研判）」，杜绝与真实 LLM 研判混淆。

---

## 4. 目标统一 Report Package 契约（Phase 2 & Phase 6）

为平滑演进且**保持现有 API 完全向后兼容**，在保留原有 `sections` 字典字段的同时，于 Phase 6 引入标准化的 `report_package`（或直接升级顶层契约并保留旧键兼容别名）：

```json
{
  "report_id": "daily:2026-11-26",
  "report_type": "daily | weekly | monthly",
  "period": {
    "key": "2026-11-26",
    "start": "2026-11-25T16:00:00+00:00",
    "end": "2026-11-26T15:59:59+00:00",
    "timezone": "Asia/Shanghai"
  },
  "metric_run_id": "v1_snapshot_batch_id",
  "assessment_results": {
    "status": "completed | partial | needs_review | rule_only | failed",
    "tasks": { "...": "AssessmentResultV2" },
    "task_statuses": { "...": "TaskStatusMeta" }
  },
  "sections": [
    {
      "section_id": "executive_judgment | key_developments | global_situation | ...",
      "title": "string",
      "source_kind": "llm_assessment | deterministic_metrics | hybrid",
      "status": "completed | partial | needs_review | rule_only | failed",
      "summary": "string",
      "findings": [],
      "evidence_refs": [],
      "metrics": [],
      "limitations": []
    }
  ],
  "coverage": {
    "connected_countries": [],
    "active_sources": 50,
    "v1_analysis_coverage_rate": 0.152,
    "stance_coverage_rate": 0.68
  },
  "limitations": [],
  "generation_metadata": {
    "report_schema_version": "report_package_v2.0",
    "methodology_version": "methodology_v1.0",
    "taxonomy_version": "taxonomy_v1.0",
    "assessment_schema_version": "assessment_v2.0",
    "generated_at": "ISO-8601"
  }
}
```

公共组装逻辑抽取为 `src/gni/reports/builder.py`（共享时间窗解析、V1.0 统计加载、事件时间窗加载、任务编排调用、Report Package 装配与顶层验证），`daily.py` / `weekly.py` / `monthly.py` 仅声明各自的周期配置、章节清单与任务列表，消除重复代码。
