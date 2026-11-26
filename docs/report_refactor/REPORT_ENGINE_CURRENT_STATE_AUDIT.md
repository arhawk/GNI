# GNI 报告系统现状审计报告（Current State Audit）

> 审计日期：2026-11-26（Asia/Shanghai）  
> 性质：只读现状审计，未修改任何业务代码、数据库结构或 API 契约。

## 1. 仓库状态与运行环境

| 项目 | 当前真实状态 |
|---|---|
| Git 分支 | `main` |
| HEAD Commit | `6623f361d5211d918287f006ff4a3bc3f1fd607a`（`6623f36`） |
| 工作区状态 | 干净（无未提交修改） |
| Python 环境 | Python `3.14.6`（`.venv/bin/python`，`pytest 9.2.0`） |
| Node / 前端环境 | Node `v20.20.2`，npm `10.8.2`（Vite 8 + React + TypeScript） |

近期与报告系统直接相关的提交：
- `6623f36` `fix: remove ops telemetry and debug JSON from reports, fix weekly section numbering`
- `8140fb2` `feat: switch reports calendar to right-side popover with day/month views`
- `4f5eb36` `feat: add reports calendar, compact time window, and priority analysis queue`
- `1bcdf7f` `Remove daily report media sentiment and align top KPI strip`
- `9d47a56` `feat(phase7): decouple API routers and build 9-view intelligence presentation layer`

## 2. 本次审计覆盖的代码范围

- **API 路由层**：`src/gni/api/routers/reports.py`、`src/gni/api/routers/common.py`
- **报告组装层**：`src/gni/reports/daily.py`、`src/gni/reports/daily_package.py`、`src/gni/reports/weekly.py`、`src/gni/reports/monthly.py`、`src/gni/reports/validate.py`
- **研判与缓存层**：`src/gni/reports/narrative/runner.py`、`src/gni/reports/narrative/prompts.py`、`src/gni/reports/narrative/evidence.py`、`src/gni/reports/narrative/schemas.py`、`src/gni/reports/narrative/validator.py`、`src/gni/reports/narrative/assessment.py`
- **数据模型与契约**：`src/gni/core/contracts.py`、`src/gni/infrastructure/models.py`（`ReportNarrativeTask`、`ReportSnapshot`）
- **前端消费层**：`web/src/api.ts`、`web/src/pages/Reports.tsx`、`web/src/components/DailyReportPackageView.tsx`、`web/src/components/narrative/*`、`web/src/components/tables/*`
- **测试层**：`tests/unit/test_report_narrative_layer.py`、`tests/unit/test_phase6_daily_report_package.py`、`tests/unit/test_priority_analyze_and_calendar.py`

## 3. 真实调用链全景

### 3.1 API 入口（`src/gni/api/routers/reports.py`）

| 端点 | 函数 | 实际调用链路 |
|---|---|---|
| `GET /api/reports/daily` | `api_daily_report` (L73-93) | 可选读 `ReportSnapshot`（`from_snapshot=true`），默认调用 `build_daily_report(session, day=date, polish=polish)`（`analyze=False`），返回含 `intelligence`（仅缓存读）和 `report_package` 的混合 payload。 |
| `GET /api/reports/daily/package` | `api_daily_report_package` (L96-118) | 调用 `build_daily_report(..., analyze=False)` 并提取 `payload["report_package"]`，支持 `format=json|markdown`（经 `render_daily_brief_markdown`）。 |
| `GET /api/reports/weekly` | `api_weekly_report` (L121-129) | 调用 `build_weekly_report(session, end_day=end)`（`analyze=False`，仅读 Legacy 缓存）。 |
| `GET /api/reports/monthly` | `api_monthly_report` (L195-204) | 调用 `build_monthly_report(session, month=month, end_day=end)`（`analyze=False`，仅读 Legacy 缓存）。 |
| `GET /api/reports/calendar` | `api_reports_calendar` (L132-192) | 按 `Asia/Shanghai` 聚合当月每日非排除文章数 `total_articles` 与 `china_articles`。 |
| `POST /api/reports/{report_type}/analyze` | `api_analyze_report` (L207-249) | `daily` 支持 `engine="legacy"`（默认，3 任务）或 `engine="v2"`（9 任务 Canonical）；`weekly` 与 `monthly` **仅**支持 Legacy 6 任务，忽略 `engine` 参数。 |
| `GET /api/reports/list` | `api_reports_list` (L43-69) | 查询 `ReportSnapshot` 列表。 |

