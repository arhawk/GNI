# 产品需求文档（PRD）

**产品：** Global Narrative Intelligence（GNI）  
**版本：** 0.1（Phase 0 冻结）  
**状态：** 已冻结，供 Phase 1 实施依据  
**语言：** 中文

---

## 1. 产品定位

GNI 是**全球官方媒体舆论信号采集与叙事监测研究系统**。

核心价值不是「新闻聚合 + LLM 摘要」，而是：

1. 可管理、可审计的跨国官方来源体系  
2. 可验证的文章级结构化分析（主题 / 情感 / 立场 / 框架 / 证据）  
3. 可比较的统计口径（分母、时区、去重、样本范围公开）  
4. 长期可扩展到事件级与叙事级分析，以及证据驱动的研究 Agent  

媒体叙事 **≠** 国家政策意图 **≠** 社会民意。系统不得把报道直接解释为国家决策或全民观点。

---

## 2. 目标用户与核心问题

### 2.1 用户

- 国际媒体叙事研究人员  
- 政策 / 战略分析人员  
- 内部研究团队  

### 2.2 核心问题（MVP 必须能回答）

1. 某周/某月，短名单国家官方媒体主要关注中国哪些议题？  
2. 不同国家对同一议题的情感、立场、叙事框架有何差异？  
3. 关注度上升是原创增加还是转载增加？（MVP 先区分精确重复与单语言近重；跨语言转载 Phase 2）  
4. 对某一 Stance Target（如 Chinese Technology Industry）的立场分布如何？  
5. 当前样本是否足以支持结论？来源覆盖是否偏斜？  

### 2.3 Phase 2+ 才完整回答的问题

- 同一事件下各国叙事如何分化？  
- 相对历史基线是否出现 Narrative Shift？  
- 自然语言多步骤专题研究  

---

## 3. 范围

详见 [PRODUCT_SCOPE.md](PRODUCT_SCOPE.md)。

| 期次 | 摘要 |
|------|------|
| Phase 1 / MVP | 采集入库、文章分析、基础指标、Dashboard、日报周报、质量与成本面板 |
| Phase 2 | 跨语言转载、事件聚类、叙事漂移与基线异常 |
| Phase 3 | 研究 Agent、证据验证增强、可配置综合指数 |

**MVP 国家：** 美国、俄罗斯、德国、印度、澳大利亚  
**接通顺序：** 美 → 俄 → 德 → 印 → 澳  

---

## 4. MVP 功能需求

### 4.1 来源治理

- 注册国家、组织、来源  
- 记录 ownership、government_control_level、editorial_independence 等及证据  
- 审核、停用、属性变更历史  
- 来源健康：成功率、最近成功时间、错误类型  

### 4.2 采集与处理

- 可插拔 Adapter（RSS 优先；API/Web 基础接口）  
- 调度、重试、任务状态与日志  
- 正文提取、清洗、语言识别、UTC 标准化  
- URL / Hash 精确去重；单语言近似去重  
- 原始与清洗正文分存；版本可追溯  

### 4.3 文章级 AI 分析

- 统一 Analysis Schema  
- Topic（受控词表）、Sentiment、Target-bound Stance、Framing、Entities、Evidence Spans  
- Per-field Confidence；允许 Unknown / Ambiguous / Insufficient Evidence  
- 模型 / Prompt / Schema / Taxonomy 版本化；禁止静默覆盖  
- 缓存、日预算、失败降级  

### 4.4 指标与报告

- 独立展示 Sentiment / Stance / Framing / Attention（基础版）  
- 所有比例公开分母与统计范围  
- 日报、周报；事实结论绑定 article_id / evidence / metric_run  
- 冷启动期不发布确定性异常结论  

### 4.5 Dashboard（MVP 页面）

1. 全球总览：主题分布、国家覆盖、重点文章  
2. 国家分析：情感、立场、基础框架分布  
3. 数据质量：采集/提取/重复/分析成功率、成本  
4. 报告：日报周报与证据链接  

---

## 5. 非功能需求

| 类别 | 要求 |
|------|------|
| 可追溯 | 结论可回溯原文、来源、分析版本 |
| 可观测 | 任务日志、来源健康、分析失败可定位 |
| 成本可控 | Daily Budget、Token 上限、优先级队列 |
| 时区 | DB 存 UTC；报表时区可配置 |
| 合规 | 来源准入审查；内部研究默认；限制全文再分发 |
| 部署 | Docker Compose 单机可运行 |
| 测试 | pytest；关键逻辑单测；分析/聚类后续要评估集 |

---

## 6. 可视化信息架构（摘要）

详见 [VISUALIZATION_SPEC.md](VISUALIZATION_SPEC.md)。

约束：情感与立场分图；质量指标不与舆情结论混排；图表标注样本量与时间窗口。

---

## 7. 验收标准（MVP）

1. 来源可注册、分类、审核、停用  
2. ≥5 个稳定来源可持续采集  
3. 采集任务有状态、日志、重试  
4. 文章可规范化并按国家/来源/时间查询  
5. 精确去重与基础近似去重可用  
6. 文章级主题/情感/立场/框架可用，立场绑定 Target  
7. 证据可定位原文  
8. 分析记录模型与 Prompt 等版本  
9. LLM 有缓存、预算、降级  
10. Dashboard 展示主题、情感、立场、覆盖与质量  
11. 日报/周报可生成并追溯证据  
12. 比例展示分母与范围  
13. 数据质量与分析质量分开评估  
14. 单条失败不终止整批  

事件聚类、Narrative Shift、复杂风险、研究 Agent **不在** MVP 验收内。

---

## 8. 风险与依赖

| 风险 | 控制 |
|------|------|
| 来源不稳定 / 俄印可达性 | 准入门槛、接通顺序、健康监控 |
| 媒体分类错误 | 证据、审核、变更史、定期复核 |
| LLM 成本 | 分级分析、缓存、预算 |
| 冷启动误报 | 0–30 / 30–90 / 90+ 规则 |
| 版权条款 | COMPLIANCE、必要内容保存、限制再分发 |
| 过早复杂化 | Modular Monolith；推迟 Prefect/微服务 |

**依赖：** PostgreSQL、可替换 LLM API（默认 DeepSeek 抽象）、首批可核验 RSS/API 来源。

---

## 9. 相关文档

- [PRODUCT_SCOPE.md](PRODUCT_SCOPE.md)  
- [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md)  
- [COMPETITIVE_ANALYSIS.md](COMPETITIVE_ANALYSIS.md)  
- [SOURCE_REGISTRY.md](SOURCE_REGISTRY.md)  
- [COMPLIANCE.md](COMPLIANCE.md)  
- [ARCHITECTURE.md](ARCHITECTURE.md)（段 2）  
- [METRICS.md](METRICS.md)（段 2）  
