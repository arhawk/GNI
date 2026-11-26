# INTELLIGENCE_EXPLORER_IMPLEMENTATION.md — 专题分析页与证据文章浏览器实施报告

> 日期：2026-11-26 | 覆盖视图：Event Analysis、Topic Analysis、Country Comparison、Narrative Analysis、Sentiment & Stance、Outlook & Watchlist、Evidence & Article Explorer

## 1. 七大专题与追溯视图实现

1. **Event Analysis**（[web/src/pages/EventDetail.tsx](web/src/pages/EventDetail.tsx) + `GET /api/events/{id}`）：
   - 6 个结构化 Tab：地理与叙事、**事件时间线（严格 `event_time`，未知标示「时间未知」，与 `published_at` 媒体发布序列分列）**、媒体报道、跨国报道差异（含小样本徽标）、事件研判、原文证据片段。
2. **Topic Analysis**（[web/src/pages/Topics.tsx](web/src/pages/Topics.tsx) + `GET /api/topics` / `GET /api/topics/{id}`）：
   - 围绕四大板块 × 十五固定议题展示文章量、占全球比例、周期变化、每日趋势、国别分布、驱动事件、参与媒体、代表叙事与文章列表，显式声明多议题重叠口径。
3. **Country Comparison**（[web/src/pages/Countries.tsx](web/src/pages/Countries.tsx) + `GET /api/countries/compare`）：
   - 支持多国勾选并排比较报道量、环比变化、媒体覆盖、情感分布、对华立场分布（含覆盖率与 `Unclassified` 剔除说明）、关注议题、重点事件与代表文章；文章数 < 10 或已分类立场 < 5 时强制显示 `PartialDataBanner` 样本警告。
4. **Narrative Analysis**（[web/src/pages/Narratives.tsx](web/src/pages/Narratives.tsx) + `GET /api/narratives`）：
   - 展示叙事 ID、名称、Core Claim、主框架、状态、涉及国家/议题、首次/最近出现时间、支撑证据与反例，顶部常驻「多国同时报道不构成协调传播」声明。
5. **Sentiment & Stance Analysis**（[web/src/pages/SentimentStance.tsx](web/src/pages/SentimentStance.tsx) + `GET /api/sentiment-stance`）：
   - 左右分栏严格分离 China Stance（`target="china_mainland"`、`Stance Coverage Rate`、`Unclassified` 不入比例分母、`media` vs `quoted_actor`）与 Sentiment（文章情感表达）。
6. **Outlook & Watchlist**（[web/src/pages/Outlook.tsx](web/src/pages/Outlook.tsx) + `GET /api/outlook`）：
   - 结构化条件展望卡片（观察对象、当前证据、可能发展、触发条件、替代情景、不确定性），并按 `Fact` / `Inference` / `Hypothesis` 三栏分离，附带「非确定性预测」声明与一键触发 `outlook_assessment`。
7. **Evidence & Article Explorer**（[web/src/pages/Explorer.tsx](web/src/pages/Explorer.tsx)、[web/src/pages/ArticleDetail.tsx](web/src/pages/ArticleDetail.tsx)、[web/src/components/EvidenceDrawer.tsx](web/src/components/EvidenceDrawer.tsx)）：
   - 支持按关键词、国家、媒体、议题、情感、立场、时间、事件/叙事筛选，按 `published_at` 倒序分页；点击任意研判/报告中的 Evidence Ref 可在侧栏抽屉或文章详情页高亮原文偏移片段并展示数据来源与限制。
