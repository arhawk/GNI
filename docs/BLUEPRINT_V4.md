# Global Narrative Intelligence（GNI）
## 产品需求、技术架构与开发实施总纲 V4.0

**版本：** V4.0（Agent 驱动的官方媒体对华舆情监测产品重构）  
**核心定位：** 以 Agent 为核心的全球多国官方媒体对华舆情自动监测、分析、报告与预警系统  
**首期研究对象：** 中国及其相关目标对象  
**首期观察样本：** 其他国家官方媒体、国家控制媒体及经审核的官方传播来源  
**建设路线：** 可信来源与数据 → 文章理解与相关度加权 → 对华舆情量化 → 重大新闻/异常发现 → 自动报告与主动预警 → 深度叙事研究

---

# 0. 本次 V3.0 的核心调整

V2.0 中存在一个设计偏移：虽然产品声明以中国为中心，但指标、Dashboard 和后续能力逐渐扩展成泛化的全球新闻情报平台。V3.0 重新固定研究对象与产品边界。

## 0.1 研究对象固定

GNI 不是分析“全球发生了什么”或“全球所有舆论”，而是持续研究：

> **其他国家的官方媒体如何报道中国、评价中国及其相关目标对象，关注哪些议题，采用哪些叙事框架，以及这些表达在不同国家和时间之间如何变化。**

“全球”意味着研究样本覆盖多个国家，不意味着研究对象无限扩展。

## 0.2 研究范围结构

核心分析维度：

`Country × Source × Time × China-related Topic × Target`

- Country：报道来源所在国家。
- Source：具体媒体、官方传播机构或政府信息来源。
- Time：发布时间或研究时间窗口。
- Topic：报道涉及中国的议题，例如经济、科技、外交、安全、社会等。
- Target：报道具体评价或描述的对象，例如中国、中国政府、中国经济、中国科技产业、具体企业、政策或人物。

## 0.3 产品范围变化

| 维度 | V2.0 方向 | V3.0 方向 |
|---|---|---|
| 产品定位 | 全球媒体舆论信号与叙事系统 | 多国官方媒体对华舆情与叙事系统 |
| 研究对象 | 可扩展到任意国家、议题和目标 | 首期固定 China-centered |
| Dashboard | 全球主题/国家综合新闻总览 | 对华舆情总览、单国对华分析、跨国对比 |
| 指标 | 泛化的跨层级指标集合 | 7 个核心指标优先；演化指标后置 |
| 事件 | 作为较早的产品主线之一 | 作为解释舆情变化的后续能力 |
| 风险 | 泛化风险信号 | 对华叙事变化的研究提示，不做国家风险黑盒评分 |
| MVP | 可信数据与基础分析 | 可信数据 + 对华文章分析 + 基础对华统计与展示 |

---

# 1. 执行摘要

GNI 持续采集其他国家官方媒体和官方传播机构公开发布的中国相关信息，将文章转化为可追溯、可比较的结构化数据，建立对华舆情分析、跨国媒体比较和长期叙事研究能力。

核心价值：

1. **持续采集：** 建立国家、机构、媒体来源治理和采集体系。
2. **对华分析：** 识别文章涉及中国的主题、情感、立场、叙事框架和证据。
3. **跨国比较：** 比较不同国家媒体对中国及同一议题的关注和表达差异。
4. **变化监测：** 在历史数据和样本充分时识别关注度、立场和叙事框架变化。
5. **可追溯研究：** 每项统计和结论回溯来源、文章、证据、统计口径和分析版本。
6. **研究辅助：** 后续通过 Agent 支持查询、比较、专题研究与报告生成。

## 建设阶段

- **Phase 0：** 需求校准、来源研究、数据标准、工程初始化。
- **Phase 1 / MVP：** 稳定采集、对华文章级分析、7 个核心指标、Dashboard、日报/周报、质量面板。
- **Phase 2：** 跨国对比深化、跨语言转载识别、事件聚类、叙事变化指标、历史基线。
- **Phase 3：** 研究型 Agent、专题研究、证据验证、可配置分析和研究报告。

MVP 不依赖事件聚类、复杂 Narrative Shift、风险指数或高级 Agent 才能成功。

---

# 2. 产品定位、用户与研究问题

## 2.1 产品定位

GNI 是**多国官方媒体对华舆情与叙事监测研究系统**。

分析对象是被监测媒体公开表达的报道内容。输出：

- **事实层：** 哪些媒体在什么时间发布了哪些中国相关报道，报道涉及什么对象、主题和证据。
- **文章分析层：** 报道表达的情感、对具体目标的立场、采用的叙事框架。
- **舆情统计层：** 不同国家和媒体集合对中国的关注度、议题结构、情感/立场/框架分布。
- **比较层：** 不同国家、来源、议题和时间窗口之间的差异。
- **演化层：** 在历史样本充分时，识别对华叙事结构变化。
- **研究层：** 生成有来源证据和明确统计口径的分析结论。

媒体表达不等于政府政策、政府真实意图、公众民意或社会整体态度。系统不得将被监测媒体的内容直接解释为国家立场或全民观点。

## 2.2 主要用户

- 国际媒体研究人员。
- 政策、战略与国际关系研究人员。
- 内部舆情分析和研究团队。
- 需要跟踪特定国家或议题的决策支持人员。

## 2.3 核心研究问题

1. 哪些国家的官方媒体近期更关注中国？
2. 各国媒体对中国报道的关注度如何变化？
3. 各国媒体主要关注中国哪些领域和议题？
4. 各国报道对中国及具体目标对象的情感倾向是什么？
5. 各国媒体对中国、中国政府、中国经济、中国科技产业等具体对象持什么立场？
6. 各国媒体通过什么叙事框架描述中国？
7. 不同国家对同一中国议题的叙事差异是什么？
8. 对华报道变化由哪些媒体、报道或事件推动？
9. 某种叙事框架是否持续存在，或相较历史基线发生变化？
10. 当前样本覆盖和数据质量是否足以支持研究结论？

## 2.4 MVP 不做

- 不监测全球所有新闻议题。
- 不把“中国相关报道”扩展成泛化的各国国内舆情分析。
- 不代表某国全部媒体、社会舆论或公众态度。
- 不推断国家真实意图、外交决策或政策行为。
- 不预测战争、政变或外交冲突。
- 不把单篇报道直接升级为国家级叙事或风险结论。
- 不无差别抓取全球数百来源。
- 不采集强反爬、登录、付费墙或合规不清的网站。
- 不强制对每篇文章进行高成本深度 LLM 分析。
- 不默认将指标压缩成单一“对华舆情分数”。

---

# 3. 研究对象、样本与分析单位

## 3.1 Country：国家

国家是对比维度。首期选择 3–5 个国家，根据研究价值、来源稳定性、语言处理能力和样本平衡确定。

国家不直接作为“态度标签”。结论应描述为“该国被监测官方媒体样本的报道表现”。

## 3.2 Source：媒体来源

来源是研究样本的组成部分。需区分：

- State-owned Media：国有媒体。
- State-controlled Media：受到政府实质控制的媒体。
- Public Service Media：公共服务媒体，需要审查治理结构和编辑独立性。
- Government Communication Sources：政府部门、新闻办公室、机构公告和官方声明。
- Mainstream Independent Media：后续作为对照样本，不默认属于官方媒体。

来源属性应有证据、置信度、审核人、审核时间和变更历史。

## 3.3 Topic：对华议题

主题描述报道讨论中国的哪个领域。例如：

- Politics & Governance：政治、治理、制度、政策。
- Economy & Trade：经济、贸易、投资、产业、供应链。
- Technology：AI、半导体、通信、科技产业。
- Security & Military：军事、安全、国防、网络安全。
- International Relations：外交、国际关系、区域合作。
- Society & Culture：社会、人口、教育、文化。
- Environment & Energy：环境、气候、能源。

Topic 是文章讨论内容，不是报道立场。

## 3.4 Target：目标对象

立场必须绑定目标对象，不能简单给整篇文章贴“亲华/反华”标签。

初始 Target：

- China
- Chinese Government
- Chinese Communist Party
- Chinese Economy
- Chinese Technology Industry
- Chinese Military
- Chinese Society
- Chinese Foreign Policy
- Specific Company / Entity / Policy / Person

文章可能对不同 Target 表达不同立场，允许 Target 未明确或证据不足。

## 3.5 三层分析单位

### L1 Article：文章级（Phase 1）

回答：这篇报道如何表达中国相关内容？

- Topic。
- Sentiment / Emotion（情感与情绪）。
- Target-bound Stance（对指定目标的立场）。
- Primary / Secondary Frame。
- Entities。
- Evidence Spans。
- Topic Prominence。
- Per-field Confidence。
- Unknown / Ambiguous / Insufficient Evidence。

### L2 Event：事件级（Phase 2）

回答：围绕同一事件，各国媒体如何报道？

- 事件相关报道量。
- 独立报道数和原创报道数。
- 来源及国家覆盖。
- 事件发展阶段。
- 事件内不同国家的情感、立场和框架差异。
- 事件关系：same_event、follow_up、sub_event、related_event。

主题相同不代表事件相同；事件聚类需人工评估，优先控制 False Merge。

### L3 Narrative：国家/来源集合叙事级（Phase 2 起逐步启用）

回答：一个国家或来源集合在一段时间内如何持续描述中国或某一目标？是否出现结构性变化？

统计单位：

`Country × Source Group × Topic × Target × Time`

Narrative-level 指标必须由足够的文章级样本聚合，不能将单篇文章的标签当作国家整体叙事。

---

# 4. 指标体系：重新定义 7 + 4 + 1

## 4.1 指标设计原则

指标必须围绕研究问题，不是为了指标数量而开发。

所有指标明确：

- 分析对象和层级。
- 统计单位（Article / Unique Story / Source）。
- 时间窗口。
- 来源范围。
- 主题范围。
- Target。
- 分子、分母。
- 去重方式。
- Unknown / Missing / Excluded 的处理。
- 指标版本和计算时间。

情感、立场、框架和关注度是不同概念，不应混为一类。

## 4.2 Phase 1：7 个核心指标

### M1 Article Count — 对华报道数量

指定国家、来源集合、时间窗口和中国相关范围内的文章数量。

用途：观察报道规模、监测数据量及趋势。

限制：转载、重复发布可能放大数量。不能单独代表舆论影响力。

### M2 Unique Story Count — 独立报道故事数量

去重或 Story Cluster 后的独立新闻故事数量。

用途：降低转载、翻译稿和重复发布对关注度的放大。

MVP 先 URL / Hash / 单语言近似去重；跨语言转载识别在 Phase 2 扩展。不能把同一事件的独立报道视为重复。

### M3 Attention Share — 对华关注占比

推荐定义：

`China Attention Share = 中国相关报道数 / 指定媒体集合同期全部有效报道数`

必须明确统计单位是 Article 还是 Unique Story。Dashboard 默认同时显示 Article Count 和 Unique Story Count；Attention Share 使用明确选定的分母并标注。

用途：衡量对华报道在该媒体样本整体新闻产出中的相对关注程度。

限制：需要采集或估计来源同期全部有效报道，否则分母不完整时不得发布正式 Attention Share。若仅采集中国相关内容，不能用抓取到的文章数冒充媒体整体报道总数。

### M4 Sentiment Distribution — 情感分布

对中国相关报道文本的情感评价或语气进行分类。

