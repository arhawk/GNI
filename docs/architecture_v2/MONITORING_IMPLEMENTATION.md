# MONITORING_IMPLEMENTATION.md — Phase 4 监测与聚合实施报告

> 分支：`cursor/data-trust-batch1` | 日期：2026-11-26 | 依据：GNI Architecture & Implementation Specification V2.0（Phase 4）

## 1. 十大监测与聚合能力状态总览

| # | 能力项 | 实现文件 | 状态 | 关键约束落实情况 |
|---|---|---|---|---|
| 1 | Global Metrics | `src/gni/metrics/v1_stats.py`, `service.py` | `implemented` | 按唯一 `article_id` + URL/内容哈希去重统计，严格 `published_at` 窗口 `[start, end)` |
| 2 | Country Metrics | `src/gni/metrics/v1_stats.py` | `implemented` | 严格按 `Source.country_id` 归属 |
| 3 | Source Metrics | `src/gni/metrics/v1_stats.py`, `service.py` | `implemented` | 新增可选 `include_source_scope=True` 输出 `scope_type="SOURCE"` 快照（默认兼容既有测试） |
| 4 | Topic Metrics | `src/gni/metrics/v1_stats.py`, `taxonomy_v1.py` | `implemented` | 四大板块 × 15 议题，同板块/同议题内去重，跨议题允许重叠 |
| 5 | Sentiment Metrics | `src/gni/metrics/v1_stats.py`, `service.py` | `implemented` | 在 `StatSnapshotRow.sentiment_counts` 独立汇总情感分布，不与 Stance 混算 |
| 6 | Stance Metrics | `src/gni/metrics/v1_stats.py`, `analysis/stance_util.py` | `implemented` | `Unclassified` 保留总量、排除出正中负分母；展示 `stance_coverage_rate`；屏蔽历史旧版与 `quoted_actor` |
| 7 | Historical Trends | `src/gni/metrics/service.py` (`get_historical_trend`) | `implemented` | 按 `(scope_type, scope_id)` 返回去重后的按时间升序历史 `StatSnapshot` 序列 |
| 8 | Change Detection | `src/gni/metrics/changes.py`, `src/gni/alerts/rules.py` | `implemented` | 多因素确定性检测（绝对增量、相对变化率、历史基线、最小样本门槛防小样本误报、连续增长期数、国家/信源覆盖度）；`alerts/rules.py` 切 V1.0 严格口径与 `published_at` |
| 9 | Event Aggregation | `src/gni/events/extract.py`, `match.py`, `service.py` | `implemented` | 优先消费 Phase 3 结构化 `event_candidates[]`；`event_time` 未知保持 `None`；`match.py` 增加防关键词误合并护栏；`service.py` 补齐 `split_event()` + `EventRevision` 合并/拆分审计 |
| 10 | Narrative Aggregation | `src/gni/events/narratives.py` | `implemented` | 严格区分「同议题」与「同叙事」（需 `frame` 一致 + `claim` token Jaccard 达标）；区分 `supporting_evidence` 与 `counter_evidence`；落库复用 `NarrativeCluster` + `EventNarrativeEvidence`（0 新增表）；绝不据此推断协调传播 |

## 2. 核心规则与防误判机制

1. **小样本误报抑制（`metrics/changes.py`）**：
   - `detect_volume_change()` 同时校验 `recent_count >= min_sample_size`、`abs_delta >= min_abs_delta`、`rel_change >= min_rel_change` 与 `source_count >= min_sources`。例如 `1 -> 2`（+100%）会被严格拦截并返回 `None`。
   - `detect_stance_shift()` 同时要求 `recent_classified >= min_classified` 与 `stance_coverage_rate >= min_coverage_rate`。
   - `detect_cross_country_divergence()` 要求至少 2 个国家各自达到 `min_per_country` 且负面立场率差值达到 `min_rate_gap`。
2. **事件防误合并与可追溯变更（`events/match.py`, `events/service.py`）**：
   - `_is_false_merge_pair()` 阻止仅因同含 "China" 关键词但主体/动作完全不同的报道被强行合并。
   - `merge_events()` 与新增的 `split_event()` 均在 `EventRevision` 表中双向落盘审计记录。
3. **叙事防误聚类与反例保留（`events/narratives.py`）**：
   - 相同 `topic_id` 下不同 `frame` 或不同 `claim` 保持分簇；同一主张下的 `refute` 或相反倾向陈述自动归入 `counter_evidence`。
