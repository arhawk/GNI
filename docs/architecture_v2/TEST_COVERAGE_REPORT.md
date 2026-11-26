# TEST_COVERAGE_REPORT.md — Batch 1–3（Phase 2–6）测试覆盖报告

> 分支：`cursor/data-trust-batch1` | 日期：2026-11-26 | 测试命令：`.venv/bin/pytest tests/unit --ignore=tests/unit/test_editorial_focus.py -q`

## 1. 总体测试结果

- **全量单元测试（排除与本批次无关的既有 `test_editorial_focus.py`）**：**134 passed, 0 failed**（运行时间 4.48s）。
- **Batch 3（Phase 5–6）新增测试**：共 **7 项核心单元/集成/端到端测试**（100% 通过），未删除或弱化任何既有测试。
- **本地真实数据烟雾测试**：对本地 SQLite 数据库执行 `build_daily_report(analyze=False)` + `ReportPackageContract` 校验 + `render_daily_brief_markdown()`，结果 `validation_status="passed"`（27 篇涉华去重文章，7 个章节完整输出）。
- **既有无关失败说明**：`tests/unit/test_editorial_focus.py` 中 2 项历史遗留失败（由早期 `configs/sources.yaml` 扩充引发），与 Batch 1–3 无关。

## 2. Batch 3（Phase 5–6）新增测试矩阵

| 测试文件 | 用例名 | 覆盖范围与边界 | 结果 |
|---|---|---|---|
| `tests/unit/test_phase5_assessment_engine.py` | `test_evidence_package_traceability_and_no_raw_fulltext_dump` | 任务级 `EvidencePackageContract`、`article_id`/`evidence_id`/`article_version_id`/`published_at`/`source_name` 追溯、`quoted_actor` 计数、`NarrativeCluster` 接入、禁止全文倾倒 | PASS |
| `tests/unit/test_phase5_assessment_engine.py` | `test_all_9_canonical_assessment_tasks_run_through_unified_framework` | 全部 9 类规范研判任务经统一框架执行、Fact/Inference/Hypothesis 三分、`ReportNarrativeTask` 缓存命中、主观置信度声明 | PASS |
| `tests/unit/test_phase5_assessment_engine.py` | `test_assessment_validator_catches_coordinated_propagation_and_volume_as_risk` | 三层校验拦截「协调传播过度推断」「负面量=现实风险」「未授权数字 99.9%」「无证据 Fact 自动降级」 | PASS |
| `tests/unit/test_phase5_assessment_engine.py` | `test_assessment_handles_zero_data_and_llm_timeout_gracefully` | 零数据窗口短路 `insufficient_data`（0 LLM 调用）；LLM 超时降级 `failed` 并保留确定性证据引用 | PASS |
| `tests/unit/test_phase6_daily_report_package.py` | `test_daily_brief_e2e_six_chapters_snapshot_and_markdown` | 端到端闭环（监测数据 → 证据包 → 研判任务 → 6 章+附录 `ReportPackageContract` → `validate_report_package` → Markdown → `ReportSnapshot` 保存/查询/重生成） | PASS |
| `tests/unit/test_phase6_daily_report_package.py` | `test_daily_brief_zero_data_edge_case` | 零数据日报产出完整 7 章节结构且标记 `generation_status="insufficient_data"` | PASS |
| `tests/unit/test_phase6_daily_report_package.py` | `test_api_daily_report_and_v2_analyze_compatibility` | FastAPI `GET /api/reports/daily` 兼容性 + `POST /api/reports/daily/analyze`（`engine="v2"`, `save_snapshot=True`）无 Key 优雅降级并落库 `ReportSnapshot` | PASS |

## 3. Batch 1–2 与历史回归保护

- `tests/unit/test_v2_contracts_and_article_intel.py`（5 项）：PASS
- `tests/unit/test_article_intelligence_boundaries.py`（9 类文章边界）：PASS
- `tests/unit/test_phase4_monitoring_and_aggregation.py`（9 类监测/聚合边界）：PASS
- `tests/unit/test_metrics_v1_spec.py`（V1.0 统计方法论 10 项核心验收）：PASS
- `tests/unit/test_report_narrative_layer.py`（既有日报/周报/月报叙事层与 API）：PASS
- `tests/unit/test_imports.py`（模块导入与底层依赖方向静态守护）：PASS
