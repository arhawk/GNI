# Blueprint V4 对照审计与默认裁决

**日期：** 2026-11-24  
**权威：** [BLUEPRINT_V4.md](BLUEPRINT_V4.md)（**§22 及以后冲突时优先**）  
**原则：** 文档对齐；**不**重写已验收 P1-A 采集栈。

---

## 1. 仓库现状（摘要）

- Phase 0 文档 + 工程骨架已完成；P1-A RSS 采集已验收（≥5 监测国家、全量 feed stub）
- 技术栈与 V4 MVP 一致（Modular Monolith、Postgres、Cron/APScheduler、无 Kafka/Prefect 强制）
- 未实现：P1-B 清洗、P1-C LLM/相关度权重、P1-D 指标、Dashboard、预警、重大新闻

---

## 2. V4 vs 当前 docs 关键差异

| 主题 | 当前（V3 对齐后） | V4（§22+） | 裁决 |
|------|-------------------|------------|------|
| 产品形态 | 对华研究分析平台 | Agent 驱动**监测**（自动监测→理解→量化→发现→报告→预警） | 采用 V4；深度叙事后置 |
| 涉华加权 | china_relevance 雏形 | **China Relevance Weight** + 原始/加权双视图 | 纳入 Phase 1 文档与 Schema |
| 指标 | 7 项研究指标 | 7 项 + 加权/运营监测指标 | METRICS 增监测章节；无黑盒总分 |
| Frame 词表 | taxonomy_v0.1 旧 10 类 | V4 候选框架集 | 升版 taxonomy_v0.4 |
| Dashboard | 总览/国家/跨国/质量 | Overview、Countries、News&Events、Articles、Reports、Alerts、Quality、Research | 重写 DASHBOARD |
| 重大新闻 | 偏 Phase 2 事件 | P1 **规则型候选**（非完整聚类） | 任务书纳入 |
| 预警 | Phase 3 Risk | P1 **规则型 Alerts** | 新增 ALERTS.md；研究 Agent 仍 Phase 3 |
| Attention Share | 同源全量分母 | 分母不可靠则**禁止正式发布** | 硬约束；现全量 stub 有利 |
| P1-A 门槛 | ≥5 **监测国家** | §17 写「≥5 个来源」 | **保持 ≥5 监测国家**；建议回写 V4 §17 |
| Agent | Phase 3 | 监测编排可轻量；开放式研究 Agent 非 MVP | ARCHITECTURE 写清边界 |

---

## 3. 内文张力默认裁决

1. **Agent 驱动 ≠ MVP 全自主研究 Agent：** MVP = 确定性流水线 + 规则预警 + 模板/辅助报告；多步骤研究 Agent → Phase 3。  
2. **重大新闻 ≠ 完整事件聚类：** P1 规则打分/候选列表；可控 False-Merge 的事件系统 → Phase 2。  
3. **权重不篡改原文计数：** Article Count 与 Weighted Article Volume 必须并列。  
4. **P1-A 代码不重写。**

---

## 4. 待标定 → 已冻结 provisional（2026-11-24）

详见 [PROVISIONAL_CALIBRATION.md](PROVISIONAL_CALIBRATION.md)：

- Relevance 等级→权重中点/区间与 incidental 默认不进核心统计  
- Sentiment `s_i` 与 Mixed 不进加权分母  
- 预警阈值与冷启动禁用（`alert_rules_provisional_v0.1`）  
- 重大新闻特征权重（`major_news_score_provisional_v0.1`）  
- 公开评测代理：GDELT_chinaNews 等（非 GNI 金标）  

Agent 模块接口 ADR 仍可后置；交付切分以任务书 P1-A→F 为准（非 V4 Sprint 字母）。

---

## 5. 本轮文档动作

入库 V4；更新 PRD、PRODUCT_SCOPE、METRICS、AI_ANALYSIS、TAXONOMY、DASHBOARD、ALERTS、PHASE1_TASK_BRIEF、REPORT_GOVERNANCE、ARCHITECTURE、ARTICLE_ANALYSIS_SCHEMA、DEVELOPMENT_PLAN、README；后续冻结 PROVISIONAL_CALIBRATION。
