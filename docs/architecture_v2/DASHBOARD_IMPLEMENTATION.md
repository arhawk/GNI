# DASHBOARD_IMPLEMENTATION.md — Global Intelligence Dashboard 实施报告

> 路由：`/` | 前端：[web/src/pages/Overview.tsx](web/src/pages/Overview.tsx) | 后端：[src/gni/api/routers/dashboard.py](src/gni/api/routers/dashboard.py) (`GET /api/dashboard`)

## 1. 六大区块信息架构落地

| 区块 | 展示内容 | 数据来源 | 统计与护栏校验 |
|---|---|---|---|
| **A. Executive Overview** | 今日涉华唯一文章总量（主 KPI）、较昨日 / 7 日均值变化、报道国家数、报道媒体数、Stance Coverage Rate、正中负立场条 | `build_daily_report()` -> `v1_stats.global` | 严格以 `Article Count` 为主 KPI，不展示 `Weighted Volume`；立场覆盖率 < 80% 时自动显示 `PartialDataBanner` |
| **B. Executive Assessment** | Overall Situation、Key Findings（带 `Fact`/`Inference` 徽标与原文证据按钮）、Most Important Changes、Important Watch Items | 日报第 1/6 章 + `ReportNarrativeTask` 缓存 (`overall_situation_assessment` / `outlook_assessment`) | 结论优先于图表；无 LLM 缓存时诚实展示 `rule_only` 提示 |
| **C. Global Attention** | 近 14 日全球涉华报道趋势、国家报道量分布（含 `SampleSizeBadge`）、四大板块分布、十五个固定议题分布 | `trends_payload()` + `v1_stats` (`countries` / `boards` / `topics`) | 显式标注多议题允许重叠、不可相加等于全球总量 |
| **D. Key Developments** | 当日重要事件卡片（事件类型、`event_time`、文章数、涉及国家、媒体数、代表文章一键证据追溯） | `daily.sections.major_events` | `event_time` 缺失显示「时间未知」 |
| **E. Emerging Signals** | 左栏「已观察事实 (Fact)」、右栏「分析推断 (Inference)」分栏展示 | `daily.sections.signals` + 日报第 5 章 `findings` | 严格区分观察事实与推断 |
| **F. Daily Report Entry** | 展示 `report_id`、`generation_status`、`validation_status`，一键跳转 `/reports` | `report_package` 元数据 | 完整闭环入口 |

## 2. 真实数据库验证

在本地 SQLite 数据库运行 `GET /api/dashboard`：返回 `article_count = 27`，与 `GET /api/reports/daily/package` 中的 `coverage.global_article_count = 27` 完全一致。
