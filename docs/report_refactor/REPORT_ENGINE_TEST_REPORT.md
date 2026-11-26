# 报告系统测试现状与缺口报告（Test Report）

> 执行时间：2026-11-26（只读测试运行）  
> 测试命令：`.venv/bin/pytest tests/unit/test_report_narrative_layer.py tests/unit/test_phase6_daily_report_package.py tests/unit/test_priority_analyze_and_calendar.py -v`

## 1. 已有测试运行结果（真实基线）

| 测试文件 | 用例数 | 结果 | 覆盖内容 |
|---|---|---|---|
| `tests/unit/test_report_narrative_layer.py` | 6 | **6 PASSED** | Daily/Weekly/Monthly prompt 区分、三层校验器（数值/证据/推理）、`evidence_ref` 简写兼容、三类报告缓存/重试/降级 E2E、`/api/reports/*` 路由与 `/analyze` 触发、证据裁剪 |
| `tests/unit/test_phase6_daily_report_package.py` | 3 | **3 PASSED** | Daily 6 章 `ReportPackageContract` E2E + 快照 + Markdown 导出、零数据日边界（`insufficient_data`）、Daily API 与 `engine="v2"` 兼容性 |
| `tests/unit/test_priority_analyze_and_calendar.py` | 3 | **3 PASSED** | `_select_articles_for_analysis` 涉华优先级与最新时间排序、`build_monthly_report(end_day=...)` 滚动 30 天窗口、`GET /api/reports/calendar` 时区聚合 |
| **合计** | **12** | **12 PASSED (1.86s)** | 无失败用例（含 3 条 FastAPI/Starlette 弃用 warning） |

## 2. 测试缺口清单（当前未覆盖）

1. **Weekly / Monthly Canonical 编排与 Report Package 测试**：当前无任何测试覆盖 Weekly/Monthly 运行 Canonical 9 任务或产出 `ReportPackageContract`。
2. **缓存键版本失效测试**：缺少“切换 `model_version` / `methodology_version` / `taxonomy_version` 后自动失效旧缓存”的单元测试。
3. **月报月中不完整月份对比测试**：缺少在自然月月中（如 11 月 15 日）生成月报时 `is_partial_period` 标记与 MTD 对齐环比的测试。
4. **周报边界与跨年/跨月测试**：缺少 `_week_window` 跨年（如 `2026-01-03`）、夏令时/时区边界以及空周回退测试。
5. **反证与统计口径守卫测试**：
   - 缺少“LLM 输出编造未在输入出现的百分比/文章数时被拦截为 `needs_review`”的跨 Weekly/Monthly 回归测试。
   - 缺少“Unclassified 计入总量但不进正/中/负比例分母，且必须输出 `stance_coverage_rate`”的报告级端到端断言。
6. **前端组件与交互测试**：`web/` 目前仅有 `tsc -b && vite build` 与 `oxlint` 静态检查，尚无 `Reports.tsx` / `ReportCalendarPopover` 的单元测试或 E2E 渲染测试。

## 3. 可复现问题记录

- **问题 A（已复现）**：对 `POST /api/reports/weekly/analyze` 或 `monthly/analyze` 传入 `{"engine": "v2"}` 时，路由层（`src/gni/api/routers/reports.py:229-247`）直接忽略 `engine` 参数，仍执行 Legacy 6 任务。
- **问题 B（已复现）**：在 `ReportNarrativeTask` 已有缓存的情况下，仅变更 `GNI_LLM_MODEL` 而不改 `prompt_version` 与数据时，`run_assessment_task()`（`assessment.py:564-574`）会直接命中旧模型生成的缓存。
- **问题 C（已复现）**：在 11 月中旬调用 `GET /api/reports/monthly?month=2026-11` 时，当月不完整天数直接与上月完整 31 天做减法得出负 `delta`，且 `historical_v1_stats` 未标识当月为不完整月。
