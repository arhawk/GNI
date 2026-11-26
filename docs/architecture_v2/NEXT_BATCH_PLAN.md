# NEXT_BATCH_PLAN.md — 下一批次（Batch 5: Phase 8 治理、反馈与质量评估体系）实施建议

> 当前状态：Batch 4（Phase 7 API 解耦与前端情报展示层）已完成并暂停，等待人工验收确认后再启动 Batch 5。

## 建议的 Batch 5（Phase 8）实施路线

### 1. 人工反馈与治理闭环（Human-in-the-Loop & Governance UI）
- 为 `EventRevision`（`lock` / `merge` / 已有 API 的 `split`）提供前端治理操作面板与审计历史展示。
- 增加 `needs_review` 研判任务与异常文章的复核队列，支持 `record_source="human_override"` 修正立场、议题与事件归属并留痕。

### 2. 模型评估与历史研判回溯（Evaluation & Audit）
- 建立黄金测试集（Golden Set）与离线评测脚本，定期统计文章立场准确率、原文偏移核验率、研判三层校验通过率与 Prompt 版本对比。
- 在系统管理页增加历史 `ReportSnapshot` / `ReportNarrativeTask` 成本、延迟、校验失败原因的趋势回溯视图。

### 3. Reporting 扩展与前端自动化测试
- 将 Weekly Intelligence Report 与 Monthly Strategic Review 迁移至统一 `ReportPackageContract`。
- 为 `web/` 引入 Vitest + Testing Library（或 Playwright）对 6 条核心用户流程建立浏览器级回归测试。

### 4. 运营数据回填建议
- 在确认 API 预算后分批执行 `gni analyze run --reanalyze-legacy`，提升真实库 `stance_coverage_rate` 并生成 `NarrativeCluster` 真实样本，使 Narrative Analysis 页面呈现完整跨国叙事演化。
