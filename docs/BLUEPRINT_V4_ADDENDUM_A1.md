# Global Narrative Intelligence（GNI）
## V4.0 技术实施文档补充：三级涉华文章筛选与内容提取流程

**文档类型：** V4.0 补充规范（Addendum）  
**建议版本号：** V4.0-A1  
**适用范围：** Phase 0 / Phase 1（MVP）  
**适用模块：** Ingestion、Processing、China Relevance Screening、Article Analysis、Data Quality  
**与主文档关系：** 本文件补充并细化 V4.0 中第 8 章数据处理、第 10 章 AI 分析与质量、第 14 章技术架构、第 15 章数据模型。若与主文档存在不一致，以主文档的产品边界为准；本补充文件仅对“如何筛选涉华文章”作进一步具体化。  
**术语：** 本文「筛选 L1/L2/L3」= 标题 / 正文 / 片段，落在 [DATA_LAYERS.md](DATA_LAYERS.md) **数据层 Layer 3**；勿与 Blueprint §14.3 系统分层编号或分析单位 L1 Article/L2 Event 混淆。

---

# 1. 设计目标与核心决策

## 1.1 目标

GNI 需要从各国官方媒体持续采集文章，但采集到的文章并非全部与中国有关。系统必须以可控成本识别真正涉及中国的文章，并提取文章中与中国有关的内容，为后续情感、立场、主题、叙事框架、事件和指标计算提供可靠输入。

本补充文件定义以下能力：

1. 标题级初筛（Title Screening）。
2. 正文级涉华判断（Full-text China Relevance Screening）。
3. 涉华内容片段提取（China-related Span Extraction）。
4. 相关度分级与权重（China Relevance Level / Weight）。
5. 不确定样本处理、漏检评估和重新筛选机制。
6. 与后续 Sentiment、Stance、Topic、Frame 分析的边界。

## 1.2 核心决策

**采用三级筛选，但标题初筛不承担最终淘汰职责。**

| 层级 | 名称 | 核心问题 | 主要输入 | 主要输出 | 是否可直接判定最终涉华 |
|---|---|---|---|---|---|
| L1 | 标题初筛 | 标题是否显式或可能涉及中国？ | 标题、摘要（若有）、来源元数据 | 相关 / 可能相关 / 未命中 / 不确定 | 否 |
| L2 | 正文筛选 | 正文是否实质涉及中国？ | 完整正文及必要上下文 | 涉华 / 非涉华 / 不确定 / 正文不可用 | 是，核心判断层 |
| L3 | 涉华片段提取 | 文章中哪些内容与中国有关，相关程度如何？ | 正文、L2 结果 | 片段、实体、Target 候选、相关度级别与权重 | 形成后续分析输入 |

标题初筛的主要作用是**优先级排序、降低明显无关内容的处理成本、帮助调度**，不是为了在正文分析前大量删除文章。

## 1.3 不采用“标题命中即涉华”的原因

标题可能出现以下情况：

- 标题明确提到 China，但正文只是无关背景或偶然提及。
- 标题没有提到 China，但正文核心讨论中国。
- 标题使用 Beijing、Chinese firms、Asian giant、the world's second-largest economy 等间接指代。
- 标题使用企业、人物、政策或地理实体，必须结合上下文才能判断是否属于中国相关对象。
- 标题是概括性或修辞性表达，单靠关键词无法准确判断。

因此，关键词命中只构成候选信号，不等于最终分类。

## 1.4 MVP 的推荐策略

1. 对采集到的每篇文章先保存原始元数据和原始抓取记录。
2. 对标题执行低成本规则匹配和实体别名匹配。
3. 标题明显相关或可能相关的文章优先进入正文处理队列。
4. 只要正文提取可行，正文筛选应尽可能覆盖所有文章；不要因标题未命中就永久丢弃。
5. 如果处理预算不足，标题未命中文章可以延迟处理，但必须保留待处理状态，并通过抽样评估估计漏检率。
6. 正文筛选确认涉华后，提取涉华片段，再开展后续分析。

---

# 2. 端到端流程与状态机

## 2.1 处理流程

```text
Source Fetch
   ↓
Raw Article Persistence
   ↓
Metadata Normalization
   ↓
Title Screening (L1)
   ├── Explicit / Likely Relevant ──────┐
   ├── Uncertain ───────────────────────┤
   └── No Match ──> Deferred Queue ─────┤
                                         ↓
                              Full-text Extraction
                                         ↓
                              Full-text Screening (L2)
                               ├── China-related
                               ├── Not China-related
                               ├── Uncertain
                               └── Text Unavailable
                                         ↓
                          China-related Span Extraction (L3)
                                         ↓
                           Span / Entity / Target Validation
                                         ↓
                        Relevance Level + Weight Assignment
                                         ↓
                    Sentiment / Stance / Topic / Frame Analysis
                                         ↓
                          Metrics / Dashboard / Reports
```

