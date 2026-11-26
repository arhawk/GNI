# NEXT_BATCH_PLAN.md — 下一批开发建议（Phase 5–8）

> 前置门禁：本批次（Phase 2–4）已完成并暂停，等待人工审核确认后再启动以下工作。

## 建议批次划分

### Batch 3：Phase 5（Assessment Engine 与统一 Evidence Package）
1. **统一证据包构建器**：将 `src/gni/reports/narrative/evidence.py` 对齐至 `EvidencePackageContract`，直接消费 Phase 4 的 `StatSnapshot`、`SignalRecordContract`（`metrics/changes.py`）、`Event` 与 `NarrativeCluster`（含 `supporting_evidence` 与 `counter_evidence`）。
2. **扩展研判任务覆盖**：在现有 4 类任务（`executive_summary`、`topic_narrative_analysis`、`country_stance_comparison`、`outlook_watchlist`）基础上，复用同一套 Pydantic 校验与缓存机制，增量补齐事件演化、叙事竞争与异常信号专项研判。
3. **三层硬校验强化**：强制校验每条 `Fact`/`Inference`/`Hypothesis`/`Outlook` 的证据引用存在性、数字一致性（与 `StatSnapshot` 零偏差）及反例呈现。

### Batch 4：Phase 6（Reporting Engine 统一与按需重跑）
1. 将 `daily.py` / `weekly.py` / `monthly.py` 逐步统一映射到 `ReportPackageContract` + `ReportSectionContract`，严格分离确定性数据块与 LLM 研判块。
2. 支持单章节失败降级与按需重跑，不影响其他确定性统计板块输出。

### Batch 5：Phase 7–8（API 升级、依赖清理与前端可追溯展示）
1. 解耦 `events/service.py -> gni.dashboard.data`，清零 `test_layer_dependency_direction` 中的最后 1 处白名单。
2. 暴露 `ArticleIntelligenceContract`（含 `expression_owner`、原文证据高亮偏移、`quality_flags`）、`SignalRecordContract` 与 `NarrativeCluster`（正/反例对比）API 端点，并同步更新 React 前端详情抽屉与报告页面。

## 审核前可选的运营前置动作
- 如需立即提升本地库 V1.0+ 立场覆盖率，可在确认预算后运行：
  - `.venv/bin/gni analyze run --reanalyze-legacy --provider deepseek --limit 100`
  - 或离线验证：`.venv/bin/gni analyze run --reanalyze-legacy --provider heuristic --limit 100`
