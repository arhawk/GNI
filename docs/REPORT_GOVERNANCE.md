# 报告治理与证据约束（REPORT_GOVERNANCE）

**版本：** 0.5（对齐 Blueprint V4 §27 + 数据五层）  
**阶段：** MVP 实现日报/周报/月报模板 + 规则预警投递；开放式研究 Agent 在 Phase 3  
**数据层：** 报告属 [DATA_LAYERS.md](DATA_LAYERS.md) Layer 5；`reports*` 表后置，MVP 产物可落 `data/daily_report_*.md`。仅使用 `AVAILABLE_FOR_ANALYTICS` / 已分析涉华样本；禁止无证据编造。

---

## 1. 报告类型（MVP）

| 类型 | 窗口 | 说明 |
|------|------|------|
| daily | 自然日（指定时区） | **七段冻结格式**见 [DAILY_REPORT_SPEC.md](DAILY_REPORT_SPEC.md)：口径→关注→语气/立场→议题/框架→事件主线→代表证据→质量 |
| weekly | 自然周 | 同上 + 周环比与走势（冷启动谨慎） |
| monthly | 自然月 | 格局与持续性；须按统一口径基于文章级数据重算，禁止简单日均 |

重大新闻候选简报可作为日报章节或独立投递；结构见 Blueprint V4 §26.5。

---

## 2. 结论类型

| 类型 | 含义 | 发布规则 |
|------|------|----------|
| Fact | 有原文或可靠结构化数据支持 | 必须绑定证据 ID |
| Inference | 多证据支持的分析推断 | 明确标记为推断 |
| Hypothesis | 待验证假设 | 不得写成事实 |
| Background | 背景知识 | 不得冒充本次采集证据 |

标准表述须落在「被监测官媒样本」，禁止无证据扩大为国家政策/民意结论。

---

## 3. 证据硬约束

正式报告中的**事实性结论**必须绑定：

- `article_id` 和/或 `evidence_id`  
- 和/或 `metric_run_id` / `alert_id`  
- `source_id`  
- 时间窗口与统计口径（含 weight 版本）  

**无证据 → 验证器拒绝写入正式报告**，或要求改写为不确定性说明。

禁止编造：文章、来源、引用、统计值、数据库 ID。

---

## 4. 报告元数据

每份报告记录：

- report_type、period_start/end、timezone  
- country_scope、source_scope  
- taxonomy_version、metric_definition_version、relevance_weight_version  
- generator（rule/llm）、model/prompt 版本（若用 LLM 润色）  
- sample_size、weighted_sample、coverage notes、limitations  
- created_at、content 快照  

生成后保留**证据快照**。自然语言生成不得改写统计结果。

---

## 5. 与预警的关系

规则预警摘要可进入日报「异常变化」；完整生命周期与反馈见 [ALERTS.md](ALERTS.md)。质量类（SOURCE_HEALTH_FAILURE）不得伪装为舆情结论。

---

## 6. Agent 边界

**MVP：** 模板拼装 + 可选润色 + Evidence QA。  
**Phase 3：** 开放式研究问题多步骤检索。  

Agent 不可：替代采集、替代指标/阈值计算、无证据声称重大事件、推断政府真实意图。