## 2.2 文章处理状态

建议将筛选状态和文章生命周期状态分开存储，避免一个 status 字段承担过多含义。

**Screening 状态：**

- `pending`：尚未筛选。
- `title_screened`：已完成标题初筛。
- `fulltext_pending`：等待正文筛选。
- `fulltext_screened`：已完成正文筛选。
- `span_extracted`：已完成涉华片段提取。
- `review_required`：需要人工复核。
- `not_china_related`：正文判断为非涉华。
- `insufficient_text`：正文缺失或质量不足，无法判断。
- `failed`：筛选任务执行失败，可重试。

**后续分析状态：**

- `analysis_pending`
- `analysis_completed`
- `analysis_partial`
- `analysis_failed`

`not_china_related` 不应等同于文章被删除。文章及其采集元数据仍需保留，以支持审计、抽样和未来重新筛选。

## 2.3 幂等性和重跑

筛选任务应使用以下信息组成版本化缓存键：

`article_id + article_content_version + screening_stage + screening_prompt_version + taxonomy_version + model_version`

相同输入和相同版本的任务重复执行时，应优先读取已有结果，避免重复调用模型。

当正文内容变化、筛选规则变化、Prompt 变化、实体词典变化或模型版本变化时，创建新的筛选运行记录，不覆盖旧结果。

---

# 3. L1：标题初筛（Title Screening）

## 3.1 目标

用低成本方法判断文章标题是否明确或可能涉及中国，并为正文提取和分析任务分配优先级。

标题初筛不是完整语义分析，不需要给出情感、立场或叙事框架。

## 3.2 输入字段

至少包括：

- `article_id`
- `title_original`
- `title_normalized`
- `source_id`
- `source_country_id`
- `language`
- `summary_or_deck`（可选）
- `published_at`（可选）
- `matched_entities`（规则匹配结果）

如有摘要或副标题，可作为辅助输入，但必须记录其来源字段，不能把摘要误当成正文。

## 3.3 两段式实现

### A. 规则和实体词典匹配

建立可版本化的 China-related Entity Dictionary，至少覆盖：

1. 国家名称与别名：China、People's Republic of China、PRC、中国及各语言变体。
2. 政府和政治机构：Chinese Government、State Council、Ministry of Foreign Affairs 等。
3. 政党与公共机构：按研究范围纳入并维护别名。
4. 地理实体：Beijing、Shanghai、Shenzhen、Hong Kong、Taiwan、Xinjiang、Tibet 等；其是否纳入涉华范围须依据明确的研究范围规则，而非仅凭地名出现就判定。
5. 企业与组织：Huawei、BYD、Tencent、Alibaba 等中国企业及其多语言别名。
6. 人物：纳入研究范围的中国政治人物、企业负责人及其他人物。
7. 政策、倡议和项目：Belt and Road Initiative、Made in China 2025 等。
8. 产业和群体表达：Chinese EV makers、Chinese semiconductor industry 等。
9. 间接指代表达：Beijing、Chinese authorities、the mainland 等，需结合语境消歧。

词典条目建议字段：

`entity_id, canonical_name, entity_type, aliases, supported_languages, target_mapping, valid_from, valid_to, ambiguity_notes, inclusion_scope, dictionary_version`

规则匹配应支持大小写、标点、Unicode 规范化、词形变化和多语言别名。不能简单使用不带边界控制的子串匹配。

### B. 模糊标题语义判断

对于规则未命中但可能涉及中国的标题，或命中歧义实体的标题，可调用轻量 LLM 判断是否值得进入正文筛选。

建议输出：

- `title_screening_label`: `explicit_relevant | likely_relevant | no_match | uncertain`
- `matched_entity_mentions`
- `reason_short`
- `confidence`
- `needs_fulltext_priority`

模型必须遵循：

- 只判断“标题是否显示或暗示中国相关性”。
- 不得因出现 Asia、trade、technology、security 等宽泛词语就自动判定涉华。
- 不得将香港、台湾、新疆、西藏等实体的提及自动解释为对中国整体的评价；需按研究范围与具体语境识别相关性。
- 对 Beijing 等歧义表达保留 `uncertain`，不要强制二分类。
- 不推断文章情感或立场。

## 3.4 标题筛选标签

