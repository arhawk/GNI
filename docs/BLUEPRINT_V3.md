# Global Narrative Intelligence（GNI）
## 对华舆情与叙事监测系统：产品需求、技术架构与开发实施总纲 V3.0

**版本定位：** 以中国为固定研究对象，以其他国家官方媒体为主要观察样本，监测、比较和研究其对中国的报道、态度、叙事及变化。  
**核心口径：** “全球”指跨国家/地区的监测覆盖，不代表分析全球所有议题，也不代表各国公众民意。  
**历史文档：** 产品/架构以 [BLUEPRINT_V4.md](BLUEPRINT_V4.md) 为准；数据生命周期见 [DATA_LAYERS.md](DATA_LAYERS.md)。

---

## 1. 产品定位与目标

GNI 是**全球多国官方媒体对华舆情与叙事监测研究系统**。系统持续采集其他国家官方媒体及相关政府传播机构发布的公开信息，分析其对中国及中国相关目标对象的报道，提供可比较、可追溯的指标、趋势、证据与研究报告。

核心研究问题：
1. 哪些国家/媒体近期关注中国？关注度如何变化？
2. 各国媒体主要关注中国哪些领域、事件和目标对象？
3. 对中国及具体目标对象，报道的情感评价和立场分别是什么？
4. 各国媒体主要采用什么叙事框架、论据和归因方式？
5. 不同国家之间，对同一中国议题的报道有何差异？
6. 与历史基线相比，对华叙事是否发生变化？变化由哪些来源、议题和事件推动？
7. 数据覆盖和样本质量是否足以支持上述结论？

**研究边界：** 监测媒体表达，不直接代表国家政策、政府真实意图、全体媒体或公众民意。官方媒体报道也不自动等于政府正式声明。

## 2. 研究对象模型

### 2.1 固定核心对象
- `Central Target`: China
- 研究范围可按具体对象细分：
  - Chinese Government
  - Chinese Communist Party
  - Chinese Economy
  - Chinese Technology / Technology Industry
  - Chinese Military
  - Chinese Society / Culture
  - Chinese Foreign Policy
  - Chinese Companies / Specific Entity
  - Specific Policy / Initiative / Person

### 2.2 观察维度
统计与筛选的默认研究单元：

`Country × Source × Topic × Target × Time`

跨国比较时可聚合为：

`Country × Topic × Target × Time`

默认 Target 为 China；若用户选定更具体目标，则分析应绑定该目标，不能把对中国企业的批评自动算作对中国政府的批评。

### 2.3 来源样本边界
首期以官方媒体为主，来源属性分开记录：
- State-owned / State-controlled Media
- Public Service Media（需审核治理和编辑独立性）
- Government Communication Sources（政府机构、新闻稿、公告）
- Mainstream Independent Media（未来作为对照组）

来源样本只能代表被纳入的媒体集合。报告必须显示来源范围、样本量、覆盖限制。

## 3. 产品用户与使用场景

主要用户：国际媒体研究人员、政策/战略研究人员、内部分析团队。

典型任务：
- 查看近期全球对华舆情概况。
- 比较不同国家对中国 AI、贸易、外交、军事等议题的关注和叙事。
- 进入某国分析其对华情感、目标对象立场和主要框架。
- 发现指标变化后下钻至媒体、文章、原文证据。
- 生成可追溯的日报、周报和专题研究。

## 4. 产品信息架构（Dashboard）

采用**一个总览 + 四个研究页面 + 一个质量页面**，页面以研究问题组织，而不是按指标堆叠。

### 4.1 对华舆情总览（Phase 1）
回答：近期其他国家媒体如何报道中国？
- KPI：对华文章数、独立报道数、监测国家数、活跃来源数。
- 全球/国家关注度排名：Article Count、Unique Story Count、Attention Share。
- 对华情感分布与明确立场分布（分开展示）。
- 对华主题分布。
- 重点叙事框架。
- 近期关注度变化、重点文章和研究摘要。
- 所有图表可点击下钻到国家/主题/文章。

