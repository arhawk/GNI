# Provisional 标定默认值与公开评测代理

**状态：** `provisional_v0.2`（2026-11-24；对齐 Addendum A1 等级词表）  
**权威：** [BLUEPRINT_V4_ADDENDUM_A1.md](BLUEPRINT_V4_ADDENDUM_A1.md) §6；[BLUEPRINT_V4.md](BLUEPRINT_V4.md)  
**原则：** 临时默认可运行、可版本化；**不能**冒充已校准金标。

---

## 1. China Relevance Level / Weight（provisional）

| Level | 定义摘要 | weight 中点 | 区间 | 核心舆情纳入 |
|-------|----------|-------------|------|--------------|
| core | 中国/明确 Target 为主要讨论对象 | 0.90 | 0.80–1.00 | 是 |
| substantial | 重要参与方或重要分析对象 | 0.65 | 0.50–0.79 | 是 |
| secondary | 有实质意义的次要对象/背景 | 0.35 | 0.20–0.49 | 是（可配置） |
| incidental | 简短提及，研究意义有限 | 0.10 | 0.01–0.19 | **默认否** |
| none | 无实质涉华 | 0.00 | 0.00 | 否 |
| uncertain | 证据不足 | null | — | 否；不计加权分母 |

**旧名映射（v0.1 → v0.2）：** major→substantial；moderate→secondary；minor→incidental（或 secondary，按语境）；not_relevant→none；unknown→uncertain。

- `estimated_share` ≠ `weight`；版本：`relevance_weight_version=provisional_v0.2`  
- Article Count **永不**被 weight 改写  

---

## 2. Sentiment 连续分（provisional）

| label | `s_i` 默认 |
|-------|------------|
| positive | MVP 可用 +0.60 |
| neutral | 0.00 |
| negative | MVP 可用 −0.60 |
| mixed | **不进** Weighted Sentiment Score 分母 |
| unknown / insufficient_evidence | **不进**分母 |

---

## 3. 预警阈值（provisional）

见既有规则表；版本 `alert_rules_provisional_v0.1`。冷启动禁用正式「统计显著」断言。

---

## 4. 重大新闻候选打分（provisional）

版本 `major_news_score_provisional_v0.1`；**禁止**用负面情感替代重要性。

---

## 5. 公开标注集（评测代理）

| 数据集 | 用途 |
|--------|------|
| [GDELT_chinaNews](https://github.com/sunlizhuang/GDELT_chinaNews) | 英文涉华正/负 smoke |
| [GateNLP/chinese-news-framing](https://github.com/GateNLP/chinese-news-framing) | Frame 方法参考 |
| CNTSenti / HF Trade Tension | 思路参考；后者多为模型标 |

无公开集覆盖 Relevance Weight → 继续 provisional。

---

## 6. 筛选分层（Addendum）

- L1 标题：调度/优先级，非终裁（P1-B 规则实现）  
- L2 正文：最终纳入（P1-C）  
- L3 片段：分析输入（P1-C）  
