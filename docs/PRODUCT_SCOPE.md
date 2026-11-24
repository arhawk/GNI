# 产品范围（PRODUCT_SCOPE）

**产品：** Global Narrative Intelligence（GNI）  
**文档语言：** 中文  
**版本：** 0.4（对齐 Blueprint V4）  
**权威：** [BLUEPRINT_V4.md](BLUEPRINT_V4.md)（§22+ 冲突优先）

---

## 1. 产品一句话

以 **China** 为固定研究对象，由监测流水线（可含轻量 Agent 编排）持续采集他国官方媒体，理解涉华内容并按 **China Relevance Weight** 量化，发现重大新闻候选与异常，自动交付报告与规则预警。

---

## 2. 研究视角与维度

| 层面 | 约定 |
|------|------|
| Central Target | China（可细分为政府/经济/科技/军事/社会/外交/实体等） |
| 观察样本 | 他国官方媒体 + 政府传播；属性分类、分组统计 |
| 默认单元 | Country × Source × Topic × Target × Time |
| MVP 国家短名单 | US、RU、DE、IN、AU |
| P1-A 验收门槛 | **≥5 监测国家**各 ≥1 个 verified+active 源 |
| 样本平衡（2026-11-24） | 目标各国约 **2** 个 active 源；能采到则优先本地语言（RU/DE/IN），不以英文为默认 |
| 扩展池 | 加拿大等，按可采集性纳入 |

「全球」= 跨国覆盖，≠ 全球所有议题，≠ 公众民意。

---

## 3. Phase 边界

### Phase 1 / MVP（监测型）

- 来源治理与稳定采集（P1-A 已完成，不重写）  
- 清洗、去重、涉华片段定位、**Relevance Weight**、六维文章分析  
- 7 项研究指标 + 加权/运营监测指标；**原始/加权双视图**  
- 规则型重大新闻候选 + 规则 Alerts  
- Dashboard：Overview / Countries / News&Events / Articles / Reports / Alerts / Quality  
- 日报 / 周报 / 月报模板 + 证据校验  

### Phase 2

跨语言故事、可控事件聚类、Frame Entropy、Narrative Shift、Persistence、Convergence、预警统计校准。

### Phase 3

开放式研究 Agent、复杂专题、Risk / 研究信号深化。

---

## 4. MVP 明确不做

- 推断国家真实意图或全民舆论  
- 黑盒综合舆情总分 / 「国家对华态度分」  
- 强爬登录/付费墙/不可评估站点  
- 完整事件图谱与开放式研究 Agent  
- 分母不可靠时发布正式 Attention Share  

---

## 5. 成功标准（摘要）

用户无需日读全量官媒，即可通过总览、报告、重大新闻候选与主动提醒，了解被监测样本对华报道量、倾向与重要变化，并能一键追溯原文与口径。详见 [PRD.md](PRD.md)。
