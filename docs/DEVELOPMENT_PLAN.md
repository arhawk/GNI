# 开发实施计划（DEVELOPMENT_PLAN）

**产品：** GNI  
**版本：** 0.4（对齐 Blueprint V4）  
**权威设计：** [BLUEPRINT_V4.md](BLUEPRINT_V4.md) · 审计：[PHASE0_REPOSITORY_AUDIT_V4.md](PHASE0_REPOSITORY_AUDIT_V4.md)  
**说明：** 阶段表示能力交付顺序，不是固定人周工期。V3 蓝图保留作历史。

---

## 1. 总原则

**可靠来源 → 涉华理解与 Weight → 原始/加权指标 → 重大新闻候选与预警 → 报告交付 → 深度叙事与研究 Agent**

- Central Target = China；维度 Country × Source × Topic × Target × Time  
- 每次只推进当前授权阶段  
- LLM 不算正式指标；无证据不上正式报告  
- 与 V4 §22+ 冲突时以 V4 修订为准  
- **不因文档对齐重写已验收 P1-A**  

---

## 2. Phase 0：设计与骨架

- 原 Phase 0 骨架与文档已交付  
- 2026-11-24：入库 V3 并对齐  
- 2026-11-24：入库 V4、审计报告、PRD/METRICS/DASHBOARD/ALERTS/任务书等对齐  

---

## 3. Phase 1：监测型 MVP（A–F）

| 段 | 内容 | 状态 |
|----|------|------|
| **P1-A** | 来源 + RSS 采集；≥5 监测国家 | **已验收（不重写）** |
| **P1-B** | 清洗/抽取/去重 + 规则 L1；见 Addendum A1 | **已验收** |
| **P1-C** | L2/L3 + Relevance Weight + 六维分析 | **完成** |
| **P1-D** | 七项研究指标 + 加权/运营指标；Attention 分母门禁 | **完成** |
| **P1-E** | V4 Dashboard 导航（含 Articles/Alerts/News 候选） | 待授权 |
| **P1-F** | 日/周/月报 + 规则预警 + 重大新闻候选 | 待授权 |

详见 [PHASE1_TASK_BRIEF.md](PHASE1_TASK_BRIEF.md)。

---

## 4. Phase 2 / 3

- Phase 2：跨语言故事、完整事件聚类、叙事变化指标、预警校准  
- Phase 3：开放式研究 Agent、高级专题与 Risk 深化  
- **2026-11-24 确认：** 在 **P1-F 完成前**只保留路线图，**不**写独立 P2/P3 任务书。  
- Provisional 参数与公开评测代理：[PROVISIONAL_CALIBRATION.md](PROVISIONAL_CALIBRATION.md)  
- 三级筛选补充：[BLUEPRINT_V4_ADDENDUM_A1.md](BLUEPRINT_V4_ADDENDUM_A1.md)  

---

## 5. 工程管理

ADR、Migration、pytest、合成数据标注 Synthetic；可选 Issues。
