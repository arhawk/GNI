# 报告任务配置参考（Report Task Profile Reference）

> 源码位置：`src/gni/reports/orchestrator.py`（`REPORT_TASK_PROFILES`、`resolve_profile_tasks`）

| 报告类型 | Profile Version | Core 必选任务 | Optional 可选任务 | 执行依赖顺序 |
|---|---|---|---|---|
| `daily` | `daily_profile_v1.0` | `event_analysis`, `change_detection_assessment`, `overall_situation_assessment`, `risk_signal_assessment`, `outlook_assessment`（5） | `topic_analysis`, `country_comparison`, `narrative_analysis`, `sentiment_stance_analysis`（4） | 先 6 个维度分析任务，再 3 个综合/风险/展望任务 |
| `weekly` | `weekly_profile_v1.0` | 上述 5 核心 + `topic_analysis`, `country_comparison`, `sentiment_stance_analysis`（8） | `narrative_analysis`（1） | 同上 |
| `monthly` | `monthly_profile_v1.0` | 全部 9 类 Canonical 任务（9） | 无 | 同上 |

通过 `resolve_profile_tasks(report_type, profile="core"|"full", requested_tasks=...)` 同时支持 Canonical 与 Legacy 任务名（自动映射）。
