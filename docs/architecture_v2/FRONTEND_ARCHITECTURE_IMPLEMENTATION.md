# FRONTEND_ARCHITECTURE_IMPLEMENTATION.md — Phase 7 前端情报展示架构实施报告

> 分支：`cursor/data-trust-batch1` | 日期：2026-11-26 | 技术栈：React 19.3 + TypeScript + Vite 8 + React Router 7 + MapLibre GL 6

## 1. 架构原则与复用策略

- **零框架替换 / 零多余依赖**：完全复用既有 React 19 + Vite 8 + `react-router-dom` + `maplibre-gl` + 原生 CSS 变量体系（`web/src/App.css`、`web/src/components/intel.css`），构建产物仅 422 kB（gzip 120 kB），`tsc -b && vite build` 耗时 294ms。
- **前端零正式指标重算**：所有统计口径（`Article Count`、`Stance Coverage Rate`、正中负比例、4 大板块 × 15 议题、国别归属）均直接消费后端确定性 API，前端不做二次重算或近似估算。
- **统一 API 客户端**：新增 [web/src/apiV2.ts](web/src/apiV2.ts) 并在 [web/src/api.ts](web/src/api.ts) 重导出，集中管理 TypeScript 契约与错误提取，保持全部旧页面调用 100% 兼容。

## 2. 九大目标视图与路由映射

| # | 目标视图 | 路由 | 页面组件 | 状态 |
|---|---|---|---|---|
| 1 | Global Intelligence Dashboard | `/` | [web/src/pages/Overview.tsx](web/src/pages/Overview.tsx) | 已完成并运行（前后端打通） |
| 2 | Daily Intelligence Report | `/reports` | [web/src/pages/Reports.tsx](web/src/pages/Reports.tsx) + [web/src/components/DailyReportPackageView.tsx](web/src/components/DailyReportPackageView.tsx) | 已完成并运行（Daily 6 章+附录；Weekly/Monthly 保留旧视图） |
| 3 | Event Analysis | `/events`, `/events/:id` | [web/src/pages/Events.tsx](web/src/pages/Events.tsx), [web/src/pages/EventDetail.tsx](web/src/pages/EventDetail.tsx) | 已完成并运行 |
| 4 | Topic Analysis (4×15) | `/topics` | [web/src/pages/Topics.tsx](web/src/pages/Topics.tsx) | 已完成并运行 |
| 5 | Country Comparison | `/countries` | [web/src/pages/Countries.tsx](web/src/pages/Countries.tsx) | 已完成并运行 |
| 6 | Narrative Analysis | `/narratives` | [web/src/pages/Narratives.tsx](web/src/pages/Narratives.tsx) | 已完成并运行（真实库待聚簇后显示完整数据） |
| 7 | Sentiment & Stance Analysis | `/stance` | [web/src/pages/SentimentStance.tsx](web/src/pages/SentimentStance.tsx) | 已完成并运行 |
| 8 | Outlook & Watchlist | `/outlook` | [web/src/pages/Outlook.tsx](web/src/pages/Outlook.tsx) | 已完成并运行 |
| 9 | Evidence & Article Explorer | `/explorer`, `/articles/:id` | [web/src/pages/Explorer.tsx](web/src/pages/Explorer.tsx), [web/src/pages/ArticleDetail.tsx](web/src/pages/ArticleDetail.tsx) | 已完成并运行 |

## 3. 全局可复用组件与状态规范

- **全局证据追溯抽屉**：[web/src/components/EvidenceContext.tsx](web/src/components/EvidenceContext.tsx) + [web/src/components/EvidenceDrawer.tsx](web/src/components/EvidenceDrawer.tsx)，在 `App.tsx` 顶层挂载，任意研判、报告章节、事件、叙事或 `EvidenceChips` 中的证据按钮均可一键呼出并高亮原文 `start_offset`/`end_offset`。
- **统一状态组件**：[web/src/components/StateBlocks.tsx](web/src/components/StateBlocks.tsx) 提供 `LoadingState`、`EmptyState`、`ErrorState`、`PartialDataBanner`、`SampleSizeBadge`、`ClassificationBadge`（`Fact`/`Inference`/`Hypothesis`/`Outlook`）、`StanceBadge`、`StanceBar`。
- **未实现/保留给 Phase 8**：人工反馈审核工作流、治理管理后台与模型质量评估面板未提前实施。
