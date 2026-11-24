# Dashboard 信息架构（DASHBOARD）

**版本：** 0.5（对齐 Blueprint V4 §29 + Event Intelligence IA）  
**技术：** 目标 UI = React（`web/`）；Streamlit 保留为调试入口  
**原则：** 按监测任务组织；raw/weighted 并列；情感与立场分图；**事件发生地 ≠ 报道来源国**。  
**事件模型权威：** [EVENT_INTELLIGENCE_IA.md](EVENT_INTELLIGENCE_IA.md)

---

## 1. 全局筛选

| 筛选 | 说明 |
|------|------|
| 时间范围 | 自然日/周/月或滚动窗口；展示时区可配，数据 UTC |
| 国家 | 短名单多选（报道来源国） |
| 来源组 | 如 state_controlled / public_service / gov_comms |
| Topic / Target | **默认 Target=China** |
| Sentiment / Stance / Frame | 可选 |
| China Relevance Level | Core → Incidental / Not Relevant |
| 语言 / 分析状态 | 可选 |

所有图表显示：时间窗口、时区、样本量、加权样本量、分母口径、metric / weight 版本。

**Attention Share：** 分母不可靠时不展示正式值（见 [METRICS.md](METRICS.md)）。

---

## 2. 主导航（分组壳）

### MONITORING

| 页 | 对应 |
|----|------|
| 总览 Overview | §2.1 |
| 国家与媒体 | Countries + Sources 可切换（§2.2 / §2.7） |
| 新闻中心 | News & Events / proto-Event 列表（§2.3） |

### INTELLIGENCE

| 页 | 对应 |
|----|------|
| 舆情趋势 | 趋势与分布下钻 |
| 事件与叙事 | Event 三视图（Where / Who reports / How they frame） |
| 异常与预警 | Alerts（§2.6） |

### REPORTS

| 页 | 对应 |
|----|------|
| 报告中心 | Reports（§2.5） |
| 系统与数据 | Sources & Quality（§2.7） |

---

## 2.1 Overview（总览五块）

**问题：** 现在发生了什么？哪些变化值得关注？

| 块 | 内容 |
|----|------|
| A KPI | 总文章、涉华 Article Count、监测国家、活跃来源、重大事件(Event/候选数)、预警数；**Weighted Volume 与 Article Count 分列** |
| B 地图 | **默认事件地图**（发生/宣布地钉）；可切换 **对华态度地图**（监测国媒体情感汇总色，无样本灰）。`reporting_source` API 保留、UI 不主推。互斥；态度文案须注明「被监测官媒样本」 |
| C 趋势 | 涉华量 + 情感分线（Sentiment ≠ Stance） |
| D 主题 | `taxonomy_v0.4` 分布（非威胁八类） |
| E 重要与异常 | 重大候选、量突增国、主题异动、基线异常 |

禁止：威胁情报八色图例；US/China-Aligned 站队着色；把报道国钉成事件发生地。

---

## 2.2 国家与媒体监测

**问题：** 某国被监测官方媒体如何报道中国？

- 左：国家列表（搜索、地区、报道量/情感排序、时间窗）  
- 右：详情 Tab（趋势、媒体贡献、Sentiment、Stance、Topic、Frame、近期新闻、历史）  
- **国家 ↔ 媒体**可切换；一国媒体不得压成单一「国家立场」  

---

## 2.3 新闻中心 / Event 列表

**Phase 1：** 规则型重大新闻候选 = **proto-Event**（非完整事件图谱）。

- 筛选：时间、Topic、重要性分、是否有坐标  
- 列表：标题、地点类型摘要、参与方、报道国家数、关联文章数  
- 进入事件详情三视图（§2.3.1）  

### 2.3.1 事件详情

同一 Event ID：

1. **Where** — 分类型地点地图  
2. **Who reports** — 国家 → 媒体 → 文章  
3. **How they frame** — 叙事簇 + 证据  
4. **时间线** — 发生 / 首报 / 叙事变化 / 后续  

---

## 2.4 Articles（文章库）

过滤：国家、来源、日期、Topic、Target、Sentiment、Stance、Frame、Relevance Level、分析状态、是否关联 Event。

列表与详情：标题、weight、情感、立场、Topic、原文；涉华片段与证据。

---

## 2.5–2.8 Reports / Alerts / Sources / Research

同 V4：报告列表与证据；预警分舆情/质量栏；来源质量与舆情分区；Research 可占位。

---

## 3. Phase 2+

完整事件生命周期、跨语言聚类、Narrative Shift / Entropy；开放式研究 Agent → Phase 3。

---

## 4. 交互路径

```text
Overview → Event pin / 异常列表 → Event 三视图（多源文章 + 上卷情感）→ Articles / Evidence → Report
Overview → 对华态度地图 → Country 下钻（正/中/负/未知篇数 + 文章抽样）

日报数据口径：**事件主线 + 文章证据**（见 [EVENT_FINGERPRINT.md](EVENT_FINGERPRINT.md)）；生成器可后置。
```

---

## 5. 与 VISUALIZATION_SPEC / EVENT_INTELLIGENCE_IA

页面与监测问题以本文件为准；事件语义以 [EVENT_INTELLIGENCE_IA.md](EVENT_INTELLIGENCE_IA.md) 为准；图表约束见 [VISUALIZATION_SPEC.md](VISUALIZATION_SPEC.md)。冲突时以 Blueprint V4 §22+ 与 Event IA 为准。
