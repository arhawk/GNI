# 每周分析规格（WEEKLY_REPORT_SPEC）

**版本：** weekly_report_schema_v1（**规则组装已实现** + `methodology_v1.0`；高级可视化后置）  
**统计口径：** 严格遵循 [STATISTICAL_METHODOLOGY_V1.md](STATISTICAL_METHODOLOGY_V1.md)（按 `published_at` 入窗、唯一 `Article Count`、`sections.v1_stats` / `v1_stats_prev` 输出四层级与对华立场覆盖率）。  
**产品名：** Weekly Intelligence Report  
**核心问题：** 这一周发生了什么变化？这些变化意味着什么？  
**依赖：** [REPORT_PRODUCTS.md](REPORT_PRODUCTS.md)、日报 facts 管线、更长窗口指标与事件演化。  
**阅读时长：** 8–15 分钟。

---

## 1. 定位

周报**不能**简单合并七份日报。日报回答事件；周报回答：

- 事件如何发展  
- 国家间报道差异  
- 一周内情感 / 立场 / 叙事如何变化  

UI 参考：[assets/report-ui/weekly-visual-ref.png](assets/report-ui/weekly-visual-ref.png)

---

## 2. 固定目录

| # | 章节 | 重要性 | 必须回答 |
|---|------|--------|----------|
| 1 | Weekly Executive Summary | 必须 | 整体变化、3–5 大事、国家关注变化、主题升降、跨国叙事、持续关注点 |
| 2 | Weekly Major Events Review | 必须 | 本周进展、涉及国家、关注程度、当前状态 |
| 3 | Event Evolution | 必须 | 事件本身变化 vs 报道关注点变化 vs 各国首次报道/跟进时间（三者分列） |
| 4 | Cross-country Narrative Comparison | 必须 | 同事件不同框架；共同/国别特有；本周新增与强弱变化 |
| 5 | Topic Trends | 必须 | 本周排名、环比、新出现/持续/消退（量变 ≠ 态度变） |
| 6 | Sentiment & Stance Changes | 必须 | 国家 × Target × 时间；禁止单一全球情感分 |
| 7 | Emerging Issues & Risk Signals | 必须 | 连续增长、跨国扩散、持续异常 |
| 8 | Data Coverage & Methodology | 建议 | 窗口、覆盖缺口、口径版本 |

---

## 3. 实现状态

**schema v1 已实现**（`src/gni/reports/weekly.py` + `/api/reports/weekly` + 报告中心 Tab）：

- 周环比 facts（vs 上周）  
- 事件演化占位（规则 v1 列表；完整时间线后置）  
- 国家 × 主题 / 框架摘要  
- 报告中心 Weekly 真页（明细可折叠）  

未做：参考图 Sankey / 社媒兴趣曲线。  
禁止项同 [REPORT_GOVERNANCE.md](REPORT_GOVERNANCE.md)：LLM 不点数；不把样本写成国家立场。
