# 每日情报规格（DAILY_REPORT_SPEC）

**版本：** daily_report_schema_v4（**全局涉华态势 Global Situation + 情报研判 Intelligence Judgment** + `methodology_v1.0` + `narrative/` LLM 3 任务）  
**统计口径：** 严格遵循 [STATISTICAL_METHODOLOGY_V1.md](STATISTICAL_METHODOLOGY_V1.md)（按 `published_at` 入窗、唯一 `Article Count`、信源国归属、`sections.v1_stats` 输出四层级 `GLOBAL/COUNTRY/BOARD/TOPIC` 与对华立场三分类 + 覆盖率）。  
**产品名：** Daily Intelligence Brief（每日情报）  
**核心问题：** 今日全球涉华整体态势如何？有哪些重点事件与关键变化？明日需要关注什么？  
**阅读时长：** 3–5 分钟  
**对齐：** [REPORT_PRODUCTS.md](REPORT_PRODUCTS.md)、[REPORT_GOVERNANCE.md](REPORT_GOVERNANCE.md)  
**原则：** **规则确定性统计 → EvidenceBundle → LLM 结构化分析（`executive_analysis` / `event_analysis` / `emerging_signals`）→ 3-Layer Validator → 报告中心以分析结论居中展示**；`china_signal_score` 仅用于规则排序参考，不作为真实战略风险评分。

本地开发：**必须重启** `gni api serve` 才能加载本 schema；`/health` 暴露 `daily_schema`，日报响应带 `X-GNI-Report-Schema`。UI 若收到非 v4 或缺 `overview_stats` / `risk_banner`，**整页错误态**，禁止空五段。

---

## 1. 日报五段（产品结构）

| # | 章节 | 必须回答 |
|---|------|----------|
| 1 | 当日摘要 | **研判句** `judgment_text` + `confidence` + **有无突发高风险**（`risk_banner`） |
| 2 | 数据统计 | 有效报道量、采集/排除、各国情感简表（n 门禁）、媒体类型桶、情感分技术均值 |
| 3 | 重点事件 | 按 `china_signal_score` 排序；国｜媒体｜叙事｜情感｜**风险**｜**赛道**；次要折叠；孤儿敏感标题 |
| 4 | 舆情异动 | 高风险事件 + 孤儿标题 + 情报/合成信号 |
| 5 | 次日跟踪 + 采集 | follow_ups（强制 1–3 条风险跟踪）+ crawl_status |

固定八维中：关注度无社媒热度；风险/赛道为关键词 taxonomy MVP（[`configs/risk_sectors.yaml`](../configs/risk_sectors.yaml)）。

**禁止：** 合成对华舆情总分当国家态度；把媒体样本写成民意；无 id 的事实句；虚构全球源数；社媒公众兴趣曲线；n&lt;3 写「以负面为主」。

---

## 2. JSON 形状（v4 增量）

```text
schema_version          # daily_report_schema_v4
sections.summary
  risk_banner   # { has_high_risk, high_risk_event_count, text }
  judgment_text # 规则拼装研判句（主议题 / 高风险·赛道 / 分国门禁 / 积压）
  confidence    # high | medium | low | unavailable
  overview_text # 含 judgment + 运维量级补充
sections.overview_stats
  connected_countries, media_type_counts(_zh)
  ingest{ day_total, china_effective, excluded..., duplicates, thin_or_stub }
  crawl_summary, sentiment_tech{ score_mean, vs_yesterday_delta, note }
  narrative_split{ official_topics_top, media_topics_top }
  sentiment_by_media_type
sections.major_events[]  += china_signal_score, list_tier=primary,
  primary_country, source_bucket(_zh), narrative_labels,
  sentiment_label, risk_level, sectors[], anomaly{flagged,reasons}, timeline[]
sections.secondary_events[]   # 弱对华相关，折叠
sections.orphan_headlines[]   # 高权重涉华文但未进指纹事件、且命中风险/赛道
sections.anomalies[]
sections.signals[]            # 告警 + 合成 policy_risk|sector_watch（needs_review）
sections.ops{ follow_ups[], crawl_status[], note }
sections.tone.by_country[] += status  # ok | unavailable | no_sample；min_n 默认 3
sections.coverage.taxonomy_confidence  # normal | low（>60% 同桶）
```

### 2.1 `china_signal_score`（可解释加权）

- 风险档：high +5 / medium +3 / watch +1.5  
- 已映射赛道：每赛道 +2（封顶 +4）  
- `anomaly.flagged` +2；证据 `china_relevance_weight` 均值 ×3（封顶 +3）；importance ×2（封顶 +2）  
- **弱相关惩罚**：标题/证据无 China/中国/Beijing 等且无风险/赛道命中 → ×0.25  

排序：`china_signal_score` → `risk_level` → `importance_score`。

### 2.2 情感门禁

- `n < 3` → `status=unavailable`，摘要写「样本不足不可外推」，UI 显示「样本不足」  
- 全库分析积压**不再**强制 `confidence=unavailable`（可附软提示）；当日研判以事件/孤儿/分国门禁为准

`sentiment_tech.score_mean` = 文章情感分均值（技术指标），**≠ 舆情总分**。

---

## 3. 可视化

- 风险条、异动标红表、情感三色条、主题横条、媒体量 sparkline  
- 次要事件折叠、孤儿敏感标题列表  
- **不做**社媒栏 / Left–Right 政治偏见条  

---

## 4. 生成流水线

1. Rule assemble — `build_daily_report()` → v4 facts + risk/sector tag + china_signal_score  
2. Validator — 窗口、事件去重、Fact 绑定、禁总分措辞  
3. Optional polish — 仅 narratives（不改 facts / judgment 门禁）  
4. Render — 报告中心五段布局；非 v4 硬失败  

---

## 5. 验收

- `/health.daily_schema` = `daily_report_schema_v4`；响应头 `X-GNI-Report-Schema`  
- 1 分钟内能答：有无高风险、研判句、各国情感是否可用、哪几条标红、明日跟什么、爬虫是否异常  
- 制裁 / 黑名单 / 安全协议 / 芯片流入类标题能打出 high + 半导体等（有语料时压过弱 AI 合作）  
- US n=1 → unavailable；有素材时 anomalies / follow_ups / signals 非空  
- 无 API key 仍可完整出报  