### 4.2 国家对华舆情（Phase 1）
回答：某国官方媒体如何报道中国？
- 报道量和独立报道量趋势。
- 对华 Attention Share。
- Topic Share。
- Sentiment Distribution。
- Target-bound Stance Distribution。
- Frame Distribution。
- 主要来源贡献和文章列表。
- 选择具体 Target / Topic / 时间窗口。

### 4.3 跨国对华比较（Phase 1）
回答：不同国家对中国或同一议题的报道有何差异？
- 国家 × Topic 热力图。
- 国家 × Sentiment 分布。
- 国家 × Target-bound Stance 分布。
- 国家 × Frame 分布。
- 同一 Topic / Target 下横向比较。
- 统一统计窗口和样本口径，支持排序与筛选。

### 4.4 对华叙事变化（Phase 2）
回答：对华报道的叙事结构是否发生长期变化？
- Frame Share 时间趋势。
- Frame Entropy。
- Narrative Shift（当前分布与历史基线的 JSD）。
- Persistence。
- Source Convergence（排除转载、共同引用等因素）。
- 历史基线成熟度和样本量提示。
- 变化点下钻至来源、文章、事件和证据。

### 4.5 事件与风险信号（Phase 2/3）
回答：哪些事件推动对华报道变化？哪些信号值得进一步研究？
- 事件列表与生命周期。
- 事件报道强度、国家和来源覆盖。
- 各国事件叙事差异。
- 多源佐证、异常信号及证据。
- 风险信号是研究提示，不是国家风险/意图判定。
Phase 1 仅展示文章热点和基础变化线索，不要求事件聚类。

### 4.6 数据质量与来源治理（Phase 1）
- 国家、来源类型、来源属性与审核证据。
- 采集成功率、最近采集时间、正文提取率、发布时间完整率。
- 重复率、语言识别、分析成功率、待分析队列。
- 模型调用、Token、费用和预算。
- 数据质量与舆情结论分离展示。

## 5. 指标体系：围绕“其他国家对中国”的研究问题

所有指标保留可扩展定义，但按建设优先级分层。**MVP 不实现所有指标，也不提供黑盒综合舆情总分。**

### 5.1 Phase 1 核心指标（7项）
1. **Article Count**：指定国家/来源/时间范围内涉及目标对象的文章数。保留文章级计数。
2. **Unique Story Count**：去重/故事聚类后独立新闻故事数。MVP 先精确去重与基础单语言近似去重；跨语言故事识别后置。
3. **Attention Share**：对华报道量占同一来源集合全部有效报道量的比例。明确分母和来源范围；同时展示绝对量。
4. **Sentiment Distribution**：对目标对象相关文本表达的正面/负面/中性情感分布；允许 Unknown/Ambiguous，不能强行分类。
5. **Target-bound Stance Distribution**：对明确目标对象的支持、批评、反对、认可、混合或未表达立场。Stance 必须绑定 Target；与情感分开。
6. **Frame Distribution / Frame Share**：对华报道采用的叙事框架类别及占比。多标签文章需明确统计口径（primary frame 或 multi-label share）。
7. **Topic Share**：对华报道中各主题的构成比例。主题分类与 Target 识别分离。

### 5.2 Phase 2 叙事变化指标（4项）
8. **Frame Entropy**：叙事框架分布集中/均衡程度；高熵不代表客观。
9. **Narrative Shift**：当前叙事分布与历史基线的差异，可采用 JSD；差异大不代表正负方向。
10. **Persistence**：某框架/立场在连续时间窗口的持续程度。
11. **Source Convergence**：不同来源叙事趋同程度；需控制转载、共同声明、共同通讯社等。
### 5.3 Phase 3 派生分析
12. **Risk Signals**：结合异常变化、持续性、扩散、多源验证等触发研究提示。透明规则/维度，证据可追溯，不输出无依据总分。

