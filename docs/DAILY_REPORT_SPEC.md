# 每日情报规格（DAILY_REPORT_SPEC）

**版本：** daily_report_schema_v2  
**产品名：** Daily Intelligence Brief（每日情报）  
**核心问题：** 今天发生了什么？哪些事情值得关注？  
**阅读时长：** 3–5 分钟  
**对齐：** [REPORT_PRODUCTS.md](REPORT_PRODUCTS.md)、[REPORT_GOVERNANCE.md](REPORT_GOVERNANCE.md)、[EVENT_FINGERPRINT.md](EVENT_FINGERPRINT.md)  
**原则：** **规则算数 → 结构化 JSON →（可选）LLM 只写叙述**；读报正文在前，计数表为明细。

旧版 `daily_report_schema_v1`（七段表格式）废止为默认；API 可保留兼容，默认输出 v2。

---

## 1. 固定目录

| # | 章节 | 重要性 | 必须回答 |
|---|------|--------|----------|
| 1 | Executive Summary | 必须 | 今日总体情况、KPI、今日值得关注的最多 3 个变化 |
| 2 | Major Events | 必须 | 按**重要性**排序的事件卡（非按篇数） |
| 3 | Global Coverage | 必须 | 哪些国家/媒体最关注中国；Article Count 与 Weighted Volume **并列** |
| 4 | Sentiment & Stance | 必须 | 当日情感/立场分布与分国差异（分列） |
| 5 | Emerging Signals & Alerts | 必须 | 值得注意但未成大事的信号；可标 UNCONFIRMED / NEEDS_REVIEW |
| 6 | Source & Data Coverage Notes | 建议 | 缺口、积压、无样本国、口径 |

**禁止：** 合成对华舆情总分；把媒体样本写成国家立场/民意；无 `article_id`/`event_id` 的事实句；用加权量替代实际篇数。

---

## 2. JSON 形状（`daily_report_schema_v2`）

```text
schema_version          # daily_report_schema_v2
report_type             # daily
period / period_start / period_end / timezone
generated_at
disclaimer
country_scope
generator               # rule | rule+llm
validation              # { ok, checks[], errors[] }

sections.summary
  kpis                  # china_articles, reporting_countries, reporting_sources,
                        # new_events, major_events, day_articles
  comparisons           # vs_yesterday, vs_7d_avg (china_articles / new_events …)
  top_changes[]         # { title, summary, kind, href?, evidence{} } 最多 3
  overview_text         # 规则或 LLM 润色后的今日概述（叙述）

sections.major_events[]
  event_id, title, importance_score, event_type?, event_time, first_seen_at
  status?, overview_text
  core                  # actor, action, object, target, status（可得则填）
  coverage              # article_count, country_count, source_count, countries[]
  by_country_views[]    # { country_id, article_count, dominant_sentiment?, dominant_stance?, frame? }
  follow_ups[]          # 后续关注问题（规则模板或 LLM）
  evidence[]            # article_id, title, url, country_id, source_id, sentiment, stance, published_at

sections.coverage
  by_country[]          # country_id, article_count, weighted_volume?, source_count
  by_source[]           # source_id, name, country_id, article_count
  topics_top[] / frames_top[]
  note

sections.tone
  overall_sentiment_counts / overall_stance_counts
  by_country[]          # country_id, n, sentiment_counts, stance_counts, summary_text
  note                  # 情感≠立场；引述≠媒体自身

sections.signals[]
  id, subcategory, severity, title, summary, status  # confirmed|needs_review|unconfirmed
  href, evidence{}

sections.quality
  missing_analysis, countries_without_sample, source_health_summary, notes[]

narratives              # 可选 LLM：executive, coverage, tone, signals, quality
```

---

## 3. 各节规则与 LLM 边界

### 3.1 Executive Summary

- **Facts：** KPI + vs 昨日 / vs 近 7 日日均；`top_changes` 来自量异常、跨国议题、A 类预警。  
- **规则叙述：** 固定模板拼「涉华 N 篇、M 国、K 源、新增事件…」。  
- **LLM：** 可写 `overview_text` / `narratives.executive`（≤120 字），不得发明数字。

### 3.2 Major Events

- 排序：`importance_score` 降序，其次多源/跨国。  
- 每卡必须含：发生了什么、覆盖量、分国视角摘要、证据链接。  
- 区分 `event_time` 与 `first_seen_at`。  
- **LLM：** 可写 `overview_text`、`follow_ups`；不得改 coverage 数字。

### 3.3 Global Coverage

- 国家排行、媒体排行；Topic/Frame Top。  
- Article Count 与 Weighted Article Volume 分开展示。  
- UI：白话一句 + 可展开明细表。

### 3.4 Sentiment & Stance

- 总体 + 分国；每国一条 `summary_text`（规则：主导情感/立场标签 + n）。  
- 情感描述语气；立场绑定 Target；引述观点不得当成媒体立场。

### 3.5 Signals

- 复用警报引擎 A 类（情报）当日相关；系统 B 类进 quality，不混进舆情信号主栏。  
- 允许 `needs_review` / `unconfirmed`。

### 3.6 Quality

- 积压、源健康、无样本国；与舆情结论分区。

---

## 4. UI（报告中心 · 日报）

1. 顶栏：DAILY BRIEF · 日期 · 口径 callout  
2. KPI 四格 +「今日三变化」列表（可点跳转）  
3. 重大事件卡（主阅读区）  
4. 全球覆盖（总结 + 明细）  
5. 情感与立场（分国白话 + 可展开表）  
6. 新兴信号  
7. 数据说明  

周报 / 月报 Tab：占位，链到规格文档摘要。

点击约定见 [REPORT_PRODUCTS.md](REPORT_PRODUCTS.md) §3。

可视化风格参考：[assets/report-ui/daily-visual-ref.jpg](assets/report-ui/daily-visual-ref.jpg)（不做无社媒「公众兴趣」曲线）。

---

## 5. 生成流水线

1. Rule assemble — `build_daily_report()` 填满 v2 facts。  
2. Rule narratives — 分国/事件短段。  
3. Validator — 窗口、事件去重、Fact 绑定、禁总分措辞抽检。  
4. Optional polish — LLM 只改 narratives / overview 字符串。  
5. Render — 报告中心按读报布局渲染。

---

## 6. 验收

- 几分钟内能读懂今日最重要的事（事件卡为主）。  
- 情感与立场有中文总结，不只是 JSON 表。  
- 证据可点；无 API key 仍可完整出报。  
- JSON 含齐 v2 六节键；`validation.ok` 为 true 或显式 errors。
