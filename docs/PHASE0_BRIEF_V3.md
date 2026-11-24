# GNI Phase 0 — Cursor/Codex Implementation Brief（V3）

## 任务目标
基于 GNI V3 总纲，完成**中国中心的全球多国官方媒体对华舆情研究系统** Phase 0：设计收敛、仓库审计、工程初始化和设计文档落地。

本阶段不要做生产级采集、LLM 分析、事件聚类或 Dashboard 功能实现。先让设计和工程基础可审查、可运行。

## 产品核心约束（必须遵守）
- 固定研究中心对象：China。
- 观察样本：其他国家官方媒体及相关政府传播来源；媒体来源和政府公告必须分类、分组统计。
- 核心研究维度：Country × Source × Topic × Target × Time。
- 默认 Target=China，支持细分目标：中国政府、中国经济、中国科技产业、中国军事、中国社会、中国外交、企业/人物/政策。
- 系统结论仅代表纳入的媒体样本，不等同国家政策、政府意图或公众民意。
- Phase 1 核心指标 7 项：Article Count、Unique Story Count、Attention Share、Sentiment Distribution、Target-bound Stance Distribution、Frame Distribution、Topic Share。
- Phase 2：Frame Entropy、Narrative Shift、Persistence、Source Convergence、跨语言转载/事件聚类。
- Phase 3：Risk Signals、研究 Agent、复杂专题研究。
- 不做黑盒综合舆情总分。
- MVP Dashboard：对华总览、国家对华分析、跨国比较、数据质量。叙事变化和事件风险后置。
- 指标必须保留统计分母、样本范围、时间窗口、版本与缺失值口径。

## Cursor 执行规则
1. 首先只读检查当前仓库：文件结构、现有代码、Git 状态、依赖、运行方式、已有文档。
2. 不要在第一步直接修改代码。先输出仓库审计报告和建议计划，指出哪些内容可以复用、哪些需要调整。
3. 遵循现有仓库约定；不要为了模板重写项目或引入不必要技术。
4. 任何新增设计需写入 docs，并给出决策理由、替代方案和影响。
5. 未经批准不要删除文件、改动历史、覆盖用户数据、执行大规模重构。
6. 每一任务完成后运行适当检查，并汇报变更、测试结果、剩余问题。
7. 若信息缺失，提出明确假设和需要用户确认的问题，不自行编造来源或法律许可。

## Phase 0 工作包

### P0-1 仓库审计（只读）
输出：
- 项目结构
- 当前技术栈和入口
- 现有功能/模块
- Git 工作区状态
- 依赖及可运行状态
- 可复用内容
- 风险与缺口
- 建议执行计划

等待确认后再修改。

### P0-2 产品需求冻结
建立/更新 `docs/PRD.md`：
- 产品定位与边界
- 对华研究问题
- 用户和使用场景
- 国家/媒体/目标对象/主题/时间维度
- Phase 1/2/3 功能边界
- Dashboard 信息架构
- MVP 验收标准
- 非目标和风险

### P0-3 指标定义
建立 `docs/METRICS.md`：
对 7 个 Phase 1 核心指标逐一写明：
- 研究问题
- 定义
- 公式/计算口径
- numerator / denominator
- 去重方法
- Unknown/Neutral 处理
- 过滤范围
- 维度与聚合方式
- 版本
- 示例
同时明确 4 个 Phase 2 指标和 Risk Signal 后置原则。不得把 AI 输出直接当数值统计。

### P0-4 Dashboard 线框与交互
建立 `docs/DASHBOARD.md`，至少描述：
1. 对华舆情总览
2. 国家对华舆情
3. 跨国对华比较
4. 对华叙事变化（Phase 2）
5. 事件与风险（Phase 2/3）
6. 数据质量

每页说明：目标问题、布局、图表、筛选器、下钻路径、样本提示。全局筛选建议：时间、国家、来源组、Topic、Target、语言；默认 Target=China。

交互路径：
Overview → Country/Topic → Chart Segment → Article List → Original/Evidence → (Phase 2 Event) → Report。

### P0-5 来源候选与 Source Registry
建立 `docs/SOURCE_REGISTRY.md` 与候选数据表（CSV 或 Markdown）：
- 先研究候选国家与媒体来源，评估中国研究价值、官方属性、语言、采集入口、稳定性、样本可比性和合规性。
- 不要为凑 3–5 个国家或 15–25 个来源而纳入低质量来源。
- 每个候选记录：国家、机构、来源、类型、治理属性、语言、URL、RSS/API/网页方式、更新频率、正文可提取性、ToS/robots 检查、采集难度、准入建议、证据 URL、审核日期。
- Government Communication Sources 与 Media Source 分开。
- 来源分类必须有依据，不将 Public Service Media 自动视为政府控制。

### P0-6 Taxonomy
建立 `docs/TAXONOMY.md`：
- Topic 一级/二级分类初稿。
- China Target taxonomy。
- 多语言别名和实体规范化原则。
- 多标签、Unknown、Ambiguous 规则。
- Taxonomy versioning 和历史结果不静默变更规则。

### P0-7 ERD 与 Schema
建立 `docs/DATABASE.md` 和 `docs/DATA_SCHEMA.md`：
- 设计 Phase 1 必需实体和关系。
- 重点支持 Country × Source × Topic × Target × Time 的查询路径。
- Article、Article Analysis、Evidence、Source、Topic、Target、Metric Run、Analysis Run、Report 关系。
- Phase 2 Story/Event 预留扩展，但不实现完整事件模型。
- 每张表说明职责、主键、外键、重要索引、版本和审计字段。
- 避免过度建模或无需求建表。

### P0-8 Architecture & ADR
建立 `docs/ARCHITECTURE.md`、Data Flow 图和 ADR：
- Modular Monolith + Async Pipeline
- Source Registry / Adapter
- Ingestion
- Processing
- Article Intelligence
- Metrics
- Storage
- API / Dashboard / Reports
- Cross-cutting logging, scheduling, cost, quality, versioning
- 说明 MVP 技术栈与不采用 Kafka、微服务、Neo4j、Prefect 等的理由。
- Adapter 接口和模型供应商抽象。
- 记录关键决策、备选方案、理由、影响。

### P0-9 工程骨架（确认设计后）
按现有仓库调整，目标可运行、可测试：
- 配置与环境变量
- Docker Compose（若适用）
- PostgreSQL 连接/迁移策略
- 日志
- pytest
- 模块骨架
- `.env.example`
- README：本地启动、测试、配置说明
- CI 基础检查（若仓库适合）
不得先实现复杂业务。

## Phase 0 验收
- 仓库审计报告完成。
- V3 产品边界和研究问题明确。
- 7 个核心指标定义可审查且口径明确。
- Dashboard 页面和下钻路径有设计。
- 来源候选表有可验证证据和可行性评估。
- Topic/Target Taxonomy 初稿。
- Phase 1 ERD 与数据流图。
- 技术决策有 ADR。
- 工程骨架可启动、测试可执行。
- 未引入 Phase 2/3 的复杂依赖。
- 用户确认后才进入 Phase 1 业务开发。

## 第一条 Cursor 指令
请先执行 P0-1 仓库审计。保持只读，不修改文件、不安装依赖、不运行可能改变环境或数据的命令。阅读项目文档、目录、Git 状态和配置后，输出完整审计报告，并提出基于 GNI V3 约束的 Phase 0 实施计划。等待我确认后再执行后续任务。