推荐分类：Positive / Neutral / Negative / Mixed / Unknown。

用途：描述报道的情感语气。

限制：Sentiment 不等于 Stance。对中国负面描述不一定意味着反对某个具体政策；报道中的被引用对象情绪不一定代表媒体作者态度。需明确分析主体是报道整体表达，而非机械统计引述情绪。

### M5 Target-bound Stance — 目标绑定立场

针对明确 Target 判断报道表达的立场。

可按研究需要定义分类，例如：

- Supportive / Favorable
- Critical / Opposing
- Neutral / No explicit stance
- Mixed
- Unclear / Insufficient evidence

具体标签应通过 Phase 0 taxonomy 设计和标注试验冻结。

用途：回答媒体对中国或具体对象持什么态度。

限制：必须绑定 Target。Unknown、Ambiguous、Neutral 不可混为一类；每项判断应尽可能提供证据。

### M6 Frame Distribution — 叙事框架分布

识别报道如何解释中国相关议题。

初始框架词表可作为候选，不应硬编码成唯一、永不变化的标签：

- Competition / Rivalry：竞争。
- Security / Threat：安全或威胁。
- Economic Impact：经济影响。
- Cooperation：合作。
- Governance / Ideology：治理或制度。
- Development / Innovation：发展或创新。
- Human Rights：人权。
- International Order：国际秩序。
- Other / Unknown。

用途：分析媒体叙述中国的方式。

限制：框架是多标签分类，不能压缩成单一“正负框架分”。允许 Primary / Secondary Frame，并支持 taxonomy 版本。

### M7 Topic Share — 对华议题结构

推荐定义：

`Topic Share = 某主题下中国相关报道数 / 同一范围内全部中国相关报道数`

可使用 Article 或 Unique Story 作为单位，但必须保持口径一致并注明。

用途：回答媒体关注中国的哪些方面，以及主题结构如何变化。

限制：文章可能多主题，若采用多标签计数，各 Topic Share 之和可能大于 100%。Dashboard 必须明确采用主主题互斥统计或多标签统计；建议总览使用 Primary Topic 互斥统计，专题分析保留多标签视角。

## 4.3 Phase 2：4 个叙事演化指标

### M8 Frame Entropy — 框架分布熵

衡量叙事框架分布的集中或均衡程度。

- 低值：报道集中在少数框架。
- 高值：框架分布更均衡。
- 不代表媒体更客观、更开放或更准确。

样本量不足、框架 taxonomy 变化时不计算或标记不可比较。

### M9 Narrative Shift — 叙事变化

比较当前时间窗口与历史基线中对华报道的分布差异。

可使用 Jensen-Shannon Divergence（JSD）比较框架、立场或主题分布。

高值代表分布差异较大，不代表变化方向是正面或负面。

必须控制时间窗口、样本量、来源范围、taxonomy 版本和基线成熟度。

### M10 Persistence — 叙事持续性

衡量某个框架或立场在连续多个时间窗口中持续出现的程度。

需要定义持续时间、阈值、间断容忍度及样本量要求。不能把一次短期报道激增认定为长期叙事。

### M11 Source Convergence — 来源叙事趋同

衡量不同媒体来源在相近时间内，框架或表达分布的相似程度。

需排除或控制：

- 转载和翻译转载。
- 共同引用同一官方声明。
- 共同引用同一通讯社稿件。
- 来源样本量差异。
- 共同事件导致的合理报道相似性。

趋同不证明协调、统一指挥或共同意图。

## 4.4 Phase 3：M12 Risk Signal — 研究提示信号

不是国家风险分数，也不是自动政治判断。

可能触发的观察条件：

- 对华报道量异常变化。
- 某叙事框架占比异常上升。
- 某立场变化明显。
- 多个独立来源同时变化。
- 变化持续多个时间窗口。
- 事件或原文证据显示具体背景。

系统输出“值得研究的信号”，说明触发条件、样本、证据、置信度和限制。不得仅凭单篇文章认定风险。

## 4.5 不开发黑盒综合舆情分数

MVP 不计算统一 0–100 对华舆情总分。

原因：

- Attention、Sentiment、Stance、Frame 不是同一量纲。
- Frame 是分布，不适合随意压成分数。
- 负面报道量不等于立场强度。
- 不同国家和来源样本无法未经校准直接比较。
- 综合分可能隐藏分母、权重和缺失值。

未来如确有需要，必须透明定义、版本化、可配置、公开权重和分项，只用于辅助排序，不进行因果推断。

---

# 5. Dashboard：围绕“对华舆情”重构

## 5.1 信息架构

建议产品主导航：

1. **对华舆情总览**
2. **国家对华分析**
3. **跨国对比**
4. **叙事变化与趋势**（Phase 2）
5. **事件与研究信号**（Phase 2/3）
6. **数据质量**
7. **报告**

所有页面统一筛选器：

- 时间范围。
- 国家。
- 媒体来源 / 来源集合。
- 对华 Topic。
- Target。
- 统计单位（Article / Unique Story）。
- 分析状态与数据质量条件（必要时）。

## 5.2 页面 1：对华舆情总览（Phase 1）

回答：

- 哪些国家近期更关注中国？
- 对华报道整体规模如何？
- 各国主要关注中国哪些主题？
- 对华情感和立场分布如何？
- 哪些变化值得进一步查看？

建议布局：

### A. 顶部 KPI 卡片

- 对华报道数（Article Count）。
- 独立报道数（Unique Story Count）。
- 监测国家数。
- 有效来源数。
- 可选：中国相关报道 Attention Share（仅在分母完整可用时展示）。

### B. 各国对华关注度排名

- 横向条形图：Article Count / Unique Story Count。
- 视图切换：数量 / 占比。
- 选择国家后下钻至国家分析页。

### C. 全球对华主题分布

- Primary Topic 堆叠条形图。
- 主题跨期变化：堆叠面积图或分组柱状图。
- Topic Share 与 Topic Count 切换。

### D. 情感与立场分布

- 情感分布图。
- 目标绑定立场分布图。
- 两者分开，不共用一个图表。
- 显示 Unknown / Mixed / 样本不足。

### E. 主要叙事框架

- Frame Distribution 横向条形图。
- 可选择国家或主题筛选。
- 不以单一“正负叙事指数”替代。

### F. 重点报道

列表展示标题、来源、国家、发布时间、Topic、Target、Sentiment、Stance、Frame、证据入口。

### G. 数据质量提示

显示采集状态、来源覆盖和分析完成度；与舆情结论分区展示。

## 5.3 页面 2：国家对华分析（Phase 1）

用户选择一个国家，回答“该国被监测官方媒体如何报道中国”。

建议区域：

1. 国家和来源样本概况。
2. 对华报道数量趋势。
3. Attention Share（分母可用时）。
4. Topic Share。
5. Sentiment Distribution。
6. Target-bound Stance Distribution。
7. Frame Distribution。
8. Top Sources。
9. 重点文章及原文证据。
10. 日报/周报入口。

时间趋势图必须显示样本量。情感和立场必须分别展示。

## 5.4 页面 3：跨国对比（Phase 1 基础版）

回答“不同国家媒体对中国的报道差异是什么？”

建议图表：

- Country × Topic 热力图。
- Country × Sentiment 100% 堆叠柱状图。
- Country × Stance 100% 堆叠柱状图。
- Country × Frame 热力图或小 multiples。
- 国家对华报道量排名。
- 同一 Topic 下各国文章列表。

比较前必须检查来源规模、样本量、统计时间和标签口径。避免把来源覆盖差异当作国家舆情差异。

## 5.5 页面 4：叙事变化与趋势（Phase 2）

回答“某国或媒体集合对中国的叙事是否发生变化？”

显示：

- Frame Entropy 趋势。
- Narrative Shift 趋势。
- Persistence 时间轴。
- Source Convergence 热力图。
- 当前分布与历史基线对比。
- 变化贡献最大的来源、Topic、文章和事件。

仅当历史基线、样本量、来源覆盖和 taxonomy 版本满足条件时显示正式指标；否则显示“数据积累中”及限制。

## 5.6 页面 5：事件与研究信号（Phase 2/3）

用于解释对华报道变化的背景：

- 事件列表和时间线。
- 事件相关报道数量与独立报道数。
- 国家和来源覆盖。
- 不同国家事件叙事比较。
- 事件发展及文章证据。
- 研究提示信号和触发原因。

Phase 1 可以提供热点文章列表，但不宣称已具备完整事件聚类能力。

## 5.7 页面 6：数据质量

独立展示：

- 来源数量与来源属性。
- 来源最近成功采集时间。
- 采集成功率。
- 正文提取率。
- 发布时间完整率。
- 语言识别质量。
- 重复率。
- 分析成功率。
- Evidence Span 可定位率。
- 待分析队列。
- Token 与费用。
- 来源覆盖与样本偏斜。

数据质量与分析质量分开评估；不得把采集故障造成的报道量下降解释为真实舆情下降。

## 5.8 页面 7：报告

Phase 1：

- 对华日报。
- 对华周报。
- 国家专题摘要。
- 主题专题摘要（基础版）。

报告必须包括时间范围、国家、来源范围、统计口径、样本量、限制、证据链接和版本。

---

# 6. 可视化与交互原则

## 6.1 不做指标大全

首页只展示快速回答研究问题的核心信息；专业统计指标进入专题页面。

## 6.2 统一下钻链路

`Overview → Country → Topic / Target → Metric → Source → Article → Evidence`

用户从任何图表点击数据，应能查看对应样本文章和计算口径。

## 6.3 图表建议

| 研究问题 | 推荐图表 |
|---|---|
| 哪些国家更关注中国 | 横向条形图 |
| 对华报道随时间变化 | 折线图 |
| 对华议题结构 | 堆叠条形 / 堆叠面积 |
| 各国主题差异 | Country × Topic 热力图 |
| 情感分布 | 100% 堆叠条形 |
| 目标绑定立场 | 100% 堆叠条形 |
| 叙事框架排名 | 横向条形图 |
| 国家间框架差异 | Country × Frame 热力图 |
| 叙事变化 | Shift 时间序列 + 基线对比 |
| 叙事持续性 | 时间轴 / 连续周期矩阵 |
| 来源趋同 | Source × Frame 热力图 |

## 6.4 样本量与分母

任何比例图都应可查看：

- Numerator。
- Denominator。
- Unknown / Missing。
- Excluded Count。
- Article / Unique Story 统计单位。
- 时间窗口。
- 来源范围。
- Topic 和 Target 范围。

低样本时显示警告，不应提供过度确定的结论。

---

# 7. 来源治理与采集准入

## 7.1 首期来源规模

首期建议 3–5 个国家、约 15–25 个来源作为候选目标。最终名单由 Phase 0 通过研究价值、采集可行性、来源属性、语言和样本平衡确定。

不能为凑国家数量纳入不稳定来源。

## 7.2 来源优先级

1. 稳定 RSS / API / 开放 Feed。
2. 无需登录、结构稳定的公开网页。
3. 其他采集方式仅在合规、可行和维护成本可接受时纳入。

暂不纳入强反爬、登录/付费墙、结构频繁变化或合规无法确认的来源。

## 7.3 Source Registry 字段

至少：

`source_id, name, country_id, organization_id, canonical_url, source_type, ownership_type, funding_type, government_control_level, editorial_independence, language, timezone, access_method, adapter_type, terms_url, robots_checked_at, compliance_status, evidence_url, classification_confidence, reviewed_at, active_status`

