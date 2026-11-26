# GNI 统计口径与指标计算规范 V1.0

- **文档性质：** 产品与技术实施规范
- **适用范围：** GNI 文章分析、议题分类、立场分析、数据聚合、日报、周报、月报
- **版本：** `methodology_v1.0`（分类体系：`taxonomy_v1.0`；文章分析 Schema：`article_analysis_v1.0`）
- **单一真相配置：** [configs/topics_taxonomy_v1.yaml](../configs/topics_taxonomy_v1.yaml)

---

## 1. 设计目标

建立统一、可复现、可审计的涉华舆情统计规则，使不同时间、不同国家、不同议题和不同板块的数据能够使用相同的计算口径进行比较。

本规范参考《涉华舆情月报（2026年7月）》的统计结构，采用其四大板块、15 个议题、多议题重叠和正中负三分类的基本思路，并对部分未明确披露的计算细节进行规范化补充。

### 核心原则

1. 以文章（Article）作为基础统计单位。
2. 一篇文章允许命中多个议题和多个板块。
3. 统计时在对应统计范围内进行文章去重。
4. 以文章对中国大陆的立场作为正中负分类依据。
5. 统计指标由确定性程序计算，不由 LLM 直接估算。
6. 所有统计结果必须能够追溯至原始文章和文章级分析结果。

---

## 2. 统计对象与分类体系

### 2.1 基础统计单位

第一阶段以 `Article` 为唯一基础统计单位。

- `Article Count`：**采用**，核心报道数量
- `Weighted Article Volume`：**不采用**，暂不引入人工权重
- `Unique Story Count`：**不采用**，暂不作为报告核心指标
- `Unique Event Count`：**不采用**，暂不作为报告核心指标

一篇文章必须具有唯一的 `article_id`。相同文章经过重复采集、URL 参数变化或重复入库，不应重复计数。基础去重使用 `canonical_url`、正文 `content_hash`、标题及正文相似度等机制。

### 2.2 四大板块与 15 个议题

分类体系固定为以下结构（第一阶段不新增一级板块或二级议题，详见 [configs/topics_taxonomy_v1.yaml](../configs/topics_taxonomy_v1.yaml)）：

- **安全军事 (`security_military`)**
  - 南海争端 (`south_china_sea`)
  - 印太军事博弈 (`indo_pacific_military`)
  - 台海局势 (`taiwan_strait`)
- **经贸科技 (`economy_tech`)**
  - 科技竞争 (`tech_competition`)
  - 新能源与产能过剩争议 (`new_energy_overcapacity`)
  - 关税与贸易战 (`tariffs_trade_war`)
  - 中国经济形势 (`china_economy`)
  - 半导体与出口管制 (`semiconductors_export_controls`)
- **政治外交 (`politics_diplomacy`)**
  - 中俄关系与乌克兰 (`china_russia_ukraine`)
  - 中美关系 (`us_china_relations`)
  - 一带一路 (`belt_and_road`)
  - 全球影响力与全球南方 (`global_south_influence`)
- **社会舆论 (`society_opinion`)**
  - 涉疆议题 (`xinjiang`)
  - 涉藏议题 (`tibet`)
  - 涉港议题 (`hong_kong`)

### 2.3 多标签分类规则

采用多标签分类机制。一篇文章可以：

- 命中一个或多个议题。
- 命中一个或多个一级板块。
- 同时命中不同板块下的多个议题。

分类必须基于文章实际内容（正文与涉华片段），不允许仅凭标题关键词直接认定最终议题。同一篇文章在同一个议题中只能计数一次，在同一个板块中也只能计数一次。

---

## 3. Article Count 计算规则

### 3.1 全球涉华文章总量

```text
Global Article Count = COUNT(DISTINCT article_id)
```

同一文章即使命中多个议题、多个板块，在全球总量中也只计算一次。

### 3.2 议题报道量

```text
Topic Article Count = COUNT(DISTINCT article_id)
```

同一文章可以同时计入多个议题，因此 15 个议题的报道量相加可能大于全球涉华文章总量。议题报道量排名不要求各议题占比之和等于 100%。

### 3.3 板块报道量

```text
Board Article Count = COUNT(DISTINCT article_id WHERE article matches any topic in board)
```

同一篇文章如果命中同一板块下的多个议题，在该板块中仍然只计算一次。不同板块之间允许重叠，因此四大板块的报道量不能直接相加作为全球涉华文章总量。

---

## 4. 对华立场分析规则

### 4.1 评价对象

统一采用：**对中国大陆的立场倾向（China-related Stance）**。

评价的是报道对中国大陆的表达立场，而不是：

- 文章整体的情绪语气。
- 新闻标题的正负面词汇。
- 被采访者或被引用人物的单独观点。
- 新闻事件本身的好坏。

应结合文章中的涉华内容、上下文、评价性表达及作者自身叙述进行判断。

### 4.2 三分类体系

- **正面 (`Positive`)**：对中国大陆的表达总体积极、支持或肯定
- **中性 (`Neutral`)**：客观描述，没有明显正面或负面评价
- **负面 (`Negative`)**：对中国大陆的表达总体批评、质疑或否定

数据库允许额外保留 `Unclassified`，用于证据不足、无法判断或无法确定主导立场的文章。`Unclassified` 不属于第四种立场，而是分析状态。

