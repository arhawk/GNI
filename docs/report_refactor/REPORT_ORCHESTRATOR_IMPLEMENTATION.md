# 统一报告编排器实现说明（Report Orchestrator Implementation）

## 1. 核心模块与职责

- **`src/gni/reports/orchestrator.py`**：
  - `ReportTaskProfile` 与 `REPORT_TASK_PROFILES`：显式定义 `daily`、`weekly`、`monthly` 三类报告的核心任务、可选任务与依赖执行顺序（先执行事实/维度分析任务，再执行综合与展望任务）。
  - `ReportOrchestrator.run()`：单次构建共享 `EvidenceBundle`（`prepare_evidence_bundle`），先载入已有缓存结果以保护局部重试场景下未变更任务，再按序调用 `run_assessment_task()`，最后通过 `project_canonical_to_legacy_intelligence()` 生成向后兼容的 `payload["intelligence"]`。
  - `ReportOrchestrator.load_cached_intelligence()`：快读缓存路径（不触发外部 LLM），优先读取 Canonical 缓存，无 Canonical 缓存时平滑回退到 Legacy `load_cached_intelligence()`。
- **`src/gni/reports/narrative/assessment.py`**：
  - `effective_prompt_version(spec, report_type)`：按报告类型区分 `prompt_version`（Daily 保留 `assess_*_v2.0`，Weekly 为 `weekly:assess_*_v2.0`，Monthly 为 `monthly:assess_*_v2.0`），彻底消除与 Legacy `event_analysis` 的缓存键冲突。
  - `_REPORT_CONTEXT_PREFIX`：将 Daily/Weekly/Monthly 周期定位指令动态注入系统提示词，复用同一套 9 任务执行引擎。
- **报告与路由接入**：
  - `src/gni/reports/weekly.py`、`src/gni/reports/monthly.py` 新增 `use_orchestrator` 与 `orchestrator_profile` 参数，缓存读取统一走 `ReportOrchestrator.load_cached_intelligence()`。
  - `src/gni/api/routers/reports.py` 的 `POST /api/reports/{report_type}/analyze` 对 Daily/Weekly/Monthly 统一支持 `engine="v2"|"canonical"|"orchestrator"`。

## 2. 测试验证

- `tests/unit/test_report_orchestrator.py` + 全部原有报告单测：**14 passed**（0 failed）。