### 5.4 统计口径规则
所有指标保存：
- numerator / denominator
- excluded_count / missing_count / unknown_count
- time_window / timezone
- country_scope / source_scope / topic_scope / target_scope
- deduplication_method
- metric_definition_version / computed_at

Article Count、Unique Story Count、Original Reporting Count、Source Count、Country Count 不得混用。
Neutral、Unknown、Ambiguous、Insufficient Evidence 不得合并。
多标签主题/框架占比需说明是否允许合计超过 100%。

## 6. Article-level Analysis Schema（Phase 1）

每篇文章分析：
- Country / Source / Organization / Source Governance Attributes
- Language、Published At、First Seen At
- Primary Topic / Secondary Topics
- Target Entities（China 及细分目标）
- Sentiment、Emotion、Intensity（可选）
- Target-bound Stance、Stance Strength
- Primary Frame / Secondary Frames
- Claims / Reasons / Evidence Type（后续逐步增强）
- Topic Prominence（标题、导语、正文比例、核心/顺带提及）
- Entities / Actors
- Evidence Spans（原文片段、位置、语言）
- Per-field Confidence / Status

允许 `known / unknown / ambiguous / insufficient_evidence / not_applicable`。情感描述语气，立场描述对特定目标的态度；两者分离。

## 7. Topic 与 Target Taxonomy

### Topic 初始分类
- Politics & Governance
- Economy & Trade
- Technology
- Security & Military
- International Relations
- Society & Culture
- Environment & Energy

二级主题示例：AI、半导体、贸易、供应链、外交关系、国防、能源、人口、教育等。

### Target 初始分类
- China（默认）
- Chinese Government
- Chinese Communist Party
- Chinese Economy
- Chinese Technology Industry
- Chinese Military
- Chinese Society
- Chinese Foreign Policy
- Specific Entity / Company / Person / Policy

Topic 与 Target 分开。支持多标签、父子关系、多语言别名、合并/拆分/停用、版本和生效时间。历史统计不得因静默修改词表而改变口径。

## 8. 数据来源与治理

首期建议 3–5 个国家、15–25 个稳定来源，名单通过 Phase 0 研究和可采集性评估确定，不为了国家数量凑来源。

准入优先级：
1. RSS / API / 开放 Feed。
2. 无登录、结构稳定且允许访问的公开网页。
3. 其他方式仅在合规、可维护且成本合理时评估。

Source Registry 字段：
`source_id, name, country_id, organization_id, canonical_url, source_type, ownership_type, funding_type, government_control_level, editorial_independence, language, timezone, access_method, adapter_type, terms_url, robots_checked_at, compliance_status, evidence_url, classification_confidence, reviewed_at, active_status`

来源属性须有证据、审核记录、复核周期及变更历史。政府机构公告与媒体报道分组统计，不混为一类。

## 9. Ingestion 与 Processing

流水线：

`Fetch → Parse → Normalize → Extract → Language Detect → Time Normalize → Deduplicate → Persist → Analyze → Metrics`

要求：
- 每个步骤独立、可重试、可观测；单篇失败不阻断批次。
- MVP 去重：URL canonicalization、正文/标题 hash、基础单语言相似度。
- Phase 2：跨语言转载/翻译识别、原创与转载关系。
- 同一事件的不同报道不是重复；转载、翻译和独立报道分别记录。
- 时间统一 UTC 存储，展示按研究时区；区分 published_at、first_seen_at、analyzed_at、event_time（事件层后续）。

## 10. AI 分析与质量控制

分级：
1. 规则：URL、清洗、时间、语言、Hash、基础筛选。
2. 轻量模型：Embedding、候选召回、简单分类。
3. LLM：主题、情感、目标立场、框架、实体和证据抽取。
4. 复杂推理：跨文章比较、事件关系、歧义判定，按需触发。

质量：
- 建立人工抽样标注集。
- 分别评估 Topic、Sentiment、Stance、Frame、Evidence 定位。
- 数据质量与分析质量分开。
- 每次分析保留 model、model_version、prompt_version、schema_version、taxonomy_version、status、confidence、token usage、estimated cost。
- 缓存、批处理、重试、Fallback、每日预算、单篇上限和优先级队列。
- Unknown / insufficient evidence 是合法结果，不强迫模型猜测。

