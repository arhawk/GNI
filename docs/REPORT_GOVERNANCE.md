# 报告治理与证据约束（REPORT_GOVERNANCE）

**版本：** 0.1  
**阶段：** MVP 实现日报/周报；Agent 增强在 Phase 3

---

## 1. 报告类型（MVP）

| 类型 | 窗口 | 说明 |
|------|------|------|
| daily | 自然日（指定时区） | 主题、情感/立场摘要、重点文章、质量摘要 |
| weekly | 自然周 | 同上 + 周环比（冷启动期谨慎表述） |

月报可在 MVP 后期或 Phase 1-D 扩展；非 Phase 0 实现项。

---

## 2. 结论类型

| 类型 | 含义 | 发布规则 |
|------|------|----------|
| Fact | 有原文或可靠结构化数据支持 | 必须绑定证据 ID |
| Inference | 多证据支持的分析推断 | 明确标记为推断 |
| Hypothesis | 待验证假设 | 不得写成事实 |
| Background | 背景知识 | 不得冒充本次采集证据 |

---

## 3. 证据硬约束

正式报告中的**事实性结论**必须绑定：

- `article_id` 和/或 `evidence_id`  
- 和/或 `metric_run_id`  
- `source_id`  
- 时间窗口与统计口径  

**无证据 → 验证器拒绝写入正式报告**，或要求改写为不确定性说明。

禁止编造：文章、来源、引用、统计值、数据库 ID。

---

## 4. 报告元数据

每份报告记录：

- report_type、period_start/end、timezone  
- country_scope、source_scope  
- taxonomy_version、metric_definition_version  
- generator（rule/llm）、model/prompt 版本（若用 LLM 润色）  
- sample_size、coverage notes、limitations  
- created_at、content 快照  

生成后保留**证据快照**，避免来源文章后续更新导致不可复核。

---

## 5. Agent 边界（Phase 3 预告）

Agent 可：查询、归纳、在工具结果上起草。  
Agent 不可：替代采集、替代指标计算、凭空判断事件、无证据预测政策。

流程：`Research Question → Query Tools → Evidence Retrieval → Draft Claims → Evidence Validation → Report`