来源属性有审核人、审核时间和历史记录。建议 6–12 个月复核；治理、所有权或编辑独立性变化时提前复核。

## 7.4 Source Health

监控：

- 最近成功采集时间。
- 采集成功率。
- 发现量异常。
- 正文提取率。
- 发布时间缺失率。
- 重复率。
- Adapter 错误类型。

Source Health 只衡量数据源健康，不参与舆情指标。

---

# 8. 数据处理、去重与时间标准

## 8.1 Pipeline

`Fetch → Parse → Normalize → Extract → Language Detect → Time Normalize → Deduplicate → Persist → Analyze → Aggregate`

每一步可重试、可观测；单篇失败不应中断批次。

## 8.2 去重

Phase 1：

1. URL 规范化与 Canonical URL。
2. 正文 Hash / 标题 Hash。
3. 单语言近似去重。

Phase 2：

4. 跨语言翻译转载识别。
5. 通讯社转载与原创报道识别。

区分：

- 同一文章的转载/翻译。
- 多家媒体独立报道同一事件。
- 仅讨论相同主题但内容不同的文章。

建议对象：`story_clusters`、`article_story_relations`。

统计明确区分 Article Count、Unique Story Count、Original Reporting Count、Syndicated Story Count、Source Count、Reprint Ratio。MVP 的 Original Reporting Count 可能无法可靠判定，应显示为未支持或待后续能力，不能猜测。

## 8.3 时间标准

数据库统一 UTC；展示与报表使用研究任务指定时区。

区分：

- `published_at`
- `first_seen_at`
- `analyzed_at`
- `updated_at`
- Phase 2 `event_time`

记录 `source_timezone`、`report_timezone`、`time_precision`。

支持 Daily / Weekly / Monthly 与滚动 24h / 7d / 30d / 90d / 365d。迟到文章可回补历史窗口，并记录回补原因和计算版本。

---

# 9. Taxonomy：Topic、Target、Frame、Stance

## 9.1 Topic

初始一级分类：

- Politics & Governance
- Economy & Trade
- Technology
- Security & Military
- International Relations
- Society & Culture
- Environment & Energy

二级主题由 Phase 0 根据实际研究需求确定。支持多语言别名、父子关系、版本、生效时间、合并/拆分/停用。

## 9.2 Target

初始目标：

- China
- Chinese Government
- Chinese Communist Party
- Chinese Economy
- Chinese Technology Industry
- Chinese Military
- Chinese Society
- Chinese Foreign Policy
- Specific Entity / Company / Policy / Person

## 9.3 Frame

初始框架作为候选体系，由样本试标后调整：

- Competition / Rivalry
- Security / Threat
- Economic Impact
- Cooperation
- Governance / Ideology
- Development / Innovation
- Human Rights
- International Order
- Other / Unknown

框架允许多标签，记录 Primary / Secondary。taxonomy 版本化，避免历史分析口径静默变化。

## 9.4 Stance

Stance 必须绑定 Target。标签体系需在 Phase 0 通过试标冻结；至少区分：

- Supportive / Favorable
- Critical / Opposing
- Neutral / No Explicit Stance
- Mixed
- Unclear / Insufficient Evidence

不能强制所有文章都给出明确立场。

---

# 10. AI 分析、成本与质量

## 10.1 分级处理

1. 规则：URL、HTML、语言、时间、Hash。
2. 轻量模型：Embedding、相似检索、筛选。
3. LLM 结构化分析：Topic、Sentiment、Stance、Frame、Entities、Evidence。
4. 复杂分析：歧义、跨文章比较、事件关系，按需触发。

## 10.2 成本控制

必须有：

- Content Hash Cache。
- Analysis Version Cache。
- Batch Processing。
- Retry / Backoff。
- Failure Fallback。
- Daily Budget。
- 单篇 Token 上限。
- 每日文章上限。
- 优先级队列。

预算上限时优先保证采集和存储，暂停低优先级分析，不停止数据采集。模型、Prompt、Schema 变化时保留新版本，不覆盖旧结果。

## 10.3 分析质量

建立人工抽样评估集，分别评估：

- Topic 分类准确率。
- Sentiment 分类准确率。
- Target 识别准确率。
- Stance 分类准确率。
- Frame 分类准确率。
- Evidence Span 定位准确率。

数据质量与分析质量分开评估。正文提取失败是数据质量问题；模型判断错误是分析质量问题。

---

# 11. 冷启动与历史基线

- 0–30 天：Cold Start，积累数据，不发布确定性异常结论。
- 30–90 天：Baseline Building，可展示初步变化，但降低置信度并注明限制。
- 90 天以后：仅在有效样本量、来源覆盖、稳定性和主题频率满足条件时启用正式基线。

90 天不是充分条件；低频议题可能需要更长时间。

历史回补标记覆盖时间、来源和完整性。异常分析考虑季节性、节假日、重大事件、来源变化和采集故障。

---

# 12. Agent 与报告证据约束

Phase 1 报告能力以模板化统计和有证据摘要为主。Agent 不替代采集、分析模型或指标计算。

流程：

`Research Question → Query Tools → Evidence Retrieval → Draft Claims → Evidence Validation → Report`

正式报告事实性结论必须引用已入库：

- `article_id`
- `evidence_id`
- `metric_run_id`
- `source_id`
- 原文 URL
- 时间窗口
- 统计口径

结论类型：

- Fact：原文或可靠结构化数据支持。
- Inference：多证据支持的分析推断，明确标记。
- Hypothesis：待验证假设，不得写成事实。
- Background：背景解释，不得冒充本次采集证据。

缺乏证据时，验证器拒绝正式发布或改写为不确定性说明。不得编造文章、来源、引用、统计值或数据库 ID。

---

# 13. 竞品与参考产品

竞品分析为定性借鉴，不代表对内部模型或实际性能的独立测试。

## Signal AI
借鉴：结构化分析、检索优先、风险信号、证据回溯。  
不照搬：企业声誉与品牌风险目标。

## GDELT
借鉴：多语言新闻数据、文章/实体/主题/事件分层、数据基础设施。  
不照搬：政治事件编码不等于 GNI 的媒体叙事事件。

## Media Cloud
借鉴：媒体集合、国家/语言/时间过滤、Attention、跨媒体研究。  
尤其适合参考对华报道关注度和长期媒体研究。

## Dataminr
借鉴：事件发现、多源交叉验证、事件跟踪。  
不照搬：大规模实时多模态突发事件发现超出 MVP。

## Meltwater
借鉴：Mention Volume、Share of Voice、Sentiment、趋势、告警与可视化。  
不照搬：品牌曝光指标不能直接替代国家媒体叙事研究。

## ACLED
借鉴：独立指标、透明定义、可解释指数方法。  
不照搬：冲突指标不适用于媒体叙事。

## GNI 差异化

1. 研究对象明确：对华舆情，而不是泛化全球新闻。
2. 来源治理明确：国有、政府控制、公共服务和政府传播来源分开。
3. 叙事分析深入：Sentiment、Target-bound Stance、Frame 分开。
4. 跨国比较：同一中国议题在不同国家媒体中的表达差异。
5. 长期研究：关注结构变化，不仅追踪新闻数量。
6. 证据驱动：所有结论可回溯文章、来源、原文和统计口径。

---

# 14. 技术架构

## 14.1 架构原则

采用 **Modular Monolith + Asynchronous Data Pipeline**。不采用微服务；MVP 不引入 Kafka、复杂消息中间件或 Neo4j。

原则：

- 模块边界清晰。
- 任务异步执行。
- PostgreSQL 作为主要事实存储。
- Adapter 插件化。
- 模型供应商可替换。
- 分析结果可追溯。
- 先可运行、可测试，再增加分布式复杂度。

## 14.2 MVP 技术栈

| 层 | 建议技术 | 说明 |
|---|---|---|
| Language | Python 3.12+ | 主开发语言 |
| API | FastAPI | 查询与内部服务 |
| Dashboard | Streamlit | MVP 快速交付 |
| Database | PostgreSQL | 主要业务存储 |
| Vector | pgvector | Phase 2 扩展 |
| RSS | feedparser | RSS 采集 |
| HTTP | httpx | 请求 |
| HTML | BeautifulSoup / 可替换正文提取器 | 正文提取 |
| Crawling | Scrapy（可选） | 有需要时 |
| Scheduling | Cron / APScheduler | MVP |
| AI | DeepSeek API 抽象层 | 可替换供应商 |
| Embedding | BGE-M3 或可替换多语言模型 | Phase 2 重点 |
| Testing | pytest | 测试 |
| Deployment | Docker Compose | 单机部署 |
| Logging | Python Logging / 结构化日志 | 可观测性 |

Prefect 非 MVP 强制依赖，任务复杂度上升后再评估。

## 14.3 分层

**系统分层（运行时模块）：**

1. Source Layer：国家、组织、来源注册表、治理和合规属性。
2. Ingestion Layer：RSS / API / Web Adapter。
3. Processing Layer：正文提取、规范化、语言、时间、去重、质量检查。
4. Intelligence Layer：对华文章分析、Embedding、事件识别、指标计算。
5. Storage Layer：原始数据、规范化文章、分析、证据、Story、事件和指标。
6. Application Layer：FastAPI、Dashboard、报告、Agent、告警。
7. Cross-cutting Governance：任务、日志、模型/Prompt 版本、权限、成本、质量。

**数据五层（同一 PostgreSQL 内的逻辑数据层；与上表并存、勿与筛选 L1/L2/L3 混用）：**  
见实施文档 [DATA_LAYERS.md](DATA_LAYERS.md) — Raw → Normalized → Screening & Extraction → AI Analysis → Intelligence & Analytics。筛选「标题/正文/片段」三级流程见 [BLUEPRINT_V4_ADDENDUM_A1.md](BLUEPRINT_V4_ADDENDUM_A1.md)，对应数据层 Layer 3。

## 14.4 Adapter

```python
from abc import ABC, abstractmethod

class BaseAdapter(ABC):
    @abstractmethod
    def fetch(self, source_config):
        raise NotImplementedError

    @abstractmethod
    def parse(self, raw_item):
        raise NotImplementedError

    def health_check(self, source_config):
        return {"status": "unknown"}
```

来源配置放在 Source Registry，不允许 URL 和媒体特殊逻辑散落在大量 `if/else` 中。

---

# 15. 数据模型建议

MVP 重点逻辑表：

- `countries`
- `organizations`
- `sources`
- `source_reviews`
- `source_attribute_history`
- `source_health`
- `articles`
- `article_versions`
- `article_analyses`
- `article_evidence`
- `article_entities`
- `article_topics`
- `topics`
- `topic_relations`
- `stance_targets`
- `taxonomy_versions`
- `analysis_runs`
- `model_versions`
- `prompt_versions`
- `metric_definitions`
- `metric_runs`
- `reports`
- `report_claims`
- `report_evidence`
- `ingestion_jobs`

Phase 2 增加：

- `story_clusters`
- `article_story_relations`
- `events`
- `event_articles`
- `event_embeddings`
- `event_relations`
- `event_analyses`
- `event_metrics`
- `event_corrections`
- `narrative_baselines`
- `narrative_metrics`

表清单是逻辑建议，不代表 MVP 一次性实现所有字段。Phase 0 需通过 ERD 确定最小表和扩展接口。

