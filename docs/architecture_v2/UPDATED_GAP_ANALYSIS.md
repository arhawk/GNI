# UPDATED_GAP_ANALYSIS.md — Batch 4（Phase 7）完成后的最新差距分析

> 分支：`cursor/data-trust-batch1` | 日期：2026-11-26 | 对比基线：Batch 3（`94fa71f`）

## 1. Batch 4 新关闭的 P0 / P1 缺口

| 原缺口项 | 原状态 | 现状态 | 解决方式 |
|---|---|---|---|
| `events/service.py -> gni.dashboard.data` 最后 1 处遗留跨层反向依赖 | `partially_implemented` | `implemented`（已清零） | `overview_payload` 迁移至 `src/gni/dashboard/overview.py`，移除 `test_imports.py` 白名单 |
| 单体 `api/app.py` 缺少 Dashboard/Reports/Assessments/Topics/Countries Compare/Narratives/Sentiment&Stance/Outlook/Articles/Evidence 领域接口 | `not_implemented` | `implemented` | 拆分为 9 个 FastAPI 领域路由并保持旧路由 100% 兼容 |
| 前端缺少 9 视图情报信息架构、6 章日报 `ReportPackage` 视图与全局原文偏移高亮证据追溯 | `not_implemented` | `implemented` | 新增/升级 9 个页面 + `DailyReportPackageView` + 全局 `EvidenceDrawer` |
| 历史 `v0.1` 字符串型 `sentiment`/`framing` 导致 `/api/trends` 与 `/api/events/{id}` 报错 | 新发现缺陷 | `implemented`（已修复） | 在 `dashboard/pages_api.py` 与 `events/service.py` 增强类型容错 |

## 2. 剩余缺口与归属阶段（诚实区分）

| 优先级 | 缺口项 | 当前状态 | 归属阶段 | 说明 |
|---|---|---|---|---|
| P0 | 本地库历史存量文章（~84.8%）仍为 `v0.1`，导致真实库 `stance_coverage_rate` 偏低且 `narrative_clusters` 为空 | `blocked`（待运营执行） | 数据回填 | 需确认预算后运行 `gni analyze run --reanalyze-legacy` 与叙事聚簇 |
| P1 | Weekly / Monthly 报告尚未迁移至统一 `ReportPackageContract` 与 6 章结构 | `partially_implemented` | Reporting 扩展 | 现有周报/月报 API 与 UI 保持运行 |
| P1 | Phase 8：人工反馈审核工作流、治理管理后台、`POST /api/events/{id}/split` 的前端操作入口、模型评估与历史研判回溯 | `not_implemented`（API 局部预留） | Phase 8 | 本批次严格按边界暂停，未提前实施 |
| P2 | 前端缺少 Vitest 组件单测与 Playwright 端到端浏览器自动化测试 | `not_implemented` | 前端测试专项 | 当前已覆盖 `tsc -b` + `vite build` + `oxlint` + 后端 6 流程实库测试 |
| P2 | 既有 `tests/unit/test_editorial_focus.py` 2 项历史失败 | `not_implemented` | 独立维护 | 与 Batch 1–4 无关 |