**严格口径**：历史旧版（非 `article_analysis_v1.0`）分析结果不强行映射到三分类，在 V1.0 统计中一律按 `Unclassified` 处理，需通过 `--reanalyze` 按 V1.0 重新分析后计入有效分类。

### 4.3 混合立场处理

如果文章同时包含正面和负面表达：

1. 综合涉华内容及上下文。
2. 判断文章整体对中国大陆的主导表达倾向。
3. 可以确定主导倾向时，归入 `Positive`、`Neutral` 或 `Negative`。
4. 无法确定主导倾向时，标记为 `Unclassified`。

不得为了保证数据完整率而强制给所有文章贴上正面、中性或负面标签。

### 4.4 逐篇判定

每篇文章先独立完成立场分析，再参与统计。分析结果至少保留：

- `article_id`
- `stance_label`
- `stance_confidence`
- `stance_evidence`（必须能够定位到文章中的实际证据）
- `analysis_status`
- `model_version`
- `prompt_version`

模型置信度不能直接视为真实准确率。

---

## 5. 立场比例计算

### 5.1 统计分母

正面、中性、负面比例只使用已经完成有效立场判定的文章：

```text
Classified Article Count = Positive Count + Neutral Count + Negative Count
Positive Rate = Positive Count / Classified Article Count
Neutral Rate  = Neutral Count  / Classified Article Count
Negative Rate = Negative Count / Classified Article Count
```

三类比例之和为 100%（允许显示时存在四舍五入误差）。

### 5.2 立场判定覆盖率

```text
Stance Coverage Rate = Classified Article Count / Total Relevant Article Count
```

`Unclassified` 必须保留在文章总量中，但不进入正中负比例的分母。

---

## 6. 四个统计层级的立场聚合

1. **全球涉华立场 (`GLOBAL`)**：对指定时间范围内的全球唯一涉华文章进行统计，每篇文章只参与一次。
2. **议题涉华立场 (`TOPIC`)**：对命中具体议题的唯一文章集合进行统计，跨议题命中可分别计入各议题。
3. **板块涉华立场 (`BOARD`)**：对命中该板块任意议题的唯一文章集合进行统计；同板块命中多个议题只参与一次；直接基于唯一文章集合计算，不按议题重复加权。
4. **国家涉华立场 (`COUNTRY`)**：对指定信源所属国家的唯一涉华文章集合进行统计，同时展示文章数量和立场判定覆盖率。

---

## 7. 国家归属规则

国家统计严格按照**信源所属国家 (`source_country`)**进行，不依据事件发生地、新闻涉及国家或提及最多国家。数据模型严格区分 `source_country`、`language`、`topic`、`event_location`、`event_time`。

---

## 8. 时间统计规则

第一阶段核心保留两个时间字段：

- `published_at`（文章发布时间）：日报、周报、月报文章统计**统一且严格**按 `published_at` 归入时间窗口。
- `event_time`（实际事件发生时间）：事件时间线与演化专用；无法确定时允许为空，**严禁**用 `published_at` 替代。
- `first_seen_at`（首次发现时间）：**不参与**第一阶段核心文章量、立场比例及议题热度计算。

---

## 9. 核心数据输出结构

每次统计生成可追溯的统计快照（数据表 `stat_snapshots`），至少包含：

- `period_start`、`period_end`
- `scope_type`（`GLOBAL` / `COUNTRY` / `BOARD` / `TOPIC`）、`scope_id`
- `article_count`、`positive_count`、`neutral_count`、`negative_count`、`unclassified_count`
- `positive_rate`、`neutral_rate`、`negative_rate`、`stance_coverage_rate`
- `methodology_version`、`taxonomy_version`、`analysis_version`
- `article_ids`（溯源文章 ID 列表）
- `generated_at`

---

## 10. 程序与 AI 的职责边界

- **AI 负责**：判断文章是否涉华、提取涉华内容、判断命中的议题、判断对中国大陆的立场、提取支持证据、对统计结果进行解释和报告撰写。
- **程序负责**：文章去重、唯一文章计数、多标签聚合、四大板块聚合、正中负数量和比例计算、立场判定覆盖率计算、国家和时间维度统计、统计快照生成、历史数据比较。
- **硬规则**：LLM 不得直接估算报道量、立场比例或覆盖率。所有数字必须由程序根据文章级结构化结果计算。

---

## 11. 第一阶段验收标准

自动化单元测试见 [tests/unit/test_metrics_v1_spec.py](../tests/unit/test_metrics_v1_spec.py)，逐条覆盖以下 10 条标准：

1. 一篇文章命中两个议题，两个议题分别计数，但全球总量只计一次。
2. 一篇文章命中同一板块下两个议题，该板块只计一次。
3. 一篇文章命中两个不同板块，两个板块分别计数，但全球总量只计一次。
4. 一篇文章为 `Unclassified`，仍计入文章总量，但不计入正中负比例分母。
5. 一篇文章的立场判定完成后，全球、国家、板块、议题统计均使用同一篇文章级分析结果。
6. 同一统计范围内正中负比例之和为 100%（排除四舍五入误差）。
7. 立场判定覆盖率能够反映未判定文章的比例。
8. 同一文章重复采集或重复入库，不得造成报道量增加。
9. 文章统计时间使用 `published_at`，事件分析时间使用 `event_time`。
10. 所有统计结果能够追溯到对应文章及其分析证据。
