# DATA_TRACEABILITY_REPORT.md — 前后端数据一致性与证据追溯验收报告

> 分支：`cursor/data-trust-batch1` | 日期：2026-11-26 | 自动化校验：[tests/unit/test_phase7_api_integration.py](tests/unit/test_phase7_api_integration.py)

## 1. 十项前后端数据一致性核验矩阵

| # | 一致性规则 | 验证方式 | 结果 |
|---|---|---|---|
| 1 | Dashboard `Article Count` == 后端确定性 `Metric Snapshot` (`v1_stats.global`) | 单测断言 (`3 == 3`) + 真实库烟雾 (`27 == 27`) | PASS |
| 2 | 国家报道量之和在适用口径下与全球总量一致（按 `source_country`） | 单测断言 (`US 1 + DE 2 == 3`) | PASS |
| 3 | 议题报道量允许重叠，不强求总和等于全球唯一文章总量 | 单测验证多议题文章 `tariffs_trade_war(2) + semiconductors_export_controls(1) = 3` 于 2 篇已标注文章，且 UI 显式提示 | PASS |
| 4 | Stance 正中负比例分母不包含 `Unclassified` | 单测验证 1 Pos + 1 Neg + 1 Unclassified -> `Positive=0.5, Negative=0.5` | PASS |
| 5 | `Stance Coverage Rate` 使用 `classified_count / article_count` | 单测验证 `2 / 3 = 66.7%` | PASS |
| 6 | Sentiment 与 Stance 分开读取与展示（且区分 `media` vs `quoted_actor`） | `/api/sentiment-stance` 与 `SentimentStance.tsx` 分栏独立渲染 | PASS |
| 7 | Event Timeline 严格使用 `event_time`（未知不以 `published_at` 替代） | 单测断言 `event_time=None -> time_status="unknown"`，`coverage_timeline` 另列 `published_at` | PASS |
| 8 | 文章列表严格按 `published_at` 过滤与倒序排序 | 单测验证 `a2 (now-1h)` 排在 `a1 (now-2h)` 前 | PASS |
| 9 | 研判结果引用的 Evidence ID 可真实定位原文偏移片段 | `GET /api/evidence/{evidence_id}` 单测验证 `content_excerpt[start_offset:end_offset] == text_span` + 全局 `EvidenceDrawer` 高亮 | PASS |
| 10 | Report Package 展示内容与后端保存的 `ReportSnapshot` 一致 | `POST /api/reports/daily/analyze` (`save_snapshot=true`) -> `GET /api/reports/daily/package?from_snapshot=true` 断言一致 | PASS |

## 2. 真实数据状态透明披露

- 真实本地 SQLite 库中不存在任何虚构或 Mock 数据填充：例如 `GET /api/narratives` 在当前库返回 `0`（因历史存量尚未执行叙事聚簇），前端明确展示 `EmptyState` 与原因说明；`stance_coverage_rate < 80%` 时明确展示 `PartialDataBanner`。
