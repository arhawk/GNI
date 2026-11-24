# Provisional 标定默认值与公开评测代理

**状态：** `provisional`（2026-11-24 冻结，供 P1-C 起使用）  
**权威区间来源：** [BLUEPRINT_V4.md](BLUEPRINT_V4.md) §23–24、§27  
**原则：** 临时默认可运行、可版本化；**不能**冒充已校准金标；变更须升 `relevance_weight_version` / 规则版本。

---

## 1. China Relevance Weight（provisional）

| Level | weight 默认中点 | 区间 | 核心舆情纳入 |
|-------|-----------------|------|--------------|
| core | 0.92 | 0.85–1.00 | 是 |
| major | 0.72 | 0.60–0.84 | 是 |
| moderate | 0.45 | 0.30–0.59 | 是 |
| minor | 0.20 | 0.10–0.29 | 是（可配置） |
| incidental | 0.05 | 0.01–0.09 | **默认否**（库内保留） |
| not_relevant | 0.00 | 0.00 | 否 |
| unknown | null | — | 否；不计加权分母 |

- `estimated_share` ≠ `weight`；weight 由等级规则映射，存 `relevance_weight_version=provisional_v0.1`。  
- Article Count **永不**被 weight 改写；Dashboard 必须 raw ∥ weighted 并列。

---

## 2. Sentiment 连续分（provisional）

| label | `s_i` 默认 |
|-------|------------|
| positive | +0.70（强）/ +0.40（偏）可按 intensity 细分；MVP 可用 +0.60 |
| neutral | 0.00 |
| negative | −0.60（偏）/ −0.80（强）；MVP 可用 −0.60 |
| mixed | **不进** Weighted Sentiment Score 分母；单独计 Weighted Mixed Volume |
| unknown / insufficient_evidence | **不进**分母；单独报告数量与权重 |

展示分段（非客观边界）：±0.60 强、±0.20–0.59 偏、|s|<0.20 近中性（仍须结合 Neutral 标签）。

---

## 3. 预警阈值（provisional，冷启动禁用正式异常断言）

| 规则 | 临时触发（示例） | 冷启动 |
|------|------------------|--------|
| VOLUME_SPIKE | 窗口量 ≥ 同来源/国 过去 7 日日均 × 2.0，且绝对增量 ≥ 5 篇 | 来源有效日 < 14：只标「集中」，不发正式 spike |
| NEGATIVE_SHARE_RISE | 负面 raw 或加权占比相对基线 +15pp，且样本 ≥ 10 | 同上 |
| SENTIMENT_SHIFT | \|Δ Weighted Sentiment Score\| ≥ 0.25，有效加权样本 ≥ 10 | 基线窗不足则禁用 |
| MULTI_COUNTRY_COVERAGE | 同一候选簇 ≥ 3 国 | 无簇则跳过 |
| SOURCE_HEALTH_FAILURE | 连续失败 ≥ 3 或 24h 无成功 | 立即（质量类） |

全部规则版本：`alert_rules_provisional_v0.1`。阈值非 σ 严格估计，待数据成熟再校准。

---

## 4. 重大新闻候选打分（provisional）

特征权重（归一化前线性加总，再 clip 到 0–1）：

| 特征 | 权重 |
|------|------|
| 多独立来源数（≥2/≥3） | 0.25 |
| 多国家覆盖（≥2/≥3） | 0.25 |
| 短窗报道速度相对基线 | 0.20 |
| 标题/导语涉华 + Target 高 prominence | 0.15 |
| 官方声明/领导人/政策关键词命中 | 0.15 |

**禁止**用负面情感分替代重要性。版本：`major_news_score_provisional_v0.1`。

---

## 5. 公开标注集（评测代理，非 GNI 金标）

| 数据集 | 用途 | 局限 |
|--------|------|------|
| [GDELT_chinaNews](https://github.com/sunlizhuang/GDELT_chinaNews) | 英文涉华正/负 smoke / 回归 | 无 Stance/Frame/Weight；非官媒限定 |
| [GateNLP/chinese-news-framing](https://github.com/GateNLP/chinese-news-framing) | Frame 多标签评测方法参考 | 词表 ≠ `taxonomy_v0.4`；正文常需自取 |
| [CNTSenti](https://link.springer.com/chapter/10.1007/978-3-031-72350-6_7) | 长文 Target 情感思路 | 需另行获取；中文域 |
| HF [International Trade News Tension](https://huggingface.co/datasets/Porkonsale/International_Trade_News_Tension_Analysis_Dataset) | 连续强度分参考 | **多为模型标**，不当真人金标 |

**裁决：** P1-C/D 优先接入 GDELT_chinaNews 作代理评测；GNI 官媒样本仍须抽检。无公开集覆盖 Relevance Weight → 继续 provisional。

---

## 6. 交付切分提醒

实施顺序以 [PHASE1_TASK_BRIEF.md](PHASE1_TASK_BRIEF.md) **P1-A→F** 为准；五国接通序 **美→俄→德→印→澳**。不以 V4 Sprint A–F 字母重排。Phase 2/3 任务书延后至 P1-F 完成。