| 标签 | 含义 | 建议调度 |
|---|---|---|
| `explicit_relevant` | 标题明确提及中国或明确中国实体 | 高优先级正文处理 |
| `likely_relevant` | 标题通过间接表达或相关实体暗示中国 | 高/中优先级正文处理 |
| `no_match` | 标题未发现涉华信号 | 常规队列或延迟队列，不永久删除 |
| `uncertain` | 实体歧义或标题信息不足 | 中高优先级正文处理 |

`no_match` 的含义是“标题未发现信号”，不是“文章确定不涉华”。

## 3.5 标题筛选的优先级分数

MVP 可以先使用离散优先级，不必建立复杂评分模型：

- `P1`：明确命中中国国家/政府/重要人物/核心政策。
- `P2`：命中中国企业、产业、间接指代或语义疑似相关。
- `P3`：标题未命中，但来源属于重点来源或文章属于高优先级专题，等待正文筛选。

如果后续确需数值优先级，可将实体类型、标题位置、摘要命中、来源重要性作为排序特征；该分数仅用于任务调度，不能用作 China Relevance Weight。

---

# 4. L2：正文级涉华判断（Full-text Screening）

## 4.1 目标

根据文章正文判断其是否实质涉及中国，区分真正涉华内容与偶然提及，并识别正文提取质量是否足以支持判断。

L2 是最终的涉华纳入判断层。标题结果只能作为辅助上下文，不得覆盖正文证据。

## 4.2 输入

- 标准化正文（保留段落边界）。
- 标题、摘要和副标题（辅助上下文）。
- 来源、语言和时间元数据。
- L1 标题筛选结果及命中实体。
- 研究范围与实体词典版本。

## 4.3 正文筛选标签

- `china_related`：正文中存在实质性中国相关内容。
- `not_china_related`：正文没有实质性中国相关内容，或仅有不构成研究对象的偶然提及。
- `uncertain`：正文存在潜在相关表达，但目标、指代或上下文不足以判断。
- `insufficient_text`：正文提取失败、正文过短、仅有导航/广告/版权信息，或文本质量不足。

不要把 `uncertain` 或 `insufficient_text` 强行归入 `not_china_related`。

## 4.4 “实质涉及中国”的判断标准

满足下列任一情形，通常可以判为 `china_related`：

1. 中国或中国相关 Target 是文章主要讨论对象。
2. 中国是文章重要论点、解释链条或事件背景的一部分。
3. 文章对中国相关政策、机构、企业、人物、产业或社会现象作出实质描述、评价或分析。
4. 中国虽不是标题主体，但在正文中占据具有研究意义的内容。
5. 报道讨论国际事件，而中国是其中不可忽略的参与方、影响方或被评价对象。

通常不应仅因以下情况判为 `china_related`：

1. 仅在历史背景、名单、地址、版权或无关比较中出现一次中国名称。
2. 仅出现一个中国地名，但该地名与中国议题无关或存在同名歧义。
3. 自动抓取正文混入导航、推荐文章、广告或页脚，导致词典误命中。
4. 文章只讨论亚洲或全球市场，没有实际涉及中国。

边界案例应输出 `uncertain`，并给出具体原因。

## 4.5 正文分析的范围控制

正文筛选可以先对全文进行理解，但最终涉华结论必须能定位到原文段落或句子。

对超长文章：

1. 先进行结构化分段，保留段落 ID 和原文偏移量。
2. 可先用实体词典/NER 找候选段落。
3. 对候选段落及其前后上下文进行模型判断。
4. 对全文做一次遗漏检查，避免只看命中段落而漏掉代词、同义表达和后文回指。
5. 若使用分块分析，最后必须执行跨块合并与全篇一致性检查。

不允许仅凭单个关键词段落直接决定全文是否涉华。

## 4.6 L2 输出 Schema

```json
{
  "article_id": "...",
  "screening_label": "china_related",
  "reason_codes": ["substantive_china_discussion", "china_is_major_actor"],
  "summary_of_relevance": "文章实质讨论中国相关议题的简短说明",
  "candidate_targets": ["China", "Chinese Government"],
  "supporting_paragraph_ids": [3, 4, 7],
  "contradictory_or_ambiguous_context": [],
  "confidence": 0.91,
  "requires_human_review": false
}
```

以上为结构示例，实际 schema 应使用项目统一 Pydantic/JSON Schema 定义。`confidence` 是模型自报的辅助信号，不得直接解释为准确率或统计置信区间。

## 4.7 低置信度和冲突处理

触发人工复核或二次模型判断的情况：

- `uncertain`。
- 关键实体存在多义性。
- 标题判断为明确涉华，但正文判断非涉华。
- 标题未命中，但正文模型判断高度涉华且实体词典未命中。
- 文章正文缺失或正文抽取质量异常。
- 多模型结果冲突（如系统启用交叉检查）。
- 文章涉及重要事件或高优先级来源，且筛选结果将影响重大报告。

