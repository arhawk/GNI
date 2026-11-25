# 报告治理与证据约束（REPORT_GOVERNANCE）

**版本：** 0.6（对齐三层情报产品 report_products_v1）  
**阶段：** 日报 v2 实现中；周报/月报规格已冻结、编码后置  
**数据层：** 报告属 [DATA_LAYERS.md](DATA_LAYERS.md) Layer 5；MVP 可落 `data/daily_report_*.md`。仅使用可分析涉华样本；禁止无证据编造。

产品总纲：[REPORT_PRODUCTS.md](REPORT_PRODUCTS.md)  
规格：[DAILY_REPORT_SPEC.md](DAILY_REPORT_SPEC.md) · [WEEKLY_REPORT_SPEC.md](WEEKLY_REPORT_SPEC.md) · [MONTHLY_REPORT_SPEC.md](MONTHLY_REPORT_SPEC.md)

---

## 1. 报告类型

| 类型 | 窗口 | 说明 |
|------|------|------|
| daily | 自然日（报告时区） | **Daily Brief** — 事件主线；`daily_report_schema_v2` |
| weekly | 自然周 | **变化分析** — 规格已冻结，实现后置 |
| monthly | 自然月 | **长期格局** — 规格已冻结；须文章级重算，禁止简单日均 |

---

## 2. 统一元数据（每份报告）

| 字段 | 要求 |
|------|------|
| Reporting Period | `period_start` / `period_end` + timezone |
| Generated At | `generated_at`（UTC） |
| Data Coverage | 覆盖国家、媒体及完整度说明 |
| Article Count | 实际涉华文章数（不得被加权量替换） |
| Unique Story Count | 可得则填 |
| Event Count | 关联/新增事件数 |
| Methodology | metric / taxonomy / weight 版本 |
| Evidence | 原文、链接、证据片段或 ID |
| Confidence | 模型字段置信度适用范围（若有） |
| Limitations | 缺失、语言、判断局限 |

另记：`report_type`、`schema_version`、`country_scope`、`generator`、`sample_size`。

三种时间：`published_at` / `event_time` / `first_seen_at` — 晚发现不得写成当日新发生。

---

## 3. 结论类型

| 类型 | 含义 | 发布规则 |
|------|------|----------|
| Fact | 有原文或可靠结构化数据 | 必须绑定证据 ID |
| Inference | 多证据支持的分析推断 | 明确标记为推断 |
| Hypothesis | 待验证 | 不得写成事实；信号可标 UNCONFIRMED / NEEDS_REVIEW |
| Background | 背景知识 | 不得冒充本次采集证据 |

标准表述须落在「被监测官媒样本」，禁止无证据扩大为国家政策/民意结论。

---

## 4. 证据硬约束

事实性结论必须绑定：

- `article_id` 和/或 `evidence_id`  
- 和/或 `metric_run_id` / `alert_id` / `event_id`  
- `source_id`（尽量）  
- 时间窗口与统计口径  

**无证据 → Validator 拒绝或降级为不确定性说明。**

禁止编造：文章、来源、引用、统计值、数据库 ID。自然语言不得改写统计结果。

---

## 5. Validator 检查清单

- 时间窗口与报告日一致  
- KPI 文章数与库内过滤计数一致（抽检）  
- 事件列表无重复 `event_id`  
- Major Events / Evidence 每条 Fact 有 `article_id` 或 `event_id`  
- 未输出「对华总分 / 综合舆情指数」类字段  
- 叙述中未把样本写成「国家官方立场 / 民意」  
- （若 polish）叙述中的数字均来自 facts  

MVP：同包内确定性函数；独立 Validation Agent 服务化后置。

---

## 6. 与预警的关系

A 类情报预警可进入日报「Emerging Signals」；B 类系统告警进入「Data Coverage / Quality」，不得伪装为舆情结论。完整生命周期见预警文档 / 引擎。

---

## 7. Agent 边界

**MVP：** 模板拼装 + 可选润色 + Validator。  
**后置：** 周/月 Agent、开放式研究。  

Agent 不可：替代采集、替代指标计算、无证据声称重大事件、推断政府真实意图。
