# Dashboard 信息架构（DASHBOARD）

**版本：** 0.4（对齐 Blueprint V4 §29）  
**技术：** Streamlit（MVP）  
**原则：** 按监测任务与交付组织页面；原始计数与加权量并列；情感与立场分图。

---

## 1. 全局筛选

| 筛选 | 说明 |
|------|------|
| 时间范围 | 自然日/周/月或滚动窗口；展示时区可配，数据 UTC |
| 国家 | 短名单多选 |
| 来源组 | 如 state_controlled / public_service / gov_comms |
| Topic / Target | **默认 Target=China** |
| Sentiment / Stance / Frame | 可选 |
| China Relevance Level | Core → Incidental / Not Relevant |
| 语言 / 分析状态 | 可选 |

所有图表显示：时间窗口、时区、样本量、加权样本量、分母口径、metric / weight 版本。

**Attention Share：** 分母不可靠时不展示正式值（见 [METRICS.md](METRICS.md)）。

---

## 2. Phase 1 主导航（V4）

### 2.1 Overview（舆情总览）

**问题：** 现在发生了什么？哪些变化值得关注？

- KPI：涉华 Article Count、Weighted Article Volume、正负比例、监测国家/活跃来源、重大新闻候选数、高优先级预警数  
- 加权情感趋势、国家量/情感变化排名  
- 重点正/负面文章、重大新闻候选、最新预警  
- 可选 Agent/模板生成的当日摘要  
- 采集与分析质量状态条  

### 2.2 Countries（国家监测）

**问题：** 某国被监测官方媒体如何报道中国？

- 报道量、加权量、情感趋势（raw + weighted）  
- Topic / Target / Frame；来源贡献  
- 该国近期重大新闻候选与预警  
- 下钻文章与证据  

### 2.3 News & Events（重大新闻/事件）

**Phase 1：** 规则/相似度**候选簇**列表（非完整事件图谱）。

- 筛选：时间、国家、Topic、重要性/突发候选分  
- 展示：摘要、覆盖国家/来源、报道趋势、情感分布、关联文章  
- 允许人工合并/拆分反馈（完整事件生命周期 → Phase 2）  

### 2.4 Articles（文章库）

过滤：国家、来源、日期、Topic、Target、Sentiment、Stance、Frame、Relevance Level、分析状态、是否关联新闻候选。

列表：标题、来源、国家、时间、weight、情感、立场、Topic、Target、簇、原文链接。

详情：涉华片段、分析结果、证据、模型/权重版本、人工纠正入口。

### 2.5 Reports（报告中心）

日报/周报/月报列表；生成/截止时间、覆盖范围、校验状态；结论可展开证据。

### 2.6 Alerts（预警中心）

级别、类型、范围、触发时间、状态；规则与基线细节；代表文章；误报反馈。质量类与舆情类分栏。详见 [ALERTS.md](ALERTS.md)。

### 2.7 Sources & Quality（来源与数据质量）

来源属性与审核证据；采集成功率、提取率、时间完整率；重复率、分析成功率、Token/费用。**与舆情结论分区。**

### 2.8 Research（研究分析）

Phase 1 可占位或轻量下钻；跨国热力图等深化可后置。开放式研究 Agent → Phase 3。

---

## 3. Phase 2+（预告）

完整事件生命周期、Narrative Shift / Entropy 等叙事变化页；Risk 提示与研究 Agent 工作台。

---

## 4. 交互路径

```text
Overview / Alerts → Country / News candidate → Chart → Articles → Evidence → Report
```

建议图表：排名横条、时间折线/堆叠、100% 堆叠分布、热力图、文章表。地图仅覆盖辅助。

---

## 5. 与 VISUALIZATION_SPEC

本文件定义页面与监测问题；[VISUALIZATION_SPEC.md](VISUALIZATION_SPEC.md) 补充图表约束。冲突时以本文件与 Blueprint V4 §22+ 为准。