模型自报置信度只能作为复核队列排序特征之一，不能作为唯一分流依据。还应结合实体冲突、文本质量、规则命中和任务重要性。

---

# 5. L3：涉华片段提取（China-related Span Extraction）

## 5.1 目标

在 L2 确认涉华后，提取文章中真正与中国有关的句子、段落或连续文本片段。后续情感、立场和框架分析优先使用这些片段及必要上下文，而不是把整篇文章不加区分地当成对华表达。

## 5.2 提取粒度

推荐采用两级粒度：

- **Paragraph Span：** 以段落为主，适合保留完整论述上下文。
- **Sentence Span：** 对长段落或多目标段落进一步定位句子。

不要在 MVP 阶段过度追求 token 级最小片段。片段必须保留足够上下文，避免把转折、否定、条件、引述归属和代词指代切断。

## 5.3 每个片段需要记录

- `span_id`
- `article_id`
- `article_version_id`
- `paragraph_index`
- `sentence_start_index` / `sentence_end_index`（可选）
- `char_start` / `char_end`（相对于明确版本的规范化正文）
- `text_original`
- `language`
- `span_type`：`direct_mention | coreference | contextual_reference | quoted_reference | background_reference`
- `related_entities`
- `candidate_targets`
- `relevance_reason`
- `extraction_confidence`

偏移量必须绑定 `article_version_id` 和正文规范化版本。若正文被重新提取或清洗，旧偏移量不可直接复用。

## 5.4 涉华片段类型

- `direct_mention`：直接出现 China、中国或明确中国实体。
- `coreference`：通过代词、简称或上下文回指中国相关对象。
- `contextual_reference`：没有直接提及中国名称，但结合上下文明确指向中国。
- `quoted_reference`：引述内容中涉及中国。
- `background_reference`：作为背景信息提及中国，通常权重较低，但不能自动排除。

引述内容需要额外记录表达主体。引述了某人的反华观点，不代表媒体自身持相同立场。

## 5.5 片段完整性与校验

模型返回的片段不能只保存模型重述文本。必须通过原文校验：

1. 片段文本必须能在指定文章版本的正文中定位。
2. 保存原文起止位置或段落 ID。
3. 若模型输出经过改写，不能作为原文 Evidence Span；应重新定位原句。
4. 找不到精确原文时标记 `span_validation_failed`，不得静默保存为证据。
5. 片段重叠时按原文位置合并或保留关系，不得重复计数。
6. 对否定、转折、比较、条件句和引述归属，保留足够上下文。

## 5.6 后续分析输入策略

推荐输入结构：

`China-related spans + adjacent context + article title + source metadata`

而不是只输入孤立句子。

- Sentiment：判断媒体报道对涉华内容的整体语气，同时区分作者叙述与引用观点。
- Stance：对具体 Target 逐项判断，必须绑定表达主体和证据。
- Topic：判断涉华内容所讨论的议题。
- Frame：判断文章如何组织和解释涉华议题。
- Claims/Evidence：提取重要主张、事实依据和来源归属。

如果文章存在多个互不相同的涉华片段，允许不同片段对应不同 Target、Topic、Sentiment 或 Stance，不要强行压成一个全篇标签。

---

# 6. China Relevance Level 与 Weight

## 6.1 分级与数值权重分开

必须区分：

- `china_relevance_level`：可解释的类别。
- `china_relevance_weight`：用于聚合统计的连续权重。

类别是研究者能理解的语义分级；数值权重是经评估和校准后用于统计的参数。不能把模型随口给出的 0.83 当作已经验证的客观比例。

## 6.2 初始分级建议

| Level | 定义 | 初始权重区间（仅用于试验） |
|---|---|---:|
| `core` | 中国或明确中国 Target 是文章主要讨论对象、核心事件主体或主要论点 | 0.80–1.00 |
| `substantial` | 中国是重要参与方或重要分析对象，但并非全文唯一核心 | 0.50–0.79 |
| `secondary` | 中国是有实质意义的次要对象或重要背景之一 | 0.20–0.49 |
| `incidental` | 仅简短提及，研究意义有限 | 0.01–0.19 |
| `none` | 无实质涉华内容 | 0 |
| `uncertain` | 证据不足，无法稳定判断 | 不分配正式权重，保留空值 |

区间仅是 Phase 0 的候选设计，不是最终冻结标准。应通过人工样本和实际分布校准。`incidental` 是否纳入某些统计，应由指标定义决定，不得默认所有涉华文章都纳入。

