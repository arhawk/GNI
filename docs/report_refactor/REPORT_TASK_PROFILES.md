# 报告任务配置矩阵（Report Task Profiles）

> 设计原则：日报重“今日发生了什么与即时异动”、周报重“本周相对上周的变化与跨国差异”、月报重“长期格局、持续性与结构演进”。按需启用 Canonical 9 任务，避免无关任务增加延迟与 Token 成本。

## 1. 三类报告的任务配置表

| Canonical Task Type | Daily（每日情报） | Weekly（每周分析） | Monthly（每月研判） | 周期差异化侧重点 |
|---|---|---|---|---|
| `overall_situation_assessment` | **必需** | **必需** | **必需** | Daily=当日态势与核心驱动；Weekly=本周 vs 上周总评；Monthly=月度战略格局与结构变化 |
| `change_detection_assessment` | **必需** | **必需** | 可选（默认开启） | Daily=较昨日/7日均异动；Weekly=环比增减与小样本甄别；Monthly=跨月结构偏离 |
| `event_analysis` | **必需**（Top 5） | **必需**（Top 6） | **必需**（Top 8） | Daily=当日进展；Weekly=一周演化与各国跟进时序；Monthly=阶段性回顾与延续影响 |
| `topic_analysis` | 可选（文章数 >= 15 时启用） | **必需** | **必需** | Weekly=Attention/Stance/Structure 三分；Monthly=3-6 月持续性（`ongoing`/`short_term`/`insufficient_history`） |
| `country_comparison` | 可选（活跃国家 >= 3 时启用） | **必需** | **必需** | Weekly=同事件跨国叙事差异；Monthly=国别媒体长期画像与样本局限 |
| `narrative_analysis` | 可选（narratives 非空时启用） | 可选（默认开启） | **必需** | Weekly=新兴/分化叙事；Monthly=主导/新兴/衰退叙事格局（严禁推断协调传播） |
| `sentiment_stance_analysis` | 可选（立场覆盖率 > 0 时启用） | **必需** | **必需** | 必须区分比例变化与绝对篇数变化，强制披露 `stance_coverage_rate` 与 `unclassified_count` |
| `risk_signal_assessment` | **必需** | **必需** | 可选（默认开启） | Daily=当日预警归因；Weekly=跨国扩散与持续性异常；Monthly=中长期结构风险 |
| `outlook_assessment` | **必需** | **必需** | **必需** | Daily=明日监测清单；Weekly=下周监测重点；Monthly=下月条件性展望（触发条件+不确定性） |

## 2. 默认执行成本估算（DeepSeek）

- **Daily 默认必选 5 任务**（全量时最多 9 任务）：兼顾时效与深度；零数据日自动短路为 0 次 LLM 调用。
- **Weekly 默认 8–9 任务**：覆盖变化解释、事件演化、议题趋势、跨国比较、立场变化与下周展望。
- **Monthly 默认 9 任务**：完整覆盖长期格局、叙事演化与战略展望。

## 3. 触发策略

- `GET /api/reports/{daily|weekly|monthly}`：**严禁**触发外部 LLM，仅返回确定性统计 + 已缓存的研判结果（无缓存时返回 `status="rule_only"`）。
- `POST /api/reports/{daily|weekly|monthly}/analyze`：
  - 支持 `profile="core" | "full"`（或显式传入 `tasks=[...]` 指定子集）。
  - 支持 `force=true` 强制刷新与失败任务局部重试（`tasks=[failed_ids]`）。