## 11. 数据模型

### MVP 必须实体
- countries
- organizations
- sources
- source_reviews / source_attribute_history
- source_health
- articles
- article_versions
- article_analyses
- article_evidence
- article_entities
- article_topics
- topics / topic_relations
- stance_targets
- taxonomy_versions
- analysis_runs / model_versions / prompt_versions
- metric_definitions / metric_runs
- ingestion_jobs
- reports / report_claims / report_evidence

### Phase 2 扩展
- story_clusters / article_story_relations
- events / event_articles / event_embeddings / event_relations / event_analyses / event_metrics / event_corrections
- narrative_baselines / narrative_metrics

数据模型必须使 `country + source + topic + target + time` 成为可筛选、可聚合的核心路径。不要在 Phase 1 过度实现事件图谱。

## 12. 指标计算与历史基线

- 所有聚合由可测试的指标模块计算，不由 LLM 直接生成数值。
- 指标计算记录版本、范围、分母、去重口径和时间。
- 0–30 天：冷启动，不发布确定性变化结论。
- 30–90 天：初步趋势，注明低置信度和覆盖限制。
- 90 天后：仅在有效样本量、来源覆盖和稳定性达到门槛后使用正式基线；低频议题需更久。
- 历史回补需标记数据来源、覆盖率、完整性和回补批次。
- 异常检测需考虑媒体产量变化、节假日、重大事件、来源故障和样本结构变化。

## 13. Reports 与 Agent

Phase 1：日报/周报模板 + 查询工具辅助，事实结论必须链接 article/source/metric evidence。
Phase 3：研究 Agent 多步骤任务。

研究流程：

`Research Question → Query/Filter → Retrieve Evidence → Calculate Metrics → Draft Claims → Validate Evidence → Report`

结论类型：
- Fact：直接证据或结构化数据支持。
- Inference：由多个证据推导，明确标注。
- Hypothesis：待验证，不写成事实。
- Background：背景知识，与本次数据证据分开。

Agent 不得虚构文章、来源、指标、引用或 ID；证据不足时明确说明。

## 14. Dashboard 交互与可视化规则

统一全局筛选：时间范围、国家、来源组、主题、Target、语言。默认 Target=China。

交互路径：
`Overview → Country/Topic → Chart Segment → Articles → Evidence → (Phase 2 Event) → Research Report`

建议图表：
- 排名：横向条形图。
- 时间：折线/堆叠面积；显示样本量。
- 分布：100% 堆叠条；情感和立场分开。
- Country × Topic / Country × Frame：热力图。
- Frame Share：横向条形图或时间序列。
- Narrative Shift：时间趋势与基线区间。
- 文章：列表/表格，不以地图替代。
- 地图仅作为国家覆盖或事件地理辅助。

首页优先呈现研究发现，不展示所有专业统计量。所有图表可下钻并显示分母、样本数、数据范围和证据。

## 15. 技术架构与技术栈

采用 **Modular Monolith + Asynchronous Data Pipeline**，不使用微服务。

逻辑层：
1. Source Registry & Governance
2. Ingestion Adapters
3. Processing / Normalization / Deduplication
4. Article Intelligence
5. Metrics & Reports
6. Storage
7. API / Dashboard
8. Cross-cutting: Scheduling, Logging, Observability, Cost, Versioning, Quality

MVP 技术栈：
- Python 3.12+
- FastAPI
- Streamlit（Dashboard 快速实现）
- PostgreSQL
- RSS: feedparser
- HTTP: httpx
- HTML: BeautifulSoup / 可替换正文提取器
- Scrapy（按需）
- Cron / APScheduler
- LLM Provider Adapter（可替换）
- pytest
- Docker Compose
- Logging / structured logs

Phase 2 评估 pgvector、Embedding、Prefect。MVP 不引入 Kafka、Neo4j、微服务、复杂消息系统。

