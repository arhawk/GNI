# 统一研判结果契约（Assessment Schema）

> 源码位置：`src/gni/core/contracts.py`（`AssessmentResultContract`）

## 核心字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `task_type` | `str` | Canonical 9 任务标识之一 |
| `task_version` | `str` | 任务/提示词版本（默认 `v2.0`，运行时填入 `effective_prompt_version`） |
| `report_type` | `str \| None` | `daily \| weekly \| monthly` |
| `period` | `str \| None` | 报告周期标识 |
| `evidence_hash` | `str \| None` | 本次运行共享 `EvidenceBundle` 指纹 |
| `executive_summary` | `str` | 执行摘要 |
| `key_findings` | `list[dict]` | 结构化关键发现 |
| `observations` / `interpretations` / `hypotheses` | `list[dict]` | 严格分离 Fact / Inference / Hypothesis |
| `evidence_refs` / `supporting_metrics` / `counter_evidence` | `list` | 证据引用、确定性指标引用与反证 |
| `confidence` / `limitations` / `watch_items` | `str / list` | 置信度、样本局限与观察项 |
| `details` | `dict` | 任务专属结构（事件七维解读、跨国对比、议题深潜等） |
| `status` | `Literal` | `completed \| needs_review \| insufficient_data \| degraded \| failed` |
| `validation_result` | `dict` | 三层校验器报告 |
| `generated_at` / `model_version` / `prompt_version` / `schema_version` / `methodology_version` / `taxonomy_version` | `str \| None` | 全链路可追溯治理字段 |

所有新增字段均带安全默认值且 `extra="ignore"`，完全向后兼容历史缓存记录。
