# 每月研判规格（MONTHLY_REPORT_SPEC）

**版本：** monthly_report_schema_v1（**规则组装已实现**；高级可视化后置）  
**产品名：** China Media Monthly Strategic Review（MVP 五国监测样本）  
**核心问题：** 一个月以来，被监测样本中对华报道格局发生了什么变化？  
**依赖：** [REPORT_PRODUCTS.md](REPORT_PRODUCTS.md)、日报/周报 facts、稳定长窗数据。  
**阅读时长：** 15–30 分钟。

---

## 1. 定位

月报**不能**合并四周周报。从情报监测升级为战略性分析：长期趋势、国家差异、结构性变化。  
须按统一口径基于文章级数据**重算**，禁止简单日均。  

UI 参考：[assets/report-ui/monthly-visual-ref.png](assets/report-ui/monthly-visual-ref.png)

---

## 2. 固定目录

| # | 章节 | 重要性 | 必须回答 |
|---|------|--------|----------|
| 1 | Monthly Executive Assessment | 必须 | 关注度变化、主议题、国家叙事变化、情感立场变化、可能延续到下月的趋势 |
| 2 | Global Attention Landscape | 必须 | 国家/媒体覆盖、集中度、Topic Share、月增速 |
| 3 | Major Event Retrospective | 必须 | 3–10 个大事完整过程与关键节点 |
| 4 | Country-Level Analysis | 必须 | 监测媒体画像（非政府立场） |
| 5 | Narrative Landscape | 必须 | 主导/新兴/减弱叙事；跨国覆盖；勿混「出现次数」与「叙事强度分」 |
| 6 | Sentiment & Stance Long-term Trends | 必须 | 保留 Target 维度；事件冲击与持续性 |
| 7 | Emerging Risks & Strategic Signals | 必须 | 持续性关注、叙事强化、跨国扩散、议题迁移、结构变化 |
| 8 | Outlook | 建议 | 观察对象、依据、后续指标、触发条件、不确定性（非预测必然） |
| 9 | Data Coverage & Methodology | 必须 | 元数据与局限 |

---

## 3. 实现状态

**schema v1 已实现**（`src/gni/reports/monthly.py` + `/api/reports/monthly` + 报告中心 Tab）。  
未做：参考图级战略可视化。文案限定 **MVP 五国监测样本**，禁止「全球舆论」夸大。

禁止：仅凭报道变化推断政府意图、政策结果或真实社会风险。
