# UPDATED_GAP_ANALYSIS.md — Batch 3（Phase 5–6）完成后的最新差距分析

> 分支：`cursor/data-trust-batch1` | 日期：2026-11-26 | 对比基线：Batch 1–2（`ceeca01`）

## 1. Batch 3 新关闭的 P0 / P1 缺口

| 原缺口项 | 原状态 | 现状态 | 解决方式 |
|---|---|---|---|
| 缺少任务级统一 `EvidencePackageContract` 构建器（未衔接文章级偏移、`changes.py`、`NarrativeCluster`） | `partially_implemented` | `implemented` | `evidence.py:build_task_evidence_package()` 实现按任务裁剪、原文偏移追溯与正反证分离 |
| 研判层仅覆盖 4 类旧任务，缺少统一 9 类研判任务执行框架与 Fact/Inference/Hypothesis 分离输出 | `partially_implemented` | `implemented` | 新增 `assessment.py` 统一框架落地 9 类任务 + `AssessmentResultContract` + 协调传播/量=风险校验护栏 |
| 日报未封装为统一 6 章+附录 `ReportPackageContract`，缺少报告级校验与快照重生成闭环 | `partially_implemented` | `implemented` | 新增 `daily_package.py` 接入 `build_daily_report()`、`ReportSnapshot` 保存/查询/重生成与 `/api/reports/daily/analyze` (`engine="v2"`) |

## 2. 剩余缺口与后续批次归属

| 优先级 | 缺口项 | 当前状态 | 归属阶段 | 说明 |
|---|---|---|---|---|
| P0 | 本地数据库历史存量文章（约 84.8%）仍为 `v0.1` 旧版分析结果 | `blocked`（待运营执行） | 数据回填 | 需确认预算后运行 `gni analyze run --reanalyze-legacy` |
| P1 | Weekly Intelligence Report 与 Monthly Strategic Review 尚未迁移至 `ReportPackageContract` | `partially_implemented` | 下一批次（Reporting 扩展） | 现有 `weekly.py`/`monthly.py` 正常运行；已预留 `ReportPackageContract(report_type="weekly"\|"monthly")` |
| P1 | React 前端页面与 API 尚未全面展示 `report_package` 6 章结构、证据原文高亮偏移、反证对比与人工审核（Feedback & Governance UI） | `not_implemented` | Phase 7–8 | 现有前端通过旧字段完全兼容，待审核后启动前端信息架构与治理界面改造 |
| P1 | `events/service.py -> gni.dashboard.data` 最后 1 处遗留反向依赖 | `partially_implemented` | Phase 7 | 已在 `test_imports.py` 登记唯一白名单，待 API 层解耦清理 |
| P2 | 上游 `processing` 偶发语种误标（印地语标为 `en`）与超长 Liveblog 议题串扰 | `partially_implemented` | 后续数据质量优化 | 不阻断当前主链路，保留在技术债务清单 |
| P2 | 既有 `tests/unit/test_editorial_focus.py` 2 项历史失败 | `not_implemented` | 独立维护 | 由历史 `sources.yaml` 扩充导致，非 Batch 1–3 引入 |
