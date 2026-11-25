# 每日情报规格（DAILY_REPORT_SPEC）

**版本：** daily_report_schema_v4（Ops/Risk；预警优先）  
**产品名：** Daily Intelligence Brief（每日情报）  
**核心问题：** 今天有没有高风险？异动在哪？明日跟什么？采集是否异常？  
**阅读时长：** 3–5 分钟  
**对齐：** [REPORT_PRODUCTS.md](REPORT_PRODUCTS.md)、[REPORT_GOVERNANCE.md](REPORT_GOVERNANCE.md)、固定八维中的**日报必出子集**  
**原则：** **规则算数 → 结构化 JSON →（可选）LLM 只写叙述**；预警段在前。

旧版 `daily_report_schema_v2` 读报布局仍可解析字段；默认输出 **v4**。

---

## 1. 日报五段（产品结构）

| # | 章节 | 必须回答 |
|---|------|----------|
| 1 | 当日摘要 | 一句话基调 + **有无突发高风险**（`risk_banner`） |
| 2 | 数据统计 | 有效报道量、采集/排除、各国情感简表、媒体类型桶、情感分技术均值 |
| 3 | 重点事件 | 国｜媒体类型｜叙事｜情感｜**风险**｜**赛道**；异动标红 |
| 4 | 舆情异动 | 事件异动 + 情报信号（基线/量/叙事规则） |
| 5 | 次日跟踪 + 采集 | follow_ups + crawl_status（429/失败/失联） |

固定八维中：关注度无社媒热度；风险/赛道为关键词 taxonomy MVP（[`configs/risk_sectors.yaml`](../configs/risk_sectors.yaml)）。

**禁止：** 合成对华舆情总分当国家态度；把媒体样本写成民意；无 id 的事实句；虚构全球源数；社媒公众兴趣曲线。

---

## 2. JSON 形状（v4 增量）

在 v2 字段之上增加：

```text
schema_version          # daily_report_schema_v4
sections.summary.risk_banner   # { has_high_risk, high_risk_event_count, text }
sections.overview_stats
  connected_countries, media_type_counts(_zh)
  ingest{ day_total, china_effective, excluded..., duplicates, thin_or_stub }
  crawl_summary, sentiment_tech{ score_mean, vs_yesterday_delta, note }
  narrative_split{ official_topics_top, media_topics_top }
  sentiment_by_media_type
sections.major_events[]  += primary_country, source_bucket(_zh), narrative_labels,
  sentiment_label, risk_level, sectors[], anomaly{flagged,reasons}, timeline[]
sections.anomalies[]
sections.ops{ follow_ups[], crawl_status[], note }
```

`sentiment_tech.score_mean` = 文章情感分均值（技术指标），**≠ 舆情总分**。

---

## 3. 可视化

- 风险条、异动标红表、情感三色条、主题横条、媒体量 sparkline  
- **不做**社媒栏 / Left–Right 政治偏见条  

---

## 4. 生成流水线

1. Rule assemble — `build_daily_report()` → v4 facts + risk/sector tag  
2. Validator — 窗口、事件去重、Fact 绑定、禁总分措辞  
3. Optional polish — 仅 narratives  
4. Render — 报告中心五段布局  

---

## 5. 验收

- 1 分钟内能答：有无高风险、各国情感简表、哪几条标红、明日跟什么、爬虫是否异常  
- 事件行可见 risk_level 与 sectors（无则 `unmapped`）  
- 无 API key 仍可完整出报  