## 6.3 权重判断因素

不能只按涉华字数占全文字数的比例计算。建议综合：

1. **内容占比：** 涉华段落/句子在全文中的比例。
2. **标题与导语显著性：** 中国是否出现在标题、摘要、导语。
3. **核心论点贡献：** 去掉涉华内容后，文章主旨是否发生实质变化。
4. **事件主体性：** 中国是否是主要行动方、参与方或被评价对象。
5. **分析深度：** 是否有连续论述、数据、专家观点或政策分析。
6. **Target 重要性：** 是否针对中国或重要中国相关对象作出实质判断。

建议先由模型输出上述因素的结构化解释，再根据经过验证的规则或校准模型映射到权重。MVP 可以先使用分级区间或规则映射，避免过早设计复杂公式。

## 6.4 统计口径约束

- 原始 `Article Count` 不应乘以相关度权重后改名为文章数量。
- 可另行计算 `Weighted Article Volume = Σ relevance_weight`，并明确称为加权文章量。
- 情感加权均值等指标必须披露分母、Unknown 处理、权重版本和分析范围。
- `uncertain` 不应自动当作 0，也不应自动按平均值填补。
- 文章包含多个 Target 时，若按 Target 统计，需定义 Target-specific relevance，不应把全篇权重不加区分地复制给每个 Target。
- 同时保留未加权统计和加权统计，便于用户检查权重对结果的影响。

---

# 7. L1/L2/L3 的模型调用策略与成本控制

## 7.1 不需要训练专属模型

本流程不要求预训练或微调 GNI 专属模型。MVP 优先使用现有通用大模型和规则组件：

- 规则/词典：高精度实体命中、规范化和候选生成。
- NER/轻量模型：可选，用于实体候选识别。
- 现有 LLM：处理语义歧义、全文判断、片段提取和相关度解释。
- 程序代码：负责正文分段、偏移量校验、权重映射、任务调度和统计计算。

模型应通过统一 Provider Adapter 调用，避免业务逻辑绑定某一家模型服务。

## 7.2 推荐调用策略

| 场景 | 处理方式 | 是否必须调用 LLM |
|---|---|---|
| 标题精确命中高置信度实体 | 规则命中，安排正文处理 | 否 |
| 标题完全未命中 | 先标记 no_match；正文仍按队列策略处理 | 否 |
| 标题实体存在歧义 | 语义判断或直接进入正文 | 可选 |
| 正文明确包含中国相关讨论 | 正文 LLM/规则联合判断 | 通常是，或经验证的轻量分类器 |
| 正文明确无关且规则证据充分 | 规则判定或轻量分类器 | 不一定 |
| 正文多目标、隐含指代、复杂引述 | LLM 深度判断 | 是 |
| 涉华片段提取 | LLM 识别候选，程序校验原文 | 是（候选提取阶段） |
| 相关度权重 | 结构化因素判断 + 程序映射 | LLM 可提供因素判断 |

不要为所有文章执行昂贵的多轮 LLM 调用。也不要为了省成本，把标题未命中文章永久排除。

## 7.3 模型路由与版本记录

每次筛选必须记录：

- `provider`
- `model_name`
- `model_version`（若供应商提供）
- `prompt_version`
- `schema_version`
- `dictionary_version`
- `taxonomy_version`
- `temperature` / 关键推理参数（如适用）
- `input_hash`
- `output_hash`
- `tokens_in` / `tokens_out`
- `latency_ms`
- `cost_estimate`
- `created_at`

模型更换不应改变文章事实数据和原始证据。新模型结果应以新 `analysis_run` 保存，支持 A/B 比较和回滚。

---

# 8. 漏检控制与质量评估

## 8.1 为什么必须评估标题漏检

如果标题初筛把某篇文章标记为 `no_match`，而系统又不再处理其正文，那么标题筛选的 False Negative 会直接变成系统永久漏报。因此，必须通过正文覆盖或抽样复核来估计漏检风险。

## 8.2 必须监控的指标

**L1 标题筛选：**

- Recall：标题筛选命中的涉华文章占所有真实涉华文章的比例。
- Precision：标题筛选命中的文章中，实际涉华文章的比例。
- False Negative Rate：标题初筛漏掉的涉华文章比例。
- `no_match` 队列抽样后发现的真实涉华比例。

**L2 正文筛选：**

- Precision / Recall / F1。
- `uncertain` 比例。
- `insufficient_text` 比例。
- 各语言、国家、来源和主题的分层表现。

**L3 片段提取：**

