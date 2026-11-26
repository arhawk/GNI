# Legacy 研判路径退场计划（Legacy Path Deprecation Plan）

1. **当前阶段（Task 2 已完成）**：
   - Daily/Weekly/Monthly 均已接入 `ReportOrchestrator`（`engine="v2"|"canonical"|"orchestrator"`）。
   - `runner.py:run_report_intelligence()` 仅在显式请求 `engine="legacy"` 时保留作为回退路径；所有只读查询优先命中 Canonical 缓存并兼容读取历史 Legacy 缓存。
2. **下阶段（Task 3–4 完成后）**：
   - 将 `/api/reports/{daily|weekly|monthly}/analyze` 默认 `engine` 切换为 `canonical`，仅保留显式 `engine="legacy"` 回退开关。
3. **退场条件（Task 6 验收后）**：
   - 三类报告前端全部切换至 `ReportPackageContract` 与 Canonical 输出，且连续 7 天生产运行无回退需求后，可将 `runner.py` 标记为 deprecated 并计划移除。