### 3.2 四条核心生成路径对比

1. **Daily 旧版路径（V4 + Legacy 3 任务）**：
   - `build_daily_report()` (`src/gni/reports/daily.py`) 计算 V1.0 确定性指标（`run_v1_stat_snapshots`）、事件与异动 → `analyze=True` 时调用 `run_report_intelligence()` (`src/gni/reports/narrative/runner.py:317`) 执行 3 个 Legacy 任务（`executive_analysis`、`event_analysis`、`emerging_signals`）；`analyze=False` 时调用 `load_cached_intelligence()` (`runner.py:139`) 仅读取缓存。
2. **Daily 新版路径（Report Package V2 + Canonical 9 任务）**：
   - `build_daily_report(..., run_v2_assessments=True)` 调用 `run_assessment_suite()` (`src/gni/reports/narrative/assessment.py:699`) 执行 9 类 Canonical Assessment 任务，再由 `build_daily_report_package()` (`src/gni/reports/daily_package.py`) 组装为 6 章 + 附录的 `ReportPackageContract` 并挂载到 `payload["report_package"]`。
   - 即使 `run_v2_assessments=False`，`daily_package.py:_pick_assessments` (L137-150) 也会尝试从 `ReportNarrativeTask` 读取已缓存的 V2 结果，或通过 `_adapt_legacy_intelligence_task` (L90-134) 将 Legacy 3 任务适配填充到 6 章中。
3. **Weekly 路径**：
   - `build_weekly_report()` (`src/gni/reports/weekly.py`) 计算近 7 日与前 7 日文章级 V1.0 统计、近 4 周序列、事件演化 → 调用 `run_report_intelligence()` (L434) 执行 6 个 Legacy 任务。**未接入** Canonical Assessment Engine，也**未输出** `ReportPackageContract`。
4. **Monthly 路径**：
   - `build_monthly_report()` (`src/gni/reports/monthly.py`) 计算自然月或滚动 30 天文章级 V1.0 统计、近 6 个月序列、国别画像与叙事格局 → 调用 `run_report_intelligence()` (L471) 执行 6 个 Legacy 任务。**未接入** Canonical Assessment Engine，也**未输出** `ReportPackageContract`。

### 3.3 前端实际消费现状（`web/src/pages/Reports.tsx`）

- **Daily 页**：当前直接渲染 `DailyBrief`（V4 统计明细 + Legacy `intelligence.tasks` 卡片），已在提交 `4f5eb36` 中移除 `DailyReportPackageView` 切换入口（组件文件 `web/src/components/DailyReportPackageView.tsx` 仍留在仓库中但无页面引用）。
- **Weekly / Monthly 页**：共用 `PeriodBrief`，消费 `sections.v1_stats`、`historical_v1_stats`、`event_evolution`、`country_profiles` 及 Legacy `intelligence.tasks`（6 任务）。
- **交互日历**：右上角正方形浮层日历（`ReportCalendarPopover`，提交 `8140fb2`）消费 `GET /api/reports/calendar`，点击日期 `D` 联动请求 `daily?date=D`、`weekly?end=D`、`monthly?end=D`。
- **可视化现状**：`/reports` 目前全部以表格（`StanceMatrixTable`、`TrendDeltaTable`、`EventRiskTable`）与文字卡片呈现，尚未渲染趋势折线图/堆叠柱图等图表组件。

## 4. 核心审计结论（已实现 / 部分实现 / 未实现）

- **已实现**：文章级 V1.0 确定性统计口径（Article Count、多议题重叠、Unclassified 独立与 coverage rate）、9 类 Canonical Assessment 统一执行框架（单引擎非多 Agent）、三层校验器（`validator.py`）、Daily `ReportPackageContract` 组装与 Markdown 导出、前端交互日历与精简日报/周报/月报视图。
- **部分实现**：
  - Legacy 与 Canonical 两套研判体系并存，共享 `ReportNarrativeTask` 表但仅 Daily 接入了 Canonical，Weekly/Monthly 仍停留在 Legacy。
  - 缓存键缺少 `model_version`、`schema_version`、`methodology_version`、`taxonomy_version`。
- **未实现**：
  - 统一的 Report Orchestrator（跨 Daily/Weekly/Monthly 统一编排器与任务 Profile）。
  - Weekly / Monthly 的 `ReportPackageContract` 契约与 Markdown 导出。
  - 月报自然月模式下的月中不完整月份公平对比机制。
  - `/reports` 页面的结构化趋势可视化图表。
