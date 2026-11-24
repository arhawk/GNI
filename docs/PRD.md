# 产品需求文档（PRD）

**产品：** Global Narrative Intelligence（GNI）  
**版本：** 0.4（对齐 Blueprint V4）  
**状态：** V4 口径冻结；供监测型 Phase 1 实施  
**语言：** 中文  
**设计权威：** [BLUEPRINT_V4.md](BLUEPRINT_V4.md)（**§22 及以后冲突时优先**；前文数据治理/证据/合规原则仍有效）  
**数据生命周期：** [DATA_LAYERS.md](DATA_LAYERS.md)（Raw→Normalized→Screening→AI Analysis→Intelligence）

---

## 1. 产品定位

GNI 是以 **Agent / 编排为交付核心** 的全球官方媒体对华舆情**监测**系统。

系统持续监测他国官方媒体及经审核官方传播来源，自动收集涉华报道，识别涉华内容与相关度，分析情感、Target 立场、主题与框架，计算可解释指标，发现重大新闻候选与异常，并自动生成日报/周报/月报与规则预警。

- **固定研究中心：** China（Central Target）  
- **观察样本：** 其他国家官方媒体及相关政府传播来源  
- **默认研究单元：** `Country × Source × Topic × Target × Time`（默认 Target=China）  
- **「全球」含义：** 跨国监测覆盖，≠ 全球所有议题，≠ 公众民意  

产品第一价值是**持续监测与自动交付**，不是让用户先掌握复杂研究工具。深度叙事研究保留，但**不是 MVP 首要目标**。

媒体叙事 **≠** 国家政策意图 **≠** 社会民意。

---

## 2. 目标用户与核心工作流

### 2.1 用户

国际媒体/政策研究人员、内部分析与值班监测团队。

### 2.2 默认工作流

`打开总览 / 接收提醒 → 整体对华舆情 → 国家与媒体变化 → 重点新闻/事件候选 → 代表性文章与证据 → 日报/月报 → 按需深入分析`

### 2.3 Phase 1 必须能回答

1. 近期被监测官媒如何报道中国？量与加权贡献如何？  
2. 正/负/中/混合分布（原始 + 加权）如何？  
3. 哪些国家/来源/议题/Target 驱动变化？  
4. 有哪些重大新闻候选与规则预警？为何触发？  
5. 样本覆盖与数据质量是否足以支持结论？  

### 2.4 Phase 2+ 才完整回答

- 可控 False-Merge 的跨语言事件系统、Narrative Shift 等  
- 开放式多步骤研究 Agent  

---

## 3. 范围

详见 [PRODUCT_SCOPE.md](PRODUCT_SCOPE.md)。

| 期次 | 摘要 |
|------|------|
| Phase 1 / MVP | 采集、涉华理解 + **China Relevance Weight**、7 项研究指标 + 加权/运营监测指标、规则型重大新闻候选与 Alerts、V4 Dashboard、日报/周报/月报 |
| Phase 2 | 跨语言故事、完整事件聚类、叙事变化指标、预警校准 |
| Phase 3 | 开放式研究 Agent、高级专题与 Risk 深化 |

**MVP 国家短名单：** US / RU / DE / IN / AU  
**P1-A 门槛：** ≥5 **监测国家**各 ≥1 个 verified+active 源（不以「≥5 个来源」替代）  

---

## 4. MVP 功能需求

### 4.1–4.3 来源、采集、文章理解

Registry、RSS 优先、清洗去重；**先定位涉华内容再结构化**；产出 Topic / Sentiment / Target-bound Stance / Frame / Claims·Evidence；**China Relevance Level + Weight**；允许 Unknown 等状态。摘要不得替代结构化分析。

### 4.4 指标

- **研究核心 7 项：** Article Count、Unique Story Count、Attention Share、Sentiment / Stance / Frame Distribution、Topic Share  
- **监测增补：** Weighted Article Volume、Weighted Sentiment Score/Distribution、N/P Ratio 等（见 [METRICS.md](METRICS.md)）  
- **硬约束：** 原始与加权**并列**；分母不可靠时**禁止发布正式 Attention Share**；**不做**黑盒综合总分；LLM 不得直接出正式指标数值  

### 4.5 Dashboard（V4 导航）

Overview、Countries、News & Events、Articles、Reports、Alerts、Sources & Quality、Research（后置增强）。详见 [DASHBOARD.md](DASHBOARD.md)。

### 4.6 报告与预警

日报/周报/月报模板 + 证据校验；规则型 Alerts（见 [ALERTS.md](ALERTS.md)）；P1 重大新闻为**规则/相似度候选**，非完整事件图谱。

### 4.7 Agent 边界

MVP = **确定性流水线 + 规则预警 + 模板/辅助生成报告**（可有轻量任务编排）。**开放式研究 Agent 不在 MVP。**

---

## 5. 非功能需求

可追溯、可观测、成本可控、UTC 存储、合规准入、Docker Compose 可运行、pytest。

---

## 6. 验收标准（MVP / 对齐 V4）

1. 来源可管理、审核、停用、属性有证据  
2. **≥5 监测国家**首批源可运行  
3. 采集有状态、日志、重试、健康  
4. 文章规范化、语言、时间、去重、可追溯  
5. 涉华识别 + Relevance Level/Weight（有理由、版本、置信度）  
6. Topic / Sentiment / Stance / Frame / Evidence 可运行；情感≠立场  
7. Unknown / ambiguous 等状态支持  
8. 7 项研究指标 + 原始/加权监测指标可复核；Attention Share 分母门禁  
9. Dashboard 含 Overview / Countries / News·Events 候选 / Articles / Reports / Alerts / Quality  
10. 图表可下钻至文章与原文；raw 与 weighted 并列  
11. 模型/Prompt/Schema/Taxonomy/权重规则/指标版本可追溯  
12. LLM 成本控制  
13. 日报/周报（月报模板）有证据；规则预警可去重与反馈  
14. 单篇失败不阻断批次  
15. 数据质量与舆情预警分开展示  

完整跨语言事件系统、Narrative Shift、开放式研究 Agent **不在** MVP。

---

## 7. 风险与依赖

权重误判、情感偏差、引用归因、样本结构变化、事件误合并、预警疲劳、Agent 幻觉——控制措施见 Blueprint V4 §34–35。

**依赖：** PostgreSQL、可替换 LLM、已核验 RSS/API。

---

## 8. 相关文档

- [BLUEPRINT_V4.md](BLUEPRINT_V4.md) · [PHASE0_REPOSITORY_AUDIT_V4.md](PHASE0_REPOSITORY_AUDIT_V4.md)  
- [PRODUCT_SCOPE.md](PRODUCT_SCOPE.md) · [METRICS.md](METRICS.md) · [DASHBOARD.md](DASHBOARD.md) · [ALERTS.md](ALERTS.md) · [PHASE1_TASK_BRIEF.md](PHASE1_TASK_BRIEF.md)  
