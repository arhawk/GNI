# 指标定义（METRICS）

**版本：** metrics_v0.4（对齐 Blueprint V4）  
**原则：** 研究 7 项保留；增补加权/运营监测指标；原始与加权**并列**；不做黑盒综合总分；**禁止 LLM 直接输出正式指标数值**。

默认研究单元：`Country × Source × Topic × Target × Time`（默认 Target=China）。

---

## 1. 建设分层

| 层 | 指标 | 阶段 |
|----|------|------|
| 研究核心 | Article Count、Unique Story Count、Attention Share、Sentiment Distribution、Target-bound Stance Distribution、Frame Distribution、Topic Share | **Phase 1** |
| 监测加权/运营 | Weighted Article Volume、Weighted Sentiment Score/Distribution、Weighted ± Volume、N/P Ratio、Sentiment Coverage、Source/Country Coverage 等 | **Phase 1** |
| 叙事变化 | Frame Entropy、Narrative Shift、Persistence、Source Convergence | Phase 2 |
| 派生 | Risk / 高级研究信号 | Phase 3 |

---

## 2. 每次 metric_run 必须记录

- metric_definition_version  
- numerator / denominator  
- excluded_count / missing_count / unknown_count  
- time_window / timezone（展示；数据按 UTC 过滤）  
- country_scope / source_scope / topic_scope / target_scope  
- deduplication_method  
- relevance_weight_version（若用加权）  
- computed_at  

**不得混用：** Article Count、Unique Story Count、Weighted Article Volume、Original Reporting Count、Source Count、Country Count。  
**不得合并：** Neutral、Unknown、Ambiguous、Insufficient Evidence。  
多标签主题/框架占比须说明是否允许合计 >100%。

---

## 3. Phase 1 七项研究核心指标

### 3.1 Article Count

- **问题：** 指定范围内有多少篇纳入条件的涉华文章？  
- **分子：** 通过 china_relevance / Target 过滤后的文章数（**不**被 weight 改写成小数篇）  
- **分母：** 不适用；须同时展示样本量  
- **版本：** `article_count_v1`

### 3.2 Unique Story Count

- **MVP：** 精确去重 + 单语言近似去重簇数  
- **Phase 2：** 跨语言故事聚类  
- **版本：** `unique_story_count_v1`

### 3.3 Attention Share

- **问题：** 对华报道占同一来源集合全部有效报道的比例？  
- **分子：** 对华相关文章数  
- **分母：** **同一 source_scope + time_window 内全部有效报道数**（含非对华；P1-A 全量 RSS stub 支撑）  
- **硬门禁：** 分母不可靠 / 仅采集涉华子集冒充全量时 → **禁止发布正式 Attention Share**（可标 `unavailable` / 内部调试）  
- **同时展示：** 绝对对华量（Article Count）  
- **版本：** `attention_share_v1`

### 3.4 Sentiment Distribution（Raw）

- 类别：positive / negative / neutral / mixed；另计 unknown / ambiguous  
- **版本：** `sentiment_distribution_v1`

### 3.5 Target-bound Stance Distribution

- Stance 必须绑定 Target；与 Sentiment 分开展示  
- **版本：** `stance_distribution_v1`

### 3.6 Frame Distribution / Frame Share

- primary-only 或多标签 share 须声明；taxonomy 绑定 `taxonomy_v0.4+`  
- **版本：** `frame_distribution_v1`

### 3.7 Topic Share

- Topic 与 Target 识别分离  
- **版本：** `topic_share_v1`

---

## 4. Phase 1 监测指标（加权与运营）

### 4.1 China Relevance Weight 使用规则

- 权重 `w_i ∈ [0,1]` 表达统计贡献，**不篡改** Article Count  
- Dashboard / 报告必须提供 **A 原始视图** 与 **B 加权视图**  
- 等级 → 权重映射：**provisional** 默认见 [PROVISIONAL_CALIBRATION.md](PROVISIONAL_CALIBRATION.md)（`relevance_weight_version=provisional_v0.1`）

### 4.2 加权规模与情感

| 指标 | 定义要点 |
|------|----------|
| Weighted Article Volume | `Σ w_i` |
| Weighted Positive / Negative / Neutral Volume | `Σ w_i × I(label)` 或连续贡献 |
| Weighted Sentiment Distribution | 按 `w_i` 加权的分布 |
| Weighted Sentiment Score | `Σ(w_i × s_i) / Σ(w_i)`，`s_i ∈ [-1,1]` |
| Negative-to-Positive Ratio (N/P) | 加权负面量 / 加权正面量；分母为 0 → N/A |
| Sentiment Coverage | 有效情感权重 / 纳入文章权重 |

**默认（provisional）：** Unknown / Insufficient Evidence / Mixed **不进** Weighted Sentiment Score 分母，但单独报告数量与权重；`s_i` 映射见 [PROVISIONAL_CALIBRATION.md](PROVISIONAL_CALIBRATION.md)。

不得把 Weighted Sentiment Score 称为「国家对华态度分」；推荐表述：**被监测官媒样本加权情感分数**。

### 4.3 覆盖与质量（运营）

Source Count、Country Count、Source Coverage Rate、Ingestion Success Rate、Article Extraction Success Rate 等——与舆情结论分区展示。

### 4.4 变化线索（规则侧，非正式 Phase 2 叙事指标）

Coverage Velocity、Baseline Deviation、Sentiment Shift 等可服务 Alerts / 重大新闻候选；冷启动禁用「统计显著异常」表述。

---

## 5. Phase 2 / 3（预告）

| 阶段 | 指标 |
|------|------|
| Phase 2 | Frame Entropy、Narrative Shift、Persistence、Source Convergence |
| Phase 3 | Risk / 高级研究信号 |

冷启动：0–30 / 30–90 / 90+ 规则见 Blueprint；基线不足只描述「集中/快速增长」。

---

## 6. 禁止

- LLM 直接生成正式指标数值  
- 只展示单一得分而无分布/样本量  
- 把采集失败导致的样本结构变化解释为舆情变化  
- 分母不可靠时发布正式 Attention Share  
- 将政府公告与媒体报道混为同一来源组而不声明  
