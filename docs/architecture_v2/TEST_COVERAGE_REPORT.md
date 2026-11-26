# TEST_COVERAGE_REPORT.md — Batch 1 & 2（Phase 2–4）测试覆盖报告

> 分支：`cursor/data-trust-batch1` | 日期：2026-11-26 | 测试命令：`.venv/bin/pytest tests/unit --ignore=tests/unit/test_editorial_focus.py -q`

## 1. 总体测试结果

- **全量单元测试（排除与本批次无关的既有 `test_editorial_focus.py`）**：**127 passed, 0 failed**（运行时间 3.87s）。
- **本批次新增/增强测试**：共 **21 项新增断言用例**（全部 100% 通过），未删除或弱化任何既有测试。
- **既有无关失败说明**：`tests/unit/test_editorial_focus.py` 中有 2 项历史遗留失败（由更早版本 `configs/sources.yaml` 扩充信源数量引发，与 Batch 1 & 2 无关）。

## 2. 按阶段测试覆盖矩阵

### Phase 2 — 数据契约统一
| 测试文件 | 用例名 | 验证要点 | 结果 |
|---|---|---|---|
| `tests/unit/test_v2_contracts_and_article_intel.py` | `test_v2_logical_contracts_validation_and_defaults` | 7 大 V2.0 逻辑契约、NULL/Unclassified 语义、`Finding`/`OutlookSignal` 扩展 | PASS |
| `tests/unit/test_imports.py` | `test_core_and_interfaces_importable` | 核心契约与接口可导入 | PASS |
| `tests/unit/test_imports.py` | `test_layer_dependency_direction` | AST 静态检查底层禁止反向导入 `reports`/`api`/`dashboard` | PASS |

### Phase 3 — 文章级情报分析（含 9 类边界案例）
| 测试文件 | 用例名 | 验证要点 | 结果 |
|---|---|---|---|
| `tests/unit/test_v2_contracts_and_article_intel.py` | `test_single_article_produces_complete_traceable_intelligence` | 单篇产出完整可追溯 `ArticleIntelligenceContract` + 精确偏移切片还原 | PASS |
| `tests/unit/test_v2_contracts_and_article_intel.py` | `test_quoted_actor_stance_and_hallucinated_quote_validation` | 虚构引句标 `unverified_stance_quote`、`quoted_actor` 不计入媒体立场 | PASS |
| `tests/unit/test_v2_contracts_and_article_intel.py` | `test_deepseek_analyze_parses_v2_narratives_entities_events` | DeepSeek v1.1 JSON 解析 `expression_owner`/`narratives`/`entities`/`event_candidates` | PASS |
| `tests/unit/test_v2_contracts_and_article_intel.py` | `test_reanalyze_legacy_selects_only_pre_v1_articles` | `--reanalyze-legacy` 仅增量重跑旧版存量文章 | PASS |
| `tests/unit/test_article_intelligence_boundaries.py` | `test_case1_non_china_article` ~ `test_case9_contradictory_narratives_preserved_with_evidence_offsets` | 覆盖全部 9 类必需边界案例（不涉华、弱涉华、多议题、混合正负、引述观点、缺失正文、未知事件时间、多事件、矛盾叙事） | 9/9 PASS |

### Phase 4 — 监测与聚合（含 9 类确定性验证）
| 测试文件 | 用例名 | 验证要点 | 结果 |
|---|---|---|---|
| `tests/unit/test_phase4_monitoring_and_aggregation.py` | `test_p4_case1_to_5_metrics_dedup_topics_unclassified_country_source_time_window` | 重复 URL/哈希去重、多议题同板块去重/跨板块重叠、`Unclassified` 分母隔离、国家归属、Source 维度、独立情感统计、`[start, end)` 时间边界 | PASS |
| `tests/unit/test_phase4_monitoring_and_aggregation.py` | `test_p4_historical_trend_helper` | `get_historical_trend()` 历史趋势与 `compute_consecutive_increase()` | PASS |
| `tests/unit/test_phase4_monitoring_and_aggregation.py` | `test_p4_case6_missing_event_time_never_filled_with_published_at` | 结构化事件候选缺失 `event_time` 保持 `None` | PASS |
| `tests/unit/test_phase4_monitoring_and_aggregation.py` | `test_p4_case7_change_detection_suppresses_small_sample_and_detects_real_shifts` | 小样本误报抑制、多信源放量信号、立场迁移、跨国分歧 | PASS |
| `tests/unit/test_phase4_monitoring_and_aggregation.py` | `test_p4_case8_event_false_merge_prevention_and_merge_split_audit` | 防关键词误合并 + `merge_events`/`split_event` 双向 `EventRevision` 审计 | PASS |
| `tests/unit/test_phase4_monitoring_and_aggregation.py` | `test_p4_case9_narrative_aggregation_distinguishes_topic_and_keeps_counter_evidence` | 区分同议题与同叙事、保留 `counter_evidence`、落库 `NarrativeCluster` + `EventNarrativeEvidence` | PASS |

### 回归保护
- `tests/unit/test_metrics_v1_spec.py`（V1.0 统计方法论 10 项核心验收）：全部 PASS。
- `tests/unit/test_report_narrative_layer.py`（日报/周报/月报三层校验、缓存与 API）：全部 PASS。
- `tests/unit/test_analyze_service.py`（分析批处理主链路）：全部 PASS。
