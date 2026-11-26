# REPORT_UI_IMPLEMENTATION.md — Daily Intelligence Report 展示层实施报告

> 路由：`/reports` | 组件：[web/src/components/DailyReportPackageView.tsx](web/src/components/DailyReportPackageView.tsx)、[web/src/pages/Reports.tsx](web/src/pages/Reports.tsx) | 后端：[src/gni/api/routers/reports.py](src/gni/api/routers/reports.py)

## 1. 六章 + 附录阅读体验

- **阅读顺序**：每章严格遵循 `Conclusion (summary) → Key Findings (带 Fact/Inference/Hypothesis 徽标) → Evidence (一键打开全局 EvidenceDrawer) → Supporting Metrics (折叠展示) → Limitations`。
- **完整 7 章节结构**：直接渲染后端 `ReportPackageContract.sections`（Chapter 1 Executive Judgment 至 Chapter 6 Outlook & Watchlist + Appendix）。
- **交互能力**：
  - 支持单章展开/收起（默认展开第 1–2 章以保证 3–5 分钟快速阅读）；
  - 支持从 `GET /api/reports/list` 切换历史已保存的 `ReportSnapshot`；
  - 支持一键触发 `POST /api/reports/daily/analyze`（`engine="v2"`, `save_snapshot=true`）及强制重生成；
  - 支持一键查看/导出 `GET /api/reports/daily/package?format=markdown` 生成的规范 Markdown 日报；
  - 保留「经典统计明细视图 (V4)」切换与 Weekly / Monthly 标签页 100% 兼容。

## 2. 实现状态区分

- Daily 6 章 + 附录 UI + 快照切换 + V2 研判触发 + Markdown 预览：**已完成并运行**。
- Weekly / Monthly 报告页面：保留既有 `PeriodBrief` 运行，迁移至 `ReportPackageContract` 属于后续扩展批次。
