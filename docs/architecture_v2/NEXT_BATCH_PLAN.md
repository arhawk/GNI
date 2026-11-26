# NEXT_BATCH_PLAN.md — 下一批次（Batch 4: Phase 7–8 及周报/月报对齐）实施建议

> 当前状态：Batch 3（Phase 5 Assessment Engine & Phase 6 Daily Intelligence Brief）已完成并暂停，等待人工验收确认后再启动以下工作。

## 建议的 Batch 4 实施路线

### 1. Reporting Engine 扩展（Weekly & Monthly 对齐 `ReportPackageContract`）
- 复用 `daily_package.py` 的章节组装与 `validate_report_package()` 模式，将 `weekly.py` 与 `monthly.py` 接入统一 `ReportPackageContract` + 历史趋势证据包（调用 `get_historical_trend()`）。
- 补齐周报（解释变化）与月报（结构演化）在 `assessment.py` 下的多周期基线对比与 `ReportSnapshot` 持久化。

### 2. Phase 7 — API 契约完善与遗留跨层解耦
- 将 `events/service.py` 中的 `overview_payload()` 迁移至 `dashboard/` 或 `api/` 层，彻底清除 `tests/unit/test_imports.py` 中的最后 1 处白名单耦合。
- 新增面向前端的只读与操作端点（保持旧端点 100% 兼容）：
  - `GET /api/reports/daily/package`（或直接消费 `GET /api/reports/daily` 中的 `report_package`）与 Markdown 导出端点；
  - `GET /api/articles/{id}/intelligence` 暴露 `ArticleIntelligenceContract`（含 `expression_owner`、已核验原文偏移、`quality_flags`）；
  - `POST /api/events/{id}/split` 暴露已实现的 `split_event()` 与 `EventRevision` 审计查询。

### 3. Phase 8 — 前端信息架构与可追溯展示（Web UI）
- 在 `web/` React 日报页增量展示 6 章结构、`Fact / Inference / Hypothesis / Outlook` 徽标、确定性指标卡与 LLM 研判区块视觉隔离、反证（`counter_evidence`）折叠面板与原文偏移高亮抽屉。
- 引入轻量人工复核（`needs_review` 队列、`record_source="human_override"` 修订闭环）。

### 4. 运营建议（审核通过后可执行）
- 使用 DeepSeek API Key 对真实日报窗口试跑一次 `POST /api/reports/daily/analyze`（`engine="v2"`, `save_snapshot=true`），抽检 9 类任务的真实中文输出与三层校验日志。
- 按批次运行 `gni analyze run --reanalyze-legacy --limit 100` 逐步提升本地库 V1.0+ 立场覆盖率。