- Span Precision：提取片段中确实与中国相关的比例。
- Span Recall：人工确认的涉华内容中被成功提取的比例。
- Exact/Approximate Span Match：原文定位准确度。
- Span Validation Failure Rate：原文无法定位的比例。
- Target Link Accuracy：片段与 Target 对应准确率。

不要只看总体准确率。类别不平衡时，Accuracy 可能掩盖漏检；涉华筛选尤其应关注 Recall 和 False Negative。

## 8.3 抽样策略

Phase 0 / MVP 建议：

1. 对 `no_match` 文章进行随机抽样，估计标题初筛漏检率。
2. 对 `china_related` 结果抽样，检查误报和相关度分级。
3. 对 `uncertain`、`insufficient_text` 和模型冲突样本进行高比例复核。
4. 按国家、语言、来源类型、文章长度、Topic 候选分层抽样。
5. 保留代表性随机评估集；另建困难案例集，不能只用困难案例估计总体准确率。

起步阶段可以从 100–200 篇人工评估样本开始，覆盖涉华/非涉华、显式/隐式提及、多语言和边界案例。样本规模应随着来源数量、语言数量和错误率调整，不应把某个固定数量视为充分证明。

## 8.4 人工复核队列

人工复核优先级建议：

- P0：重要新闻、关键来源、重大预警关联文章。
- P1：正文与标题判断冲突、模型冲突、关键实体歧义。
- P2：低置信度、片段定位失败、相关度边界案例。
- P3：普通随机质量抽样。

人工修改必须保留原始模型输出、修订值、修改人、时间、理由和规则版本。人工复核结果不能直接覆盖原始模型记录。

---

# 9. 数据库与数据结构补充

V4.0 已有 `articles`、`article_analyses`、`article_evidence`、`analysis_runs`、`model_versions`、`prompt_versions` 等表。本补充建议在现有模型上扩展，不要重复创建同义实体表。

## 9.1 建议新增或扩展的表

### `article_screenings`

保存每次 L1/L2 筛选运行结果。

建议字段：

```text
screening_id
article_id
article_version_id
stage                    -- title / fulltext
screening_label
reason_codes             -- JSONB
matched_entities         -- JSONB
supporting_paragraph_ids -- JSONB
confidence               -- nullable numeric
requires_human_review
model_version_id         -- nullable
prompt_version_id        -- nullable
rule_version
entity_dictionary_version
schema_version
input_hash
run_id
created_at
supersedes_screening_id  -- nullable
```

### `article_relevance_assessments`

保存文章级相关度判断，避免把它与情感、立场混在一个字段中。

```text
assessment_id
article_id
article_version_id
relevance_level          -- core/substantial/secondary/incidental/none/uncertain
relevance_weight         -- nullable numeric(4,3)
content_share_estimate   -- nullable numeric(4,3), optional diagnostic only
headline_prominence      -- nullable categorical/numeric
thesis_contribution      -- nullable categorical
china_actor_role         -- nullable categorical
analysis_depth            -- nullable categorical
reasoning_summary
assessment_version
model_version_id
prompt_version_id
review_status
created_at
```

### `article_china_spans`

保存 L3 提取的涉华原文片段。

```text
span_id
article_id
article_version_id
paragraph_index
sentence_start_index     -- nullable
sentence_end_index       -- nullable
char_start
char_end
text_original
language
span_type
related_entities         -- JSONB
candidate_targets        -- JSONB
relevance_reason
extraction_confidence
validation_status        -- valid / failed / needs_review
created_at
```

### `china_entity_dictionary`

保存实体规范名和多语言别名，或映射到现有实体主数据表。

```text
entity_id
canonical_name
entity_type
aliases                 -- JSONB or normalized alias table
supported_languages
inclusion_scope
ambiguity_notes
valid_from
valid_to
version
active
```

### `screening_reviews`

保存人工复核记录。

```text
review_id
article_id
screening_id
span_id                 -- nullable
review_type
original_label
corrected_label
review_reason
reviewer_id
reviewed_at
guideline_version
```

以上是逻辑字段建议，最终应按现有 V4.0 schema、ORM 和 migration 风格调整。若已有表可承载相同职责，应扩展已有表而不是机械新增。

## 9.2 索引建议

- `article_screenings(article_id, stage, created_at DESC)`
- `article_screenings(screening_label, created_at)`
- `article_china_spans(article_id, article_version_id)`
- `article_relevance_assessments(relevance_level, created_at)`
- `screening_reviews(review_status, reviewed_at)`（如有 review_status）

JSONB 字段仅在确有查询需求时增加 GIN 索引。不要为了“可能有用”而过度索引。

---

# 10. API / Service 边界建议

服务层可以采用以下接口名称，具体路径由项目 API 风格统一决定：

