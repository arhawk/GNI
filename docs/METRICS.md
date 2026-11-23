# 指标定义（METRICS）

**版本：** metrics_v0.1  
**原则：** 先独立可解释指标；MVP **不**实现综合舆情总分。

---

## 1. 六个分析维度（跨层级）

Sentiment、Stance、Framing、Attention、Narrative Shift、Risk Signal  

它们**不是**可直接相加的六个字段。每个维度须分别定义文章级 / 事件级 / 叙事级计算对象。

| 维度 | MVP | Phase 2+ |
|------|-----|----------|
| Sentiment 分布 | 是（文章聚合） | 事件/叙事级增强 |
| Stance 分布 | 是（按 Target） | 同上 |
| Framing 分布 | 是（基础） | 热力图等 |
| Attention | 基础版 | 去重增强后完整版 |
| Narrative Shift | 否 | 是（需基线） |
| Risk Signal | 否（冷启动禁止确定性异常） | 条件成熟后 |

---

## 2. 统计单位

**叙事级建议单位（Phase 2 起）：**  
`Country × Topic × Time × Source Group × Target`

**MVP 聚合：** 主要按 `Country × Topic × Time Window` 与 `Country × Target × Time Window` 展示分布。

---

## 3. 通用元数据（每次 metric_run）

必须记录：

- metric_definition_version  
- time_window、timezone（展示）、数据按 UTC 过滤  
- source_scope、topic_scope、target_scope  
- numerator、denominator、excluded_count、missing_count  
- deduplication_method  
- computed_at  

Unknown / Ambiguous / Neutral **不得混为一类**。

---

## 4. MVP 指标定义

### 4.1 SentimentShare

- **对象：** 指定国家/时间窗/来源范围内的文章（或 Unique Story，口径须声明）  
- **分子：** sentiment = 某类（如 negative）的篇数  
- **分母：** 具有明确 sentiment（非 unknown）的篇数；若用全部文章作分母须标注  
- **去重：** MVP 默认 URL/Hash 去重后的 Article Count；近重策略写进 run 元数据  

### 4.2 StanceShare

- **对象：** 绑定特定 `target_id`  
- **公式示例：** 明确批评的独立报道数 / 具有明确立场的独立报道数  
- **注意：** 多 Target 文章按 Target 分别计入  

### 4.3 FrameShare

- **分子：** 含某 frame 的文章数（多标签会导致份额之和可 >1；须注明）  
- **分母：** 有框架标注的文章数（或全部相关文章，须注明）  

### 4.4 Attention（基础版）

组合披露（不合成黑盒分）：

- Article Count  
- Unique Story Count（MVP：精确去重 + 单语言近重簇数）  
- Source Count  
- （Phase 2）Original Reporting Count、Syndicated Story Count、Reprint Ratio  

相对历史基线的变化率：冷启动期仅展示原始计数，不标「异常」。

### 4.5 TopicShare

- 某主题文章数 / 窗口内中国相关文章总数（相关性定义见 Phase 1 配置）  

---

## 5. Phase 2+ 指标（预告，MVP 不实现）

### Narrative Shift

比较当前窗口与基线窗口的框架/立场/主题分布，可用 Jensen-Shannon Divergence。高值 = 分布差异大，**不**表示正负面。

### Frame Entropy

\( H = -\sum p_i \log p_i \)，可按有效类别数标准化。低 = 框架集中；高 ≠ 客观。

### Persistence / Convergence / Risk Signal

见 Blueprint V2；须排除转载与共同引源等解释；Risk 不能由单篇认定。

---

## 6. 冷启动

| 阶段 | 天数 | 行为 |
|------|------|------|
| Cold Start | 0–30 | 不发布确定性异常结论 |
| Baseline Building | 30–90 | 可展示初步变化，降低置信度并说明限制 |
| Baseline Ready | 90+ 且样本/覆盖达标 | 才启用正式基线比较 |

90 天不是充分条件；低频主题可能需要更久。

---

## 7. 综合指数（Phase 3）

\[
I = \sum_{i=1}^{n} w_i S_i,\quad \sum_i w_i = 1
\]

约束：分项可解释、权重可配置可版本化、仅用于排序/筛选、不做因果推断。MVP **不实现**。

---

## 8. 禁止

- LLM 直接生成指标数值作为正式结果  
- 把采集失败导致的样本结构变化解释为舆情变化（须对照质量面板）  