## 15.1 分析版本

每次分析记录：

`article_id, model_name, model_version, prompt_version, schema_version, taxonomy_version, analysis_status, analyzed_at, token_usage, estimated_cost, confidence, structured_result`

同一文章允许多个分析版本；旧版本不能无记录覆盖。

## 15.2 指标版本

每次计算记录：

`metric_definition_version, time_window, timezone, country_scope, source_scope, topic_scope, target_scope, numerator, denominator, excluded_count, missing_count, deduplication_method, computed_at`

---

# 16. 法律、版权与合规

MVP 默认内部研究用途，不默认对外提供文章全文分发。

来源接入前记录：

- 网站服务条款/API 条款审查。
- robots 检查时间。
- 请求频率限制。
- 内容保存与再分发限制。
- 个人信息风险。
- 合规状态与复核人。

数据保存原则：

- 保存必要元数据、URL 和分析所需的必要内容。
- 不默认永久保存所有网页完整 HTML。
- 正文和证据片段设置权限与保留策略。
- 公开报告优先提供摘要、分析和原文链接。
- 避免未经许可大规模转载受版权保护内容。

robots.txt 不是法律授权，不能代替服务条款和版权审查。具体合规要求按来源、服务器所在地、用户所在地和用途评估。

---

# 17. 开发实施计划

## Phase 0：需求冻结与工程初始化

交付：

- V3 PRD。
- 竞品拆解。
- 国家与媒体来源候选表。
- Source Registry 字段与治理流程。
- 初始 Topic / Target / Stance / Frame Taxonomy。
- MVP ERD。
- 系统架构和数据流。
- 指标定义与分母规范。
- Dashboard Wireframe。
- 技术 ADR。
- 工程骨架、测试规范。

不做生产级爬虫和完整 AI 分析。先只读审计现有仓库，再制定改动。

## Phase 1：可信数据与对华基础分析

### P1-A 来源注册与采集
- 来源管理。
- BaseAdapter。
- RSS/API 和少量稳定 Web Adapter。
- 调度、重试、健康监控。
- 来源分类与审核。

验收：至少 5 个来源连续运行测试，失败可定位、可重试。

### P1-B 文章处理与存储
- 正文提取。
- 规范化。
- 语言识别。
- UTC 时间。
- URL/Hash 去重。
- 基础近似去重。
- 数据质量检查。

验收：文章可回溯 URL；关键字段完整；重复文章不重复进入核心统计。

### P1-C 对华文章分析
- 统一 Schema。
- Topic。
- Sentiment。
- Target-bound Stance。
- Frame。
- Entity。
- Evidence。
- Confidence。
- Unknown 状态。
- 模型抽象、缓存、预算、重试、版本管理。
- 人工抽样评估。

验收：每条分析有模型和 Prompt 版本；证据能定位原文；立场绑定明确目标。

### P1-D 核心指标与 Dashboard
实现 7 个核心指标：

1. Article Count。
2. Unique Story Count。
3. Attention Share（仅分母可靠时）。
4. Sentiment Distribution。
5. Target-bound Stance Distribution。
6. Frame Distribution。
7. Topic Share。

页面：

- 对华舆情总览。
- 国家对华分析。
- 跨国对比基础版。
- 数据质量。
- 日报/周报。

验收：统计口径、分母、时区清楚；事实结论有证据；样本不足有提示；指标可下钻至文章。

## Phase 2：跨国比较深化与叙事变化

- 跨语言转载识别。
- 多语言 Embedding。
- Story Cluster 改进。
- 事件召回、聚类、关系和生命周期。
- 人工合并/拆分与修订历史。
- 事件级指标。
- 跨国事件叙事比较。
- Narrative Baseline。
- Frame Entropy。
- Narrative Shift。
- Persistence。
- Source Convergence。
- 基础异常检测。

验收：人工标注集评估；控制 False Merge；基线达到样本门槛后才启用正式变化判断。

## Phase 3：研究型 Agent 与风险研究

- 自然语言查询。
- 文章、来源、主题、事件、趋势查询工具。
- 跨国比较研究。
- 多步骤专题研究。
- Evidence Validator。
- 自动报告。
- 研究提示信号。
- 可配置指标（必要时）。
- 复杂研究流程编排。

验收：不虚构数据库事实和引用；正式结论经证据验证；复杂推断明确标记；风险提示公开触发条件和限制。

---

# 18. MVP 验收标准

1. 来源可注册、分类、审核、停用。
2. 至少 5 个稳定来源可持续采集。
3. 采集任务有状态、日志、重试和错误记录。
4. 文章可规范化、清洗、识别语言和标准化时间。
5. 精确去重与基础近似去重可工作。
6. 对华 Topic、Sentiment、Stance、Frame 分析可工作。
7. Stance 绑定明确 Target。
8. Evidence Span 能定位原文。
9. 分析记录模型、Prompt、Schema 和 Taxonomy 版本。
10. LLM 调用有缓存、预算和失败降级。
11. Dashboard 展示对华关注度（分母可用时）、主题、情感、立场、框架、国家比较和来源覆盖。
12. 日报、周报可生成并追溯证据。
13. 所有比例展示分母和统计范围。
14. 数据质量与分析质量分开评估。
15. 采集、分析、报告任务可独立运行；单条失败不终止批次。
16. 图表可下钻至文章和证据。
17. 样本不足、数据缺失、来源覆盖偏斜时有明确提示。

事件聚类、正式 Narrative Shift、复杂风险模型和研究型 Agent 不属于 MVP 验收项。

---

# 19. 推荐项目目录

```text
gni/
├── README.md
├── pyproject.toml
├── docker-compose.yml
├── .env.example
├── docs/
│   ├── PRD.md
│   ├── ARCHITECTURE.md
│   ├── DATABASE.md
│   ├── DATA_SCHEMA.md
│   ├── SOURCE_REGISTRY.md
│   ├── TAXONOMY.md
│   ├── AI_ANALYSIS.md
│   ├── METRICS.md
│   ├── DASHBOARD.md
│   ├── API_SPEC.md
│   ├── COMPLIANCE.md
│   ├── DEVELOPMENT_PLAN.md
│   └── ADR/
├── src/gni/
│   ├── core/
│   ├── sources/
│   ├── ingestion/
│   ├── processing/
│   ├── analysis/
│   ├── metrics/
│   ├── reports/
│   ├── api/
│   ├── dashboard/
│   └── infrastructure/
├── migrations/
├── scripts/
├── tests/
└── data/samples/
```

目录可按现有仓库调整，不要为了符合模板重写已有项目。

---

# 20. 风险与控制

| 风险 | 控制措施 |
|---|---|
| 来源不稳定 | 来源准入与健康监控 |
| 官方属性判断错误 | 人工审核、证据、变更历史 |
| 样本代表性不足 | 明确样本边界、国家与来源覆盖 |
| Attention 分母不完整 | 不计算或明确标记估算/不可用 |
| 转载放大关注度 | Article Count 与 Unique Story Count 分开 |
| LLM 成本失控 | 分级分析、缓存、预算、队列 |
| 跨语言转载误判 | Phase 2 标注集与评估 |
| 事件错误合并 | 控制 False Merge、人工纠错 |
| 立场/情感误判 | Target 绑定、证据定位、Unknown 状态 |
| 冷启动误报 | 基线成熟度、样本量门槛 |
| 指标口径变化 | 指标版本、分母、时区、来源范围 |
| Dashboard 误读 | 统一筛选、样本量、口径说明、下钻证据 |
| Agent 幻觉 | 证据绑定与发布前验证 |
| 版权/条款风险 | 来源准入审查、必要内容保存、限制再分发 |
| 过早复杂化 | Modular Monolith，推迟复杂调度和微服务 |

---

# 22. 最终建设原则

建设顺序：

**中国中心研究目标 → 可靠来源样本 → 对华文章分析 → 7 个核心指标 → Dashboard 与报告 → 跨国比较深化 → 叙事变化 → 研究 Agent。**

必须坚持：

1. 研究对象固定为中国及相关 Target；国家是观察样本维度。
2. “全球”是多国来源覆盖，不代表全球公众舆论。
3. 媒体表达不等于政府意图或公众民意。
4. Article、Event、Narrative 是不同分析层级。
5. 情感、立场、框架、关注度分别定义。
6. 立场必须绑定 Target。
7. 转载数量不能直接等同关注度。
8. 所有比例公开分母、样本范围和时间窗口。
9. 来源分类和分析结果可追溯、可修订、可版本化。
10. 无证据的事实性结论不能进入正式报告。
11. Phase 1 先把 7 个核心指标做准，不为“指标齐全”提前开发高级分析。
12. 叙事变化与风险判断必须建立在历史数据、来源覆盖、样本量和证据之上。
13. 数据质量与舆情结论分开呈现。
14. 先建立连续运行、口径稳定、证据可查、结果可复核的系统，再逐步提高智能程度。

**MVP 的首要目标不是看起来像一个复杂的全球情报平台，而是可靠地回答：其他国家的官方媒体最近如何报道中国、关注中国什么、如何评价中国，以及这些表达之间有什么可验证的差异。**

---

# 22. V4.0 产品方向校准：从研究分析平台转为 Agent 驱动的监测系统

> **本章及第 22 章以后是 V4.0 对前文的正式修订。若前文与本章在产品优先级、MVP 范围或 Agent 定位上存在冲突，以 V4.0 修订为准。前文的数据治理、证据追溯、指标透明、来源合规、目标对象区分等原则继续有效。**

## 21.1 核心产品定义

GNI 是一个以 Agent 为核心的全球官方媒体对华舆情监测系统。系统持续监测其他国家的官方媒体及经审核的官方传播来源，自动收集涉华报道，识别文章中与中国相关的内容，分析报道情感倾向、具体目标立场、主题与叙事框架，计算可解释的舆情指标，并主动发现重大涉华新闻、突发事件和异常变化，自动生成日报、周报、月报及专题简报。

产品的第一价值不是让用户手动探索大量图表，而是让系统持续完成：

1. **自动监测：** 持续发现和收集新发布的涉华报道。
2. **自动理解：** 理解文章中真正与中国相关的内容，而非不加区分地分析全文。
3. **自动判断：** 识别正面、负面、中性、混合或无法判断的情感倾向，并绑定具体 Target。
4. **自动量化：** 根据相关度权重计算报道贡献、分布、趋势和比较结果。
5. **自动发现：** 发现重大新闻、突发事件、报道激增、情感变化和跨来源同步关注。
6. **自动交付：** 生成有证据、有链接、有统计口径的日报、周报、月报和预警。
7. **主动提醒：** 当满足明确触发规则时，主动向用户推送值得关注的变化。

深度叙事研究仍然保留，但主要承担解释“为什么发生变化”的作用，不再是 MVP 的首要交付目标。

## 21.2 目标与非目标

### 产品目标
- 让用户快速了解被监测官方媒体近期如何报道中国。
- 量化正面、负面、中性报道的数量、比例、强度和变化。
- 定位哪些国家、媒体、议题和具体 Target 贡献了变化。
- 及时发现重大涉华新闻与突发报道集群。
- 自动生成周期报告和有证据的异常提醒。
- 每一个分数、结论、事件和提醒都可以回溯到文章、原文片段、来源和计算口径。

