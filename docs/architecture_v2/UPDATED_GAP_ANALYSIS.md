# UPDATED_GAP_ANALYSIS.md — Batch 1 & 2 完成后的最新差距分析

> 分支：`cursor/data-trust-batch1` | 日期：2026-11-26 | 对比基线：`docs/architecture_v2/GAP_ANALYSIS.md`（Phase 1）

## 1. 本批次已关闭的 P0 / P1 缺口

| 原缺口编号/主题 | 原状态 | 现状态 | 解决方式 |
|---|---|---|---|
| 缺少统一 Pydantic v2 数据契约与版本常量 | `not_implemented` | `implemented` | 新增 `src/gni/core/contracts.py`（7 大契约 + `record_source` 来源区分）与依赖方向静态守护 |
| `china_stance` 缺少 `expression_owner`（媒体与引述未隔离） | `not_implemented` | `implemented` | `deepseek.py` / `heuristic.py` 输出 `expression_owner`，`stance_util.py` 强制拦截 `quoted_actor` |
| 文章级缺少结构化 `narratives[]`、`event_candidates[]`、原文偏移核验与 `Quality` 对象 | `not_implemented` | `implemented` | `validate_and_enrich_article_intelligence()` 实现原文偏移对齐、跨字段校验与 `ArticleQualityContract` |
| 历史旧版 `v0.1`/`v0.2` 文章缺少增量重跑入口 | `not_implemented` | `implemented` | 新增 `gni analyze run --reanalyze-legacy` |
| `alerts/rules.py` 使用旧版立场口径且以 `first_seen_at` 替代 `published_at` | `partially_implemented` | `implemented` | 切换严格 `published_at` + V1.0 `extract_v1_china_stance` |
| 缺少多因素变化检测与小样本误报抑制 | `not_implemented` | `implemented` | 新增 `src/gni/metrics/changes.py`（`SignalRecordContract`） |
| `events/extract.py` 未消费文章级结构化事件候选；缺少 `split_event()` 与防误合并 | `partially_implemented` | `implemented` | 优先消费 `event_candidates[]`、`_is_false_merge_pair()` 护栏、`split_event()` + `EventRevision` |
| `NarrativeCluster` / `EventNarrativeEvidence` 表空置、无跨文章叙事聚合 | `not_implemented` | `implemented` | 新增 `src/gni/events/narratives.py` 写入现有两张表 |

## 2. 仍遗留的缺口（留待下一批次 Phase 5–8 或运营执行）

| 优先级 | 缺口项 | 当前状态 | 归属阶段 | 说明 |
|---|---|---|---|---|
| P0 | 本地数据库历史存量文章（约 84.8%）仍为 `v0.1` 旧版分析结果 | `blocked`（待运营执行） | 运营/数据回填 | 已提供 `--reanalyze-legacy`，需在配置预算后按批执行重跑 |
| P0 | Assessment Engine 9 类研判任务与统一 `EvidencePackageContract` 组装尚未完全重构 | `partially_implemented` | Phase 5 | 现有 `reports/narrative/` 覆盖 4 类基础研判任务，需扩展统一证据包与完整校验护栏 |
| P1 | Reporting Engine 尚未切到统一 `ReportPackageContract` 与 `ReportSectionContract` | `partially_implemented` | Phase 6 | 现有 `daily.py`/`weekly.py`/`monthly.py` 可正常运行，待统一组装与按需重跑章节 |
| P1 | `events/service.py -> gni.dashboard.data` 历史遗留反向导入 | `partially_implemented` | Phase 7（API 清理） | 仅剩 1 处白名单耦合（`overview_payload()`），需迁回 `api/` 或 `dashboard/` 层 |
| P1 | `processing` 层偶发语种误标（如印地语被标为 `en`）与超长 Liveblog 议题串扰 | `partially_implemented` | 后续数据质量优化 | 抽样中已定位根因，待后续独立批次优化 |
| P2 | 前端展示层与 API 尚未全面消费 `article_intelligence`、`SignalRecordContract` 与 `NarrativeCluster` | `not_implemented` | Phase 7–8 | 需在 Phase 5–6 稳定后再升级 API 与 React 前端 |
| P2 | 既有 `tests/unit/test_editorial_focus.py` 2 项历史失败 | `not_implemented` | 独立维护 | 由历史 `sources.yaml` 扩充引起，非本批次引入 |
