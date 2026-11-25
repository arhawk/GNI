# GNI 阶段状态（权威）

**版本：** phase_status_v1（2026-11-25）  
**用途：** 消除 README / PHASE1_TASK_BRIEF / 报告文档之间对「P1-F」含义的冲突。Agent 与人工以本表为准。

---

## Phase 1 拆分

| 阶段 | 内容 | 状态 |
|------|------|------|
| P1-A～P1-E | 采集、处理、分析、指标、Dashboard | **已完成** |
| P1-F1 | Proto Event / Event Fingerprint | **原型已实现**；持续修三时间、稳定 ID、增量 rebuild |
| P1-F2 | Daily Report v2（Daily Brief） | **已实现**；持续验收 |
| P1-F3 | 持久化 Alerts 生命周期 | **待完成**（见 BATCH2 接口说明） |
| P1-F4 | Weekly / Monthly Reports | **规格完成**；编码待第三批 |
| Phase 2 | 完整跨语言事件聚合、叙事演化 | **后续** |
| Phase 3 | 开放式研究 Agent | **后续** |

互链：

- 任务书总览：[PHASE1_TASK_BRIEF.md](PHASE1_TASK_BRIEF.md)（历史 A～F 叙述保留；细节以本表 F1–F4 为准）
- 报告产品：[REPORT_PRODUCTS.md](REPORT_PRODUCTS.md)
- 预警规范：[ALERTS.md](ALERTS.md)（生命周期持久化 = P1-F3）

---

## 抽样漏检评估（L2）

对 `not_china_related` 与 `possible_china` 结果按日随机抽 20～50 篇人工复核，记录：

- 漏检（应为涉华却标 not_china）
- 过召（非涉华却进入深度分析）

不要求本阶段上完整评测平台；结果写入实验笔记或 `data/` 旁注即可。