### 产品非目标
- 不将媒体报道直接等同于国家政府立场、政策意图或公众民意。
- 不建立没有解释依据的“国家对华态度总分”。
- 不因一篇负面报道自动认定为重大事件或风险。
- 不以生成一段摘要替代文章理解、证据提取和指标计算。
- 不要求用户必须先掌握复杂研究方法才能使用系统。
- 不在 MVP 阶段追求完全自主、无人工监督的开放式研究 Agent。

## 21.3 用户核心工作流

主要工作流：

`打开总览 / 接收提醒 → 查看整体对华舆情 → 查看国家与媒体变化 → 查看重点新闻/事件 → 阅读代表性文章与证据 → 查看日报/月报 → 按需开展深入分析`

默认首页首先展示“现在发生了什么、哪些变化值得关注、系统为什么这样判断”，而不是首先展示复杂指标定义和研究工具。

## 21.4 结论对象必须准确表述

标准表达：
- “本系统监测的 X 国官方媒体样本中，负面涉华报道占比上升。”
- “被监测的 X 家官方媒体在过去 24 小时集中报道某一涉华事件。”
- “该来源样本的加权情感分数较其自身历史基线下降。”

禁止无证据扩大为：
- “X 国对中国态度恶化。”
- “X 国政府决定改变对华政策。”
- “该国民众普遍反华。”

---

# 23. 文章理解与结构化分析：先理解涉华内容，再量化

## 22.1 总体原则

文章分析采用“原文理解 → 涉华内容定位 → 结构化提炼 → 量化计算”的流程。不得先把整篇文章压缩成一段摘要，再只根据摘要打标签和计算所有指标。

原因：摘要可能遗漏限定条件、引述主体、反讽、不同 Target、文章内部观点冲突和中国相关内容的实际占比。统计必须建立在可定位的原文内容和结构化字段上。

推荐流程：

1. **读取与整理原文：** 保留标题、导语、正文、作者、发布时间、来源、语言和段落结构。
2. **识别涉华范围：** 找出标题、导语、段落、句子或片段中与中国及细分 Target 相关的内容。
3. **判断文章涉华重要性：** 判断中国是核心主题、重要次主题还是顺带提及；计算 China Relevance Weight。
4. **拆分分析对象：** 识别文章谈论的 Topic、被评价的 Target、观点主体和引用主体。
5. **分析情感与立场：** 对媒体报道自身的表达和针对具体 Target 的立场分别判断。
6. **提取框架、主张与证据：** 识别主要叙事框架、关键 Claims、Reasons 和 Evidence Spans。
7. **生成阅读摘要：** 为用户阅读生成简洁摘要；摘要不替代结构化分析。
8. **质量检查：** 对低置信度、矛盾、引用混淆、多 Target 和低相关度文章标记复核状态。
9. **聚合量化：** 由确定性计算模块根据文章级结构化结果生成指标。

## 22.2 六个文章理解维度的职责

六个维度保留，但按“核心统计字段”和“解释性字段”区分：

| 维度 | 字段职责 | 是否进入核心统计 | 说明 |
|---|---|---|---|
| Topic | 文章讨论的涉华主题 | 是 | 支持主题分布、主题趋势、国家比较 |
| Target | 文章具体讨论或评价的对象 | 是 | 所有立场和情感聚合都必须明确统计对象 |
| Sentiment | 涉华内容的情感倾向 | 是，核心 | 正面、负面、中性、混合、未知；可计算分布和情感分数 |
| Stance | 对具体 Target 的态度/立场 | 是，辅助 | 支持、认可、批评、反对、未表达、混合、未知；与情感分离 |
| Frame | 文章如何组织和解释涉华议题 | 是，辅助 | 多标签叙事框架分布，不直接压缩为正负分 |
| Claims / Evidence | 关键观点、理由、证据和原文定位 | 不直接作为情感计数 | 用于解释、核验、报告引用、质量控制和 Agent 推理 |

每个维度都应支持 `primary` 与 `secondary`（适用时），并保留字段级置信度与状态。不能因为文章只有一个总摘要，就丢失多个 Topic、Target 或互相矛盾的观点。

## 22.3 涉华内容与整篇文章的区别

系统需要区分三个层次：

- **Article-level relevance：** 整篇文章与中国议题的相关程度。
- **China-related segment：** 文章中具体谈论中国的句子、段落或内容片段。
- **Target-level expression：** 该片段对 China、Chinese Government、某企业、某政策或其他具体 Target 的评价。

情感和立场优先基于涉华片段判断，并结合全文上下文避免断章取义。不得把文章中关于美国、欧洲或其他国家的负面情绪自动计入对华负面情感。

## 22.4 观点主体与媒体表达主体

分析必须区分：
- 媒体记者/编辑的叙述性表达；
- 被采访者、专家、政府官员、反对派、社交媒体用户等被引用主体的表达；
- 文章对引用观点的支持、质疑、反驳或中性转述。

例如，报道引用某官员称“中国构成威胁”，不能仅凭这句话就判定媒体自身明确持有该立场。若文章只是客观转述，Sentiment 可为 Neutral，Stance 可为 No Explicit Stance / Reported View，而将被引用者的观点单独存入 Claim/Attributed Opinion。

## 22.5 分析结果数据结构建议

每篇文章的分析结果至少包含：

```json
{
  "article_id": "...",
  "china_relevance": {
    "weight": 0.0,
    "level": "core|major|minor|incidental|not_relevant",
    "estimated_share": 0.0,
    "title_mentions_china": false,
    "lead_mentions_china": false,
    "china_is_primary_subject": false,
    "rationale": "...",
    "confidence": 0.0
  },
  "topics": [
    {"topic_id": "...", "role": "primary|secondary", "confidence": 0.0}
  ],
  "targets": [
    {"target_id": "China", "prominence": "primary", "confidence": 0.0}
  ],
  "sentiment": {
    "label": "positive|negative|neutral|mixed|unknown",
    "score": 0.0,
    "intensity": 0.0,
    "confidence": 0.0,
    "basis_segment_ids": []
  },
  "stances": [
    {"target_id": "China", "label": "supportive|critical|opposing|no_explicit_stance|mixed|unknown", "strength": 0.0, "confidence": 0.0, "evidence_ids": []}
  ],
  "frames": [
    {"frame_id": "...", "role": "primary|secondary", "confidence": 0.0, "evidence_ids": []}
  ],
  "claims": [],
  "evidence_spans": [],
  "summary": "...",
  "analysis_status": "completed|needs_review|insufficient_evidence|failed"
}
```

上述为逻辑示例，最终字段、枚举和类型必须在 Phase 0 通过 Schema/ADR 冻结；禁止将示例中的值直接当作已经验证的分类体系。

## 22.6 Unknown、Neutral、Mixed 等状态严格区分

- `Neutral`：文本确实表达中性或平衡的报道语气/立场。
- `No Explicit Stance`：文章没有明确表达对目标的支持或反对。
- `Mixed`：同一分析对象存在实质性正负并存或相互冲突的表达。
- `Unknown`：模型无法可靠确定。
- `Ambiguous`：文本有多种合理解释，无法消歧。
- `Insufficient Evidence`：可用文本太少或证据不足。
- `Not Applicable`：该字段不适用于当前对象。

不得把 Unknown 当 Neutral，也不得为满足报表完整性而强制打分。

---

# 24. China Relevance Weight：涉华相关度加权机制

## 23.1 设计目标

用户提出：如果一篇文章只有 20% 内容讨论中国，其对整体对华舆情统计的贡献不应与一篇全文讨论中国的文章相同。GNI 采用 `China Relevance Weight`（涉华相关度权重）表达文章对中国议题的实际相关程度。

例如：某篇文章的涉华情感分数为 -0.8，涉华相关度权重为 0.2，则该文对加权情感分子的贡献为 -0.16。文章仍然是 1 篇真实报道，但其加权贡献只有 0.2。

**关键原则：权重用于表达统计贡献，不用于篡改原始文章数量；原始数量和加权数量必须并列展示。**

## 23.2 权重不能只按字数比例计算

涉华文本字数占比是重要信号，但不是唯一标准。若简单按字数计算，会产生明显误差：标题和导语中的核心议题可能只有少量文字；短新闻可能全文涉华；长篇背景报道可能只有一小段涉及中国。

权重应综合以下特征：

1. `content_share`：正文中涉华句子/段落/有效词数占比。
2. `title_prominence`：标题是否直接以中国或具体中国目标为核心。
3. `lead_prominence`：导语是否将中国作为核心对象。
4. `primary_subject`：中国是否为文章主要讨论对象。
5. `argument_centrality`：文章的核心论点是否围绕中国展开。
6. `target_prominence`：明确中国 Target 在文章中的重要性。
7. `contextual_relevance`：中国是否只是背景、比较对象或偶然提及。

建议 MVP 先使用可解释的规则/等级映射，再通过人工标注数据校准；不要一开始就设计不可解释的复杂权重模型。

## 23.3 初始权重等级（待标注集校准）

可作为 Phase 0/Phase 1 初始规则的候选：

| Level | 说明 | 初始权重区间建议 |
|---|---|---:|
| Core | 中国是文章核心对象，标题/导语/主体论点均明显涉华 | 0.85–1.00 |
| Major | 中国是重要议题之一，存在实质性篇幅与论点 | 0.60–0.84 |
| Moderate | 中国是明确次要议题，有一定分析内容 | 0.30–0.59 |
| Minor | 仅有有限篇幅或背景性讨论 | 0.10–0.29 |
| Incidental | 仅顺带提及，无实质分析 | 0.01–0.09 或不进入核心舆情统计 |
| Not Relevant | 与中国无实质关系 | 0.00 |

这些数值只是初始设计区间，不是已经验证的客观比例。Phase 0 应抽取不同长度、不同语言、不同版式文章进行人工标注，确定等级定义和权重映射。不得把 `estimated_share` 与最终 `weight` 混为一谈：前者是涉华内容比例估计，后者是综合相关度权重。

## 23.4 权重计算策略

MVP 建议：

- 先让模型识别涉华片段并估算涉华内容比例；
- 再判断标题、导语、主体论点和 Target prominence；
- 根据明确规则映射到权重；
- 对边界案例标记 `needs_review`；
- 保存权重版本、规则版本、输入特征、理由和置信度。

后续如采用可训练模型或统计模型，必须与规则基线对照评估，证明能提升人工标注一致性。

## 23.5 统计使用规则

保留两套视图：

**A. 原始报道视图**
- Article Count：符合纳入条件的原始文章数。
- Unique Story Count：独立故事数（如已具备可靠故事识别）。
- Source Count：来源数。
- Country Count：国家数。

**B. 加权贡献视图**
- Weighted Article Volume：`Σ w_i`。
- Weighted Positive Volume：`Σ w_i × I(positive)` 或连续情感正向贡献。
- Weighted Negative Volume：`Σ w_i × I(negative)` 或连续情感负向贡献。
- Weighted Neutral Volume：`Σ w_i × I(neutral)`。
- Weighted Sentiment Score：按权重计算的加权平均情感分数。

例：三篇文章权重分别为 1.0、0.5、0.2，则原始 Article Count = 3，Weighted Article Volume = 1.7。两者回答不同问题，不能互相替代。

## 23.6 情感分布与加权情感分数

建议同时展示：

