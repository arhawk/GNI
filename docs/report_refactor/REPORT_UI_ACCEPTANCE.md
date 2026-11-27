# GNI 报告前端与可视化验收文档（Task 5）

## 1. 组件清单与架构变更

| 文件 | 职责 | 状态 |
|---|---|---|
| `web/src/api.ts` | 补齐 `ReportWindowSpec`、`ReportQualityGate`、`ReportVisualizations` 类型，支持 `engine: 'orchestrator'` | 已更新 |
| `web/src/components/reports/ReportVisualizations.tsx` | 纯 SVG/CSS 数据驱动组件：`QualityGateBanner`、`WindowSpecBadge`、`TrendLineChart`、`CountryBarChart`、`TopicDeltaChart`、`StanceStackedBar`、`EventTimelineList`、`ReportVisualDashboard`（零额外臃肿图表库） | 新增 |
| `web/src/components/reports/ReportViewChrome.tsx` | 独立视图外壳：`DailyReportViewChrome`、`WeeklyReportViewChrome`、`MonthlyReportViewChrome`、`ReportExportBar`（Markdown 导出）、`CuratedEvidencePanel`（精选证据折叠面板） | 新增 |
| `web/src/pages/Reports.tsx` | 接入三类独立视图外壳、默认使用 `orchestrator` 引擎触发研判、完整保留右上角正方形日历浮层（`ReportCalendarPopover`） | 已更新 |
| `web/src/components/DailyReportPackageView.tsx` | 零引用的废弃占位视图 | 已删除 |

## 2. 统计口径与交互验收核对

- **数据驱动**：所有 5 类图表均严格消费后端 `payload.visualizations` 真实数据，空数据返回清晰空态提示。
- **统计口径零篡改**：
  - `StanceStackedBar` 显式单列 `Unclassified` 计数并注明“不计入比例分母”，右上角始终展示 `stance_coverage_rate`。
  - `TopicDeltaChart` 独立展示各议题文章数与环比 Δ，不将跨议题重叠计数错误堆叠为总量。
  - 日报不渲染重点事件时间线；周报/月报 `EventTimelineList` 渲染事件时间：优先 `event_time`（actual），缺失时以最早发布时间作为代理时间（`proxy_published_at`，Proxy Event Time）并标注“代理：最早发布时间”。
- **门禁与周期提示**：`QualityGateBanner` 区分三态（`passed` / `passed_with_warnings` / `blocked`），`WindowSpecBadge` 在月中/进行中周期醒目标注 MTD 公平环比。

## 3. 构建与 Lint 验证

- `cd web && npm run build`（`tsc -b && vite build`）：**0 errors**（288ms 构建通过）。
- `cd web && npm run lint`（`oxlint`）：**0 errors**，新增组件 0 warnings。