Adapter：
```python
class BaseAdapter:
    def fetch(self, source_config):
        raise NotImplementedError
    def parse(self, raw_item):
        raise NotImplementedError
    def health_check(self, source_config):
        return {"status": "unknown"}
```
来源配置放 Source Registry，不将 URL 和逻辑散落在 if/else。

## 16. 法律与合规

来源接入前检查 ToS/API Terms、robots、访问频率、版权、保存与再分发限制、个人信息和跨境风险。robots.txt 不等于法律授权。默认内部研究；必要正文和证据片段按最小化、访问控制与保留策略保存；公开报告以摘要和原文链接为主。

## 17. 开发实施路线

### Phase 0：设计收敛与工程初始化
交付：V3 PRD、对华研究问题清单、指标定义、Dashboard wireframe、来源候选表、Source Registry、Topic/Target Taxonomy、ERD、架构/data flow、ADR、工程骨架、测试规范。
不做生产采集和完整 LLM 分析。

### Phase 1：对华基础舆情 MVP
A. Source Registry + 采集  
B. 清洗、标准化、时间、基础去重  
C. Article-level China/Target/Topic/Sentiment/Stance/Frame/Evidence  
D. 7 个核心指标  
E. Dashboard：对华总览、国家分析、跨国比较、质量面板  
F. 日报/周报与证据回溯

验收：来源稳定运行；文章可追溯；核心分析有版本和证据；指标口径明确；Dashboard 可筛选和下钻；报告事实可验证；质量指标可查看。

### Phase 2：事件与叙事变化
跨语言故事识别、事件聚类、生命周期、跨国事件比较、Frame Entropy、Narrative Shift、Persistence、Convergence、历史基线、异常检测。使用标注集评估，控制 False Merge。

### Phase 3：研究型 Agent
复杂自然语言研究、多步骤工具调用、专题报告、证据验证器、可配置风险信号/指数、告警。

## 18. MVP 验收标准
1. 来源可管理、审核、停用、记录属性证据。
2. 3–5 国家、首批来源配置可运行（具体来源数按可行性确定）。
3. 采集有任务状态、日志、重试和健康状态。
4. 文章规范化、语言、时间、去重、来源可追溯。
5. 可识别 China 与细分目标对象。
6. Article-level Topic、Sentiment、Target-bound Stance、Frame、Evidence 可运行。
7. Unknown/ambiguous 状态支持。
8. 7 个核心指标计算可复核，分母与范围透明。
9. Dashboard 完成对华总览、国家分析、跨国比较、数据质量。
10. 图表下钻至文章和原文。
11. 模型、Prompt、Schema、Taxonomy、指标版本可追溯。
12. LLM 成本、缓存、重试、预算控制。
13. 日报/周报可生成并有证据。
14. 单篇失败不阻断批次。
15. 数据质量与分析质量分别呈现。

## 19. 风险与治理
- 来源分类误差：审核与证据、定期复核。
- 样本偏差：显示来源覆盖，不推断全民舆论。
- 转载放大：区分 Article/Story/Original/Source。
- LLM 错误：人工抽样评估、证据定位、未知状态。
- 成本失控：缓存、预算、分级处理。
- 基线不足：成熟度门槛。
- 统计口径漂移：版本化、分母透明。
- 合规风险：来源准入与保存策略。
- 过度建设：按阶段实现，不提前建设事件智能和 Agent。

## 20. 最终原则

**GNI 研究的中心始终是中国；国家是观察维度，主题是研究切面，Target 是具体评价对象，时间是变化维度。**

建设顺序：

`可靠来源 → 对华文章分析 → 对华指标 → 国家间比较 → 长期叙事变化 → 事件与研究 Agent`

首期成功标准不是“系统功能多”，而是能够可靠回答：
- 哪些国家媒体关注中国？
- 关注中国什么？
- 如何评价中国及其具体对象？
- 采用什么叙事框架？
- 国家之间有什么差异？
- 每一个结论能否回到数据与原文证据？