1. **Raw Sentiment Distribution：** 按文章数统计正面、负面、中性、混合、未知的原始分布。
2. **Weighted Sentiment Distribution：** 以 China Relevance Weight 加权的分布。
3. **Weighted Sentiment Score：** 在明确的数值映射和有效样本范围内计算连续得分。
4. **Coverage / Confidence：** 显示成功判断的权重覆盖率、未知权重占比、样本数。

不得只显示一个得分。一个分数无法表达正负报道同时大量增加的情况，也无法表达样本量和不确定性。

## 23.7 加权情感分数公式

若 Sentiment Score `s_i ∈ [-1, +1]`，China Relevance Weight `w_i ∈ [0,1]`，则：

`Weighted Sentiment Score = Σ(w_i × s_i) / Σ(w_i)`

仅对符合分析纳入规则且有有效情感分数的文章计算。Mixed、Unknown、Insufficient Evidence 的处理必须在指标定义中明确，不能默默当作 0。建议默认：Unknown/Insufficient Evidence 不进入情感分数分母，但单独报告其数量与权重；Mixed 可保留独立类别，若转换为连续分数必须有明确、经过标注验证的规则。

## 23.8 权重不能解决所有偏差

- 文章篇幅长不代表影响力大。
- 权重不代表媒体影响力、受众规模或传播效果。
- 同一通讯社转载可能造成重复贡献，需结合 Story/Original 统计。
- 不同语言的分词和正文提取方式不同，content_share 不应依赖未经校准的词数直接横向比较。
- 低相关度文章可以在原始文章库中保留，但可在核心舆情指标中设置纳入阈值；阈值必须公开并可配置。
- 应同时提供未加权和加权结果，便于用户识别权重机制造成的差异。

---

# 25. Sentiment 与 Stance 量化和打分规范

## 24.1 Sentiment 的定义

Sentiment 评估的是报道中与中国相关内容的表达倾向/语气，而不是简单判断事件本身好坏，也不是统计被引述者的情绪。

建议类别：
- Positive
- Neutral
- Negative
- Mixed
- Unknown

建议连续分数范围：`[-1.0, +1.0]`。

初始分段仅用于产品展示，不可视为天然客观边界：
- `+0.60 ~ +1.00`：强正面
- `+0.20 ~ +0.59`：偏正面
- `-0.19 ~ +0.19`：接近中性（仍需结合 Neutral 标签）
- `-0.59 ~ -0.20`：偏负面
- `-1.00 ~ -0.60`：强负面

分数必须与分类标签、置信度、证据片段一起保存。模型不得仅凭主观语气给出高精度小数；初期可以使用离散档位映射成区间中值，避免伪精确。

## 24.2 Stance 的定义

Stance 表示报道对某个明确 Target 的支持、认可、批评、反对或未明确表态。Stance 必须绑定 Target，且与 Sentiment 分离。

示例：
- 文章负面描述中国经济增长放缓，但对中国政府的政策没有明确立场。
- 文章中性报道某项外交协议，同时明确支持协议中的合作安排。
- 文章批评某家中国企业，但并不批评中国政府或中国社会。

不得把针对企业、政策、个人或单一事件的批评自动扩展为对 China 的整体负面立场。

## 24.3 多 Target 文章

同一文章可以对多个 Target 给出不同情感和立场。系统应按 Target 分别保存分析结果，聚合时必须指定 Target。若用户查看默认 China 总览，只能纳入确实指向 China 的表达；细分目标应独立统计或通过明确的父子 Target 规则汇总。

## 24.4 分数校准与质量门槛

- 建立人工标注样本，覆盖多语言、不同来源类型、不同新闻体裁、引用新闻、评论、讽刺、标题党和多 Target 场景。
- 分别评估情感分类准确率、正负面 Precision/Recall/F1、连续分数与人工等级的一致性、Target 绑定准确率。
- 对不同语言单独检查性能，不得仅凭英语测试结果推断所有语言可靠。
- 对模型输出置信度做校准；模型自报 confidence 不能直接当作统计置信区间。
- 低置信度或关键字段冲突时进入人工复核/不确定状态。
- 模型、Prompt、Taxonomy 或分数映射变化时创建新版本，历史分析可重算且保留旧版本。

---

# 26. Agent 能力架构与运行模式

## 25.1 Agent 不等于一个无限制聊天机器人

GNI Agent 应是一个受控的任务编排与分析执行系统。它调用采集、文章分析、指标计算、事件发现、报告生成和证据验证等明确能力；不能凭语言模型直接编造数字或事实。

建议采用“确定性工作流 + LLM 语义判断 + 证据验证”的混合架构：
- 采集调度、计数、分母、加权求和、趋势计算、阈值触发由确定性程序完成。
- 文章语义理解、事件候选解释、摘要和报告自然语言由 LLM 完成。
- 重要结论、数字和引用由验证步骤回查结构化数据与原文。

## 25.2 Agent 角色/子任务划分

初期不必部署多个自治 Agent 服务，可以先在一个应用内实现可测试的任务模块：

1. **Monitoring Agent：** 检查来源更新、调度抓取、发现新文章、处理失败重试。
2. **Article Intelligence Agent：** 识别涉华内容、相关度、Topic、Target、Sentiment、Stance、Frame、Claims 和证据。
3. **News/Event Triage Agent：** 识别新闻重要性、突发性、跨来源报道集群和事件进展候选。
4. **Trend & Alert Agent：** 计算变化、执行预警规则、生成触发原因。
5. **Reporting Agent：** 生成日报、周报、月报和重大新闻简报。
6. **Evidence QA Agent / Validator：** 验证报告中的数字、文章引用、链接、时间和结论是否有真实数据支持。

这些角色是职责边界，不要求在 MVP 中拆成独立微服务或不同模型。

## 25.3 Agent 工具边界

Agent 可调用的工具应是明确、可审计的函数：
- `list_active_sources`
- `fetch_source_updates`
- `get_unprocessed_articles`
- `get_article_content`
- `analyze_article`
- `get_metric_definition`
- `calculate_metric`
- `query_articles`
- `query_country_summary`
- `query_trend_series`
- `detect_news_clusters`
- `get_event_evidence`
- `create_report_draft`
- `validate_report_claims`
- `create_alert_candidate`

所有工具参数、调用时间、结果、错误和关联任务 ID 必须记录。Agent 不得直接改写原始文章、覆盖历史分析或静默修改指标定义。

## 25.4 Agent 任务模式

- **Scheduled Monitoring：** 定时执行，自动收集与分析。
- **Event-triggered Processing：** 新文章到达或阈值触发后处理。
- **On-demand Query：** 用户主动查询国家、主题、媒体或时间范围。
- **Report Generation：** 按日/周/月生成报告。
- **Alert Investigation：** 对异常信号进一步收集证据并形成解释。

每个任务具备 `task_id`、触发来源、时间范围、输入范围、状态、执行日志、产出、错误和重试信息。

## 25.5 Agent 的禁止行为

- 不允许 LLM 自行编造报道量、百分比、得分、排名或时间序列。
- 不允许没有文章证据就声称发生重大事件。
- 不允许把媒体表达推断为政府真实意图。
- 不允许将 Unknown 自动填成 Neutral。
- 不允许把引用观点自动当作媒体自身观点。
- 不允许为了报告完整而生成不存在的文章链接、来源或引用。
- 不允许在没有数据覆盖说明的情况下输出“全球媒体”结论。

---

# 27. 重大新闻、突发事件与新闻重要性识别

## 26.1 为什么必须区分新闻重要性与情感倾向

新闻重大程度、突发程度、对华情感倾向是三个独立维度：
- 一篇报道可能非常负面，但事件并不重大。
- 一件重大外交事件可能被中性报道。
- 一项突发新闻可能尚无明确情感倾向。

因此，不得以负面分数作为重大新闻判断的替代变量。

## 26.2 重要性候选维度

新闻重要性可以综合候选信号：
- 事件本身影响范围与后果；
- 是否涉及国家领导人、政府政策、外交、安全、重大经济或科技事件；
- 是否有多个独立来源报道；
- 是否跨多个国家/地区被报道；
- 报道量相对该来源历史基线是否异常；
- 是否具有明显时效性；
- 是否有官方声明、正式文件或可核验事实支撑。

每个维度需要独立记录依据。不能只凭模型主观判断输出一个高分。

## 26.3 突发性识别

突发性主要看事件首次出现、报道量增长速度和短时间内的来源扩散：
- First Seen：系统首次发现时间。
- Estimated Event Time：事件实际发生时间（如可识别）。
- Coverage Velocity：单位时间新增报道数。
- Source Spread：新增独立来源数量。
- Country Spread：新增国家数量。
- Baseline Deviation：相对该来源/议题历史报道量的偏离。

首次发现时间不能冒充事件实际发生时间。历史基线不足时，只能标记“报道集中/快速增长”，不应声称统计意义上的异常。

## 26.4 Phase 1 与 Phase 2 的实现边界

**Phase 1 基础热点发现：**
- 通过时间窗口、标题/实体/关键词相似度、文章发布时间和来源信息形成候选新闻簇。
- 提示短时间内报道量较高的主题或事件候选。
- 由 Agent 总结候选事件，列出相关报道和不确定性。
- 允许人工合并、拆分和标记误报。

**Phase 2 事件识别增强：**
- 跨语言语义聚类。
- 事件实体、时间、地点、参与方和因果链抽取。
- same_event / follow_up / sub_event / related_event / new 关系判断。
- 事件生命周期和多国报道差异。
- 事件聚类版本和人工修订记录。

## 26.5 重大新闻简报结构

每条重大新闻至少输出：
1. 标题/事件名称。
2. 发生了什么（事实摘要）。
3. 事件发生时间与系统首次发现时间。
4. 涉及的中国 Target 和 Topic。
5. 哪些国家、哪些被监测官媒进行了报道。
6. 报道数量、独立来源数、国家覆盖数。
7. 正面/负面/中性报道分布及加权结果（样本足够时）。
8. 各媒体报道角度和主要差异。
9. 代表性文章与原文链接。
10. 重要性/突发性判断依据及置信度。
11. 当前未知信息与数据覆盖限制。

---

# 28. 日报、周报、月报与主动预警

## 27.1 报告不是把 Dashboard 截图拼在一起

报告 Agent 应从指标结果、文章库、事件候选和证据库读取结构化数据，按固定模板生成内容，再经过数字与引用校验。自然语言生成不能改变统计结果。

## 27.2 日报（Daily Brief）

目标：回答“过去 24 小时被监测官方媒体如何报道中国，有什么值得关注的事？”

建议结构：
1. **今日概览：** 涉华文章数、加权文章量、监测国家/来源覆盖、与前一可比窗口的变化。
2. **情感分布：** 正面/负面/中性/混合/未知的原始及加权分布。
3. **国家观察：** 报道量或情感变化最明显的国家样本，并显示样本数。
4. **重点负面报道：** 代表性文章、Target、Topic、情感理由和原文链接。
5. **重点正面报道：** 同上。
6. **重大新闻/突发事件：** 事件摘要、报道国家、来源和证据。
7. **异常变化：** 触发规则、比较基线、样本量、代表文章。
8. **数据质量：** 采集失败、来源离线、正文提取异常、分析未完成等。
9. **今日限制：** 数据覆盖、低样本、无法判断比例和其他重要限制。

## 27.3 周报（Weekly Brief）