- `screen_title(article_id, article_version_id)`
- `extract_fulltext(article_id, article_version_id)`
- `screen_fulltext(article_id, article_version_id)`
- `extract_china_spans(article_id, article_version_id)`
- `assess_china_relevance(article_id, article_version_id)`
- `validate_spans(article_id, article_version_id)`
- `enqueue_screening_review(article_id, reason_codes)`
- `rescreen_articles(filters, screening_version)`

服务职责：

- `TitleScreeningService`：规则/词典匹配与模糊标题判断。
- `FullTextScreeningService`：正文涉华判断。
- `ChinaSpanExtractionService`：涉华片段提取及原文定位。
- `RelevanceAssessmentService`：相关度分级与权重映射。
- `ScreeningQualityService`：抽样、评估指标和漏检率统计。

这些是模块边界，不意味着要拆成微服务。MVP 应保持 Modular Monolith。

---

# 11. 错误处理与异常场景

| 场景 | 处理方式 | 是否判定非涉华 |
|---|---|---|
| 标题未命中、正文尚未提取 | 进入正文待处理/延迟队列 | 否 |
| 正文提取失败 | 标记 `insufficient_text`，重试或人工查看 | 否 |
| 正文只有摘要 | 标记文本类型和完整性，降低判断等级 | 不得直接判非涉华 |
| 页面混入导航、推荐和广告 | 正文清洗，保留原始抓取快照 | 否 |
| 文章为多语言混排 | 分段语言识别，保留原文 | 否 |
| 同一文章更新 | 新建 article_version，重新评估 | 否 |
| 模型输出 JSON 不合法 | Schema 校验失败，有限重试，失败入队 | 否 |
| 模型无法定位原文片段 | 标记 span validation failure | 否 |
| 关键词命中歧义地名 | 结合上下文消歧，必要时人工复核 | 否 |
| 文章仅偶然提及中国 | L2 判 `not_china_related` 或低级别 incidental，按规范处理 | 可判非实质涉华 |

系统不得把“没能分析”记录成“分析为不相关”。

---

# 12. Phase 0 / Phase 1 实施任务

## 12.1 Phase 0：设计与验证

1. 定义研究范围：哪些实体、地区、组织、企业、人物和政策纳入 China-related。
2. 建立首版多语言实体词典，明确歧义实体和排除规则。
3. 定义 L1/L2/L3 输出 Schema 和 Pydantic 校验模型。
4. 选择少量不同语言来源，收集显式、隐式、非涉华和边界文章。
5. 用现有大模型测试标题初筛、正文筛选和片段提取，不训练专属模型。
6. 人工检查输出，重点检查漏检、误报、片段定位和 Target 指代。
7. 冻结第一版 Prompt、规则和词典版本，建立可复现实验记录。
8. 根据真实成本决定哪些步骤用规则、轻量模型或 LLM。

## 12.2 Phase 1：MVP 开发

1. 在采集流程中保存原始文章与正文版本。
2. 实现 L1 标题初筛和实体匹配。
3. 实现正文提取与正文质量检查。
4. 实现 L2 正文涉华判断。
5. 实现 L3 涉华片段提取和原文位置校验。
6. 实现相关度等级与权重记录。
7. 将后续 Sentiment、Stance、Topic、Frame 分析输入改为涉华片段 + 必要上下文。
8. 实现 `uncertain`、`insufficient_text` 和人工复核队列。
9. 实现标题 `no_match` 文章的延迟处理或随机抽样机制。
10. 增加筛选覆盖率、漏检率、片段校验失败率和成本监控。

---

# 13. 验收标准（Acceptance Criteria）

## 13.1 功能验收

- [ ] 每篇采集文章均保存原始元数据和正文版本（正文可用时）。
- [ ] 每篇文章均能记录标题初筛结果及其规则/模型版本。
- [ ] 标题 `no_match` 不会自动导致文章永久删除或不可恢复。
- [ ] 正文筛选能输出 `china_related / not_china_related / uncertain / insufficient_text`。
- [ ] L2 的涉华判断可以追溯到正文段落证据。
- [ ] L3 能提取涉华段落/句子，并保存原文定位信息。
- [ ] 片段必须通过原文位置校验；失败时有明确状态。
- [ ] 能区分文章级相关度等级与相关度权重。
- [ ] 能区分涉华内容、引用对象观点与媒体自身表达。
- [ ] 后续分析可使用涉华片段及上下文，而不是无差别使用全文。
- [ ] 所有筛选结果均记录模型、Prompt、规则、词典和 Schema 版本。
- [ ] 支持对历史文章按新版本重新筛选，且不覆盖旧结果。