目标：回答“本周对华媒体舆情相对上周发生了什么变化？”
- 周内每日走势与上周可比窗口。
- 各国对华报道量、加权量和情感分布。
- 正负面变化较明显的国家/来源/Topic/Target。
- 本周重大新闻及事件进展。
- 连续多日出现的叙事或报道主题。
- 重点媒体观察。
- 数据质量和覆盖变化。

## 27.4 月报（Monthly Brief）

目标：回答“本月整体对华报道格局如何，哪些变化具有持续性？”
- 月度总体报道量和加权报道量。
- 国家/来源排名与覆盖变化。
- 情感分布及月度趋势。
- Topic 与 Target 结构变化。
- 重大事件回顾。
- 持续性负面/正面主题观察。
- 跨国报道差异。
- 与过去 3/6/12 个月的可比基线。
- 本月数据限制和方法变化说明。

月报不能简单把每日情感分数取平均；必须基于底层文章级数据按统一口径重新计算。

## 27.5 报告比较窗口

- 日报默认与前一相同长度窗口比较；必要时增加过去 7 天同星期基线。
- 周报与上一周比较，同时可显示过去 4 周趋势。
- 月报与上月比较，并在数据成熟时提供滚动 3/6/12 个月趋势。
- 节假日、重大事件、来源新增/停用和采集故障需显式提示。

## 27.6 主动预警类型

建议初始规则：
- `VOLUME_SPIKE`：某国家/来源/Topic 涉华报道量突然增长。
- `NEGATIVE_SHARE_RISE`：负面报道占比或加权负面量明显上升。
- `POSITIVE_SHARE_RISE`：正面报道占比或加权正面量明显上升。
- `SENTIMENT_SHIFT`：加权情感分数相对自身历史基线显著变化。
- `MULTI_COUNTRY_COVERAGE`：同一事件在多个国家媒体中集中出现。
- `SOURCE_BURST`：单一来源短期集中发布相关报道。
- `TOPIC_EMERGENCE`：某涉华议题在样本中快速出现或上升。
- `MAJOR_EVENT_CANDIDATE`：重大新闻候选被识别。
- `SOURCE_HEALTH_FAILURE`：来源采集异常（数据质量提醒，不是舆情提醒）。

每条预警包含：触发规则、观察窗口、比较基线、阈值、原始样本数、加权样本量、国家/来源范围、代表文章、置信度和限制。

## 27.7 预警去重与升级

- 相同对象、同一规则、相邻窗口重复触发时进行合并或抑制。
- 若信号持续增强、扩展到更多国家或出现新证据，可升级提醒。
- 记录首次触发、最近触发、解除时间和状态变化。
- 用户可订阅国家、来源、Topic、Target、严重程度和报告频率。
- 不得为提高提醒数量而降低阈值；应支持提醒质量评估和误报反馈。

---

# 29. 指标体系 V4.0：新增运营指标与加权舆情指标

原有 7 + 4 + 1 指标体系继续作为研究指标库，但 V4.0 需要增加面向监测产品的运营与舆情指标。建议分成四类，避免把不同意义的指标混成一个总分。

## 28.1 A. 报道规模与覆盖
- `Article Count`：符合纳入条件的原始涉华文章数。
- `Unique Story Count`：独立报道故事数（可靠聚类后启用）。
- `Weighted Article Volume`：Σ China Relevance Weight。
- `Original Reporting Count`：原创报道数量（具备可靠识别时）。
- `Source Count`：实际贡献报道的来源数。
- `Country Count`：实际有报道的国家数。
- `Source Coverage Rate`：正常运行且成功采集的来源占计划监测来源比例。
- `Ingestion Success Rate`：采集任务成功率。
- `Article Extraction Success Rate`：正文成功提取比例。

## 28.2 B. 情感舆情
- `Raw Sentiment Distribution`：原始文章正面/负面/中性/混合/未知分布。
- `Weighted Sentiment Distribution`：按涉华相关度权重计算的分布。
- `Weighted Sentiment Score`：Σ(w×s)/Σ(w)，按有效分数规则计算。
- `Weighted Positive Volume`：正面文章的相关度权重之和。
- `Weighted Negative Volume`：负面文章的相关度权重之和。
- `Negative-to-Positive Ratio`：负面与正面加权量之比；分母为零时返回 N/A，不返回无穷大。
- `Sentiment Coverage`：具备有效情感判断的文章权重占纳入文章权重的比例。

## 28.3 C. 议题与来源
- `Topic Share` / `Topic Count`。
- `Target Share` / `Target Count`。
- `Frame Share` / `Frame Count`。
- `Source Sentiment Profile`：单来源情感分布。
- `Country Sentiment Profile`：国家来源样本情感分布。
- `Source Contribution Share`：单来源对当前范围加权文章量的贡献。

## 28.4 D. 事件与变化
- `Coverage Velocity`：单位时间新增报道数。
- `Source Spread`：事件覆盖的独立来源数。
- `Country Spread`：事件覆盖国家数。
- `Baseline Deviation`：当前值与历史基线差异。
- `Sentiment Shift`：情感分布或加权分数变化。
- Phase 2 的 Frame Entropy、Narrative Shift、Persistence、Source Convergence。

## 28.5 分数与排名的展示约束

- 任何排名必须显示样本数、加权样本量和统计窗口。
- 任何国家比较必须显示来源覆盖、来源类型和数据质量。
- 不同国家的来源数量、媒体产量和样本构成差异很大时，应避免只按原始数量排序。
- 低样本量可显示“样本不足”，不强行排名。
- 任何分数都必须提供计算说明和可下钻文章。
- 不能把加权情感分数称为“国家对华态度分”。推荐称“被监测官媒样本加权情感分数”。

---

# 30. Dashboard V4.0：以监测任务和 Agent 交付为中心

## 29.1 主导航建议

1. **舆情总览（Overview）**
2. **国家监测（Countries）**
3. **重大新闻/事件（News & Events）**
4. **文章库（Articles）**
5. **报告中心（Reports）**
6. **预警中心（Alerts）**
7. **来源与数据质量（Sources & Quality）**
8. **研究分析（Research，后续增强）**

## 29.2 首页总览

首页顶部：
- 今日/本周涉华文章数。
- 加权文章量。
- 当前正负面比例。
- 监测国家数与活跃来源数。
- 新增重大新闻候选数。
- 未处理高优先级提醒数。

首页核心区域：
- 全球/各国加权情感趋势。
- 国家报道量和情感变化排名。
- 重点负面报道、重点正面报道。
- 重大新闻与突发事件列表。
- 最新预警与触发原因。
- 本日 Agent 自动生成摘要。
- 采集和分析质量状态。

## 29.3 国家监测页面

- 国家样本与媒体来源构成。
- 报道量、加权报道量和情感趋势。
- 正面/负面/中性原始与加权分布。
- Topic、Target、Frame 分布。
- 贡献最大的来源。
- 国家样本近期重大新闻和异常提醒。
- 支持点击进入文章与证据。

## 29.4 重大新闻/事件页面

- 按时间、国家、Topic、重要性候选、突发程度筛选。
- 展示事件候选摘要、覆盖国家、独立来源、报道趋势。
- 显示事件中的正面/负面/中性报道分布。
- 展示不同国家媒体叙述差异。
- 支持事件误合并/拆分反馈（Phase 2 完整实现）。

## 29.5 文章库页面

过滤条件：国家、来源、日期、Topic、Target、Sentiment、Stance、Frame、China Relevance Level、分析状态、是否重大新闻关联。

列表字段：标题、来源、国家、发布时间、涉华权重、情感、立场、Topic、Target、事件/新闻簇、原文链接。

文章详情：涉华片段、摘要、分析结果、情感/立场证据、模型版本、分析置信度、原文链接和人工纠正入口。

## 29.6 报告中心

- 日报/周报/月报列表。
- 生成时间、数据截止时间、覆盖国家和来源。
- 报告版本、状态、校验状态。
- 查看报告、导出、重新生成。
- 每条结论可以展开查看支持它的文章和指标。

## 29.7 预警中心

- 预警级别、类型、国家、来源、Topic、Target、触发时间。
- 当前状态（新建/确认/调查中/已解除/误报）。
- 触发规则与计算细节。
- 代表性文章和证据。
- 用户反馈和误报标记。

## 29.8 可视化原则

- 情感分布和立场分布分开展示。
- 原始计数和加权量并列展示。
- 时间趋势必须显示文章样本量和来源覆盖。
- 正负面比例图必须显示 Unknown/Mixed 等类别，不能隐藏不确定样本。
- 地图仅作为地理覆盖辅助，不作为核心舆情判断页面。
- 所有图表可下钻至文章、证据和计算口径。

---

# 31. V4.0 系统流程与任务状态

## 30.1 端到端业务流程

`Source Registry → Scheduled Fetch → Article Parse → Normalize → China Relevance Detection → Segment Extraction → Article Intelligence → Quality Gate → Metric Aggregation → News/Event Triage → Trend/Alert Evaluation → Report Generation → Evidence Validation → Delivery`

注意：重大新闻候选识别可以与文章分析并行启动，但最终摘要应等待基本文章分析和证据提取完成。

## 30.2 任务状态

每篇文章处理状态建议：
- `discovered`
- `fetched`
- `parsed`
- `normalized`
- `relevance_assessed`
- `analyzed`
- `quality_checked`
- `included_in_metrics`
- `needs_review`
- `failed`
- `excluded`

状态变化必须记录时间、原因、执行任务和版本。失败可重试，人工排除需有原因。

## 30.3 重新分析与历史一致性

当 Prompt、模型、Taxonomy、权重规则或情感分数映射变化时：
- 新建分析版本，不覆盖旧结果。
- 记录变更原因和生效时间。
- 支持对指定文章范围重新分析。
- 指标结果绑定具体分析版本集合。
- 报告绑定具体指标运行版本。
- 历史报告保持可复现，不因后台模型升级静默改变。

## 30.4 失败隔离

- 单一来源失败不得阻断其他来源。
- 单篇文章解析失败不得阻断批次。
- LLM 超时或输出格式错误进入重试/备用策略。
- 指标计算失败不得发布不完整报告。
- 报告校验失败时标记 Draft/Failed，不得假装已成功发布。

---

# 32. 数据模型 V4.0 增补

在原有 MVP 实体基础上，新增或扩展：

## 31.1 文章相关
- `article_segments`：原文片段、段落/句子位置、语言、片段类型、涉华标记。
- `article_relevance_assessments`：相关度等级、estimated_share、weight、权重规则版本、特征、理由、置信度。
- `article_sentiments`：Target 或涉华片段维度的情感标签、连续分数、强度、置信度、证据。
- `article_stances`：target_id、stance_label、strength、evidence_ids。
- `article_frames`：frame_id、primary/secondary、置信度和证据。
- `article_claims`：主张、主张主体、归因主体、主张类型、Target、证据。
- `article_analysis_feedback`：人工纠正、反馈原因、修订人和时间。

## 31.2 监测与 Agent
- `agent_tasks`：任务类型、触发方式、输入范围、状态、日志、产出。
- `agent_tool_calls`：工具名称、参数摘要、执行状态、结果引用和耗时。
- `monitoring_runs`：监测周期、来源集合、成功/失败统计。
- `news_candidates`：新闻候选、重要性特征、突发性特征、状态。
- `news_candidate_articles`：候选与文章关系。
- `events` / `event_articles`：Phase 2 事件实体和关系。
- `alert_rules`：规则定义、阈值、作用范围、启停状态、版本。
- `alerts`：触发值、基线、样本、状态、证据和去重键。
- `alert_feedback`：确认、误报、忽略、备注。
- `reports` / `report_sections` / `report_claims` / `report_evidence`：报告及其结论证据映射。

## 31.3 指标与版本
- `metric_definitions`：公式、纳入规则、分母、版本。
- `metric_runs`：运行窗口、输入分析版本、结果、质量信息。
- `relevance_weight_versions`：涉华权重规则版本。
- `sentiment_scale_versions`：情感映射版本。
- `prompt_versions` / `model_versions` / `taxonomy_versions`。

具体数据库范式、主键、外键、索引和约束由 ERD/ADR 确定；以上是业务实体清单，不要求逐项机械建表。可将高度相关实体合理归并，但不得丢失版本和证据关系。

---

# 33. Phase 路线图 V4.0：重新排列优先级

## Phase 0：产品与数据定义冻结
必须交付：
- V4.0 PRD 与产品流程。
- 官方媒体来源分类和候选来源清单。
- Topic / Target / Sentiment / Stance / Frame taxonomy 初稿。
- China Relevance Weight 规则初稿与人工标注指南。
- 文章分析 JSON Schema。
- 指标公式、分母和纳入/排除规则。
- 日报、周报、月报模板。
- 重大新闻与预警规则草案。
- Dashboard wireframe。
- ERD、系统架构、数据流程、ADR。
- 小规模样本集和人工标注评估方案。
- 工程骨架、测试与日志规范。

## Phase 1：Agent 驱动的监测 MVP
必须实现：
1. 来源注册、治理和健康监测。
2. 定时采集、解析、标准化和基础去重。
3. 涉华识别和片段定位。
4. China Relevance Weight。
5. 六维文章理解（Topic、Target、Sentiment、Stance、Frame、Claims/Evidence）。
6. 原始与加权情感统计。
7. 国家、来源、Topic、Target 的基础比较。
8. 基础新闻热点/事件候选发现。
9. 日报和周报自动生成。
10. 重大新闻候选简报。
11. 基础规则预警和预警中心。
12. 证据验证、报告校验和质量面板。

MVP 不要求完整的跨语言事件图谱、复杂长期叙事分析或完全自主的研究 Agent。

## Phase 2：事件识别与趋势增强
- 跨语言转载/故事识别。
- 更可靠的事件聚类和事件生命周期。
- 多国同一事件报道比较。
- 月报深化和历史基线。
- Narrative Shift、Frame Entropy、Persistence、Source Convergence。
- 异常检测统计校准。
- 预警去重、升级、反馈学习。

## Phase 3：研究型 Agent 与高级分析
- 自然语言研究问题。
- 多步骤跨国家/主题/事件检索。
- 复杂证据链和报告验证。
- 可配置研究模板。
- 高级专题分析与趋势解释。
- 更成熟的风险/研究信号规则。

## 32.1 MVP 开发顺序建议

即使 Phase 1 功能都属于 MVP，也建议按可验证依赖分批交付：

- Sprint A：来源治理、采集、文章标准化、数据质量。
- Sprint B：涉华识别、片段定位、相关度权重、文章分析 Schema。
- Sprint C：情感/立场质量评估、指标计算、国家/来源聚合。
- Sprint D：舆情总览、文章库、证据下钻。
- Sprint E：热点/新闻候选、日报/周报、报告验证。
- Sprint F：预警规则、预警中心、运行监控与验收。

每个 Sprint 应有独立验收，不允许仅凭页面可见就认定后端分析准确。

---

# 34. V4.0 MVP 验收标准

## 33.1 数据与来源
- 来源可添加、审核、启停、记录属性证据和合规状态。
- 每次采集有任务记录、成功率、错误、重试和最近更新时间。
- 每篇文章保留原始 URL、规范 URL、来源、发布时间、首次发现时间和正文版本。
- 采集、解析、分析失败可独立识别，不互相污染。

## 33.2 涉华识别与相关度
- 能识别文章是否实质涉华。
- 能定位涉华段落/句子并保留原文位置。
- 能区分核心、重要、次要、顺带和无关内容。
- 相关度权重有理由、置信度和版本。
- 相关度权重与原始 Article Count 分开保存和展示。
- 对短文、长文、标题导向文章、多语言文章进行专项测试。

## 33.3 文章分析
- Topic、Target、Sentiment、Stance、Frame、Claims/Evidence 字段可用。
- 情感和立场分离。
- Stance 必须绑定 Target。
- 引述观点与媒体自身表达区分。
- Unknown、Mixed、Ambiguous、Insufficient Evidence 状态可用。
- 重要判断有原文证据片段和位置。
- 每个分析结果绑定模型、Prompt、Schema、Taxonomy 和权重规则版本。

## 33.4 指标与舆情得分
- 原始数量与加权数量同时提供。
- 原始情感分布与加权情感分布同时提供。
- 加权情感分数公式、有效分母、未知值处理透明。
- 任何得分可下钻到文章及证据。
- 样本不足时不进行误导性排名。
- 国家比较显示来源覆盖和样本构成。

## 33.5 Agent、新闻和报告
- 定时监测任务可执行、可重试、可观察。
- 新文章能够进入分析和指标流程。
- 能生成基础热点/重大新闻候选并列出关联文章。
- 日报、周报能从结构化数据生成。
- 报告中的数字与指标结果一致。
- 报告中的事实性结论至少有可追溯文章或指标证据。
- 无证据的结论会被校验器标记或阻止发布。

## 33.6 预警与运营质量
- 至少实现报道量激增、负面比例上升、多国覆盖和来源故障等基础规则。
- 预警显示触发条件、基线、样本量和证据。
- 相同提醒可以去重，支持确认、忽略和误报反馈。
- 数据质量问题与舆情预警分开。

---

# 35. 风险、误差与治理补充

## 34.1 相关度权重误差
权重误判会直接影响加权情感结果。必须建立人工标注集，定期抽样复核；提供 raw/weighted 双视图；权重规则变化必须版本化并支持重算。

## 34.2 情感偏差
不同语言、文化表达和新闻体裁可能影响模型判断。必须分语言评估；保留证据；允许未知；定期抽查正负面高影响文章。

## 34.3 引用和归因错误
媒体引用第三方观点不代表媒体赞同。必须识别引述主体、叙述主体和反驳/支持关系；在不确定时不对媒体自身立场作强判断。

## 34.4 样本结构变化
新增来源、停用来源、来源采集故障、文章产量变化都会改变聚合分布。报告必须记录来源集合版本，并尽可能提供固定来源面板（same-source panel）对比，避免把样本变化误判为舆情变化。

## 34.5 事件误合并
相似主题不等于同一事件。Phase 1 的热点候选必须允许拆分/合并纠正；Phase 2 聚类优先控制 False Merge，并保留修订历史。

## 34.6 预警疲劳
预警过多会降低用户信任。应评估 Precision、重复率、用户确认率、误报率和处理时效；支持抑制、去重、升级和用户订阅。

## 34.7 Agent 幻觉与报告错误
报告生成后必须执行数字核对、链接核对、引用核对和结论-证据映射检查。关键结论缺证据时不发布为事实。

---

# 36. 开发交接给 Cursor / Codex / 其他 AI 的执行约束

本文件用于后续 AI 编程代理执行。代理必须遵守以下边界：

1. **先只读审计，后实施。** 第一轮不得直接改代码、安装依赖、迁移数据库或重构项目。
2. 输出仓库结构、技术栈、现有功能、Git 状态、依赖/运行状态、可复用模块、缺口和风险。
3. 对照本蓝图列出“已有/部分已有/缺失/冲突/需确认”的能力矩阵。
4. 发现文档内存在未冻结的候选规则（例如涉华权重区间、情感映射阈值、预警阈值）时，必须标记为待验证，不得擅自当成最终事实。
5. 不得擅自改变 GNI 固定研究对象：中国；观察样本为经审核的其他国家官方媒体及相关官方传播来源。
6. 不得把官方媒体、政府公告和独立媒体混为同一统计样本。
7. 不得把情感、立场、新闻重要性、突发程度合并为同一分数。
8. 不得让 LLM 直接生成统计数字；指标由可测试计算逻辑生成。
9. 不得丢弃原文、来源、证据位置、模型版本和计算口径。
10. 不得为了“Agent 自主性”提前引入微服务、复杂消息队列或多 Agent 网络；优先采用模块化单体和可审计工作流。
11. 每个阶段先提交实施计划和影响分析，等待用户确认后再修改代码。
12. 所有新增功能必须附测试、运行方式、失败处理和验收证据。

## 35.1 第一条只读审计指令模板

```text
你正在接手 GNI 项目。请先完整阅读 GNI Product & Technical Implementation Blueprint V4.0。

本轮只允许只读审计，不允许修改任何代码、配置、依赖、数据库或 Git 状态，不允许执行可能改变项目状态的命令。

请检查并输出：
1. 仓库目录结构与主要模块职责；
2. 当前技术栈、运行入口、依赖与环境要求；
3. 已实现功能及其代码位置；
4. 与 V4.0 蓝图逐项对照的能力矩阵（已实现/部分实现/未实现/冲突/待确认）；
5. 数据模型、API、前端页面、后台任务和测试现状；
6. 现有代码中可复用的模块；
7. 可能影响后续实施的技术债、缺陷、安全与合规风险；
8. 当前 Git 分支、工作区状态和未提交变更（只读查看）；
9. 建议实施顺序、依赖关系、风险和预计拆分的阶段；
10. 需要产品负责人确认的问题。

请特别检查：涉华片段定位、China Relevance Weight、情感/立场分离、Target 绑定、重大新闻候选、日报/周报/月报、预警规则、证据追溯和 Agent 报告校验。

本轮只输出审计报告和实施计划，等待确认后再开始修改。
```

---

# 37. 最终产品原则（V4.0）

GNI 的核心始终是：中国是固定研究对象，其他国家官方媒体是主要观察样本。系统通过可靠来源持续收集涉华报道，理解文章中真正与中国相关的内容，以透明的相关度权重和可追溯的文章分析结果计算舆情指标，并由 Agent 主动发现重大新闻、突发事件和异常变化，自动生成日报、周报、月报及预警。

**产品主线：**

`持续监测 → 涉华识别 → 内容理解 → 相关度加权 → 情感/立场判断 → 指标统计 → 新闻与异常发现 → 证据验证 → 自动报告/主动预警`

**底层原则：**
- 统计媒体报道，不冒充国家政策或公众态度。
- 先理解涉华内容，再量化，不对整篇文章粗暴贴标签。
- 原始数量与加权贡献并列，不让权重掩盖真实报道数量。
- 情感、立场、叙事框架、新闻重要性和突发性分开。
- LLM 负责理解和表达，确定性程序负责计数、计算和阈值判断。
- 每个结论都能追溯到文章、原文证据、指标定义和版本。
- 样本不足、证据不足或模型无法判断时，明确说明不确定性。
- Agent 的价值是减少用户持续监测和整理信息的成本，而不是制造一个无法审计的黑盒。

**V4.0 的 MVP 成功标准：** 用户不需要每天手动阅读大量官媒文章，也能通过总览、日报、重大新闻简报和主动提醒，可靠了解被监测官方媒体对中国的报道情况、正负面倾向和重要变化，并能在需要时一键追溯原始文章和判断依据。