## 13.2 质量验收

- [ ] 有按国家/语言/来源分层的筛选评估集。
- [ ] 对标题 `no_match` 文章进行抽样，估计 L1 漏检率。
- [ ] 分别报告 L1、L2、L3 的质量指标。
- [ ] 至少报告 Precision、Recall、F1；L1/L2 特别关注 Recall。
- [ ] `uncertain` 和 `insufficient_text` 不被自动并入 `not_china_related`。
- [ ] 统计中能区分原始文章数、涉华文章数、加权文章量。
- [ ] 能按模型版本比较筛选质量与成本。

## 13.3 建议的初始质量门槛

MVP 不应在没有人工评估的情况下宣称达到某个准确率。可以在 Phase 0 试验后设定门槛。若需要初始工程目标，可优先要求：

- 对核心语言/来源的 L2 Recall 达到项目约定阈值后，才允许全自动进入正式指标。
- `uncertain` 与 `insufficient_text` 保持可见，不通过强制分类来“提高”完成率。
- L3 片段原文定位失败率低于约定阈值，否则不允许将片段作为正式证据。
- 对样本量不足或某语言表现不稳定的分组，Dashboard 显示质量警告，不进行强比较。

具体数值门槛应由 Phase 0 评估结果确定，不能在没有基准数据时虚构。

---

# 14. 对 V4.0 现有章节的具体补充关系

| V4.0 原章节 | 本补充文件对应内容 | 实施时的调整 |
|---|---|---|
| 8.1 Pipeline | 第 2 章 | 在 `Extract` 后、`Analyze` 前加入 L1/L2/L3 筛选步骤；正文提取失败单独标记 |
| 9 Taxonomy | 第 3、4、6 章 | 增加多语言 China-related Entity Dictionary；明确研究范围和歧义实体 |
| 10.1 分级处理 | 第 7 章 | 明确规则、轻量模型、LLM 的分工和模型调用条件 |
| 10.3 分析质量 | 第 8 章 | 增加筛选 Recall、False Negative、Span Precision/Recall 等指标 |
| 14.3 技术分层 | 第 10 章 | 在 Processing / Intelligence Layer 中增加独立筛选服务模块 |
| 15 数据模型 | 第 9 章 | 扩展现有表或新增筛选、相关度、片段和人工复核记录 |

建议将主流程更新为：

`Fetch → Raw Persistence → Parse/Normalize → Full-text Extraction → Language/Time → Deduplicate → Title Screening → Full-text Screening → China-related Span Extraction → Relevance Assessment → Sentiment/Stance/Topic/Frame Analysis → Aggregate`

注意：标题初筛可在正文提取前并行执行；上面的串行表示逻辑依赖，不要求工程上必须串行等待。若标题未命中，正文提取可延迟，但不可永久丢弃。

---

# 15. 给后续 AI 编码 Agent 的执行约束

1. 先检查现有仓库、数据库模型、任务队列和 Prompt 管理方式，再决定如何落地；不要凭本文件臆造已有代码结构。
2. 不要在 MVP 中训练、预训练或微调专属模型。先使用现有模型 API 和规则组件。
3. 不要让标题关键词命中直接等于涉华，也不要让标题未命中直接等于非涉华。
4. 不要把正文提取失败当作非涉华。
5. 不要只保存模型总结文本；必须保存可回溯原文的涉华片段和位置。
6. 不要把全文情感、引述对象情绪、媒体立场混成一个标签。
7. 不要将 `china_relevance_weight` 当作字数占比的简单复制。
8. 不要把加权文章量冒充原始文章数量。
9. 不要静默覆盖旧筛选结果；模型、Prompt、词典或 Schema 变化时创建新版本。
10. 不要为本功能引入微服务、Kafka 或不必要的复杂基础设施；遵循 V4.0 Modular Monolith 原则。
11. 每个阶段必须提供单元测试、边界案例测试和可观察日志。
12. 对无法可靠判断的文章保留 `uncertain`，将其送入复核或延迟队列。

---

# 16. 关键结论

GNI 的文章筛选不应是“标题命中关键词 → 直接纳入”或“标题未命中 → 直接丢弃”的二元流程。正确做法是：

**标题初筛负责排序，正文筛选负责最终纳入判断，涉华片段提取负责确定后续分析对象。**

在此基础上，系统再计算 China Relevance Level / Weight，并将涉华片段及必要上下文交给后续情感、立场、主题和叙事框架分析。

这一设计既能控制模型调用成本，又能降低标题漏检风险；同时保留原文证据、版本记录和人工复核入口，为 GNI 的跨国比较和长期趋势分析建立可靠的数据基础。
