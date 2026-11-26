# GNI 报告三态质量门禁规范（Task 3）

## 1. 门禁实现（`src/gni/reports/quality_gate.py`）

`evaluate_report_quality_gate(payload)` 已接入 Daily / Weekly / Monthly 全部三类报告生成链路，输出统一的 `quality_gate` 区块：

```json
{
  "gate_version": "report_quality_gate_v1.0",
  "status": "passed | passed_with_warnings | blocked",
  "blocking_issues": [],
  "warnings": [],
  "metrics": {
    "article_count": 42,
    "stance_coverage_rate": 0.8571,
    "is_partial_period": false
  },
  "checked_at": "..."
}
```

## 2. 阻断项（`blocked`）vs 警告项（`passed_with_warnings`）

| 级别 | 检查编码 | 触发条件 |
|---|---|---|
| **阻断 (`blocking_issues`)** | `missing_required_field` | 缺少 `report_type` / `period` / `period_start` / `period_end` / `schema_version` |
| **阻断 (`blocking_issues`)** | `invalid_window_bounds` | `period_start >= period_end` |
| **阻断 (`blocking_issues`)** | `stance_count_mismatch` | `positive + neutral + negative + unclassified != article_count` |
| **阻断 (`blocking_issues`)** | `unclassified_leaked_into_denominator` | `positive_rate` / `neutral_rate` / `negative_rate` 错误地把 `unclassified` 纳入分母（误差 > `0.005`） |
| **阻断 (`blocking_issues`)** | `event_time_fabricated` | 事件时间线显式标记使用 `published_at` 伪造 `event_time` |
| **警告 (`warnings`)** | `zero_articles_in_window` | 窗口内涉华文章数为 0 |
| **警告 (`warnings`)** | `low_sample_size` | 涉华文章数 `< 5` |
| **警告 (`warnings`)** | `low_stance_coverage` | `stance_coverage_rate < 0.5` |
| **警告 (`warnings`)** | `partial_period_mtd` | 月中未完整自然月（已自动切换 MTD 公平环比） |
| **警告 (`warnings`)** | `intelligence_partial_or_failed` | 存在失败或待复核的研判任务 |
| **警告 (`warnings`)** | `legacy_validation_warning` | 传统报告校验器返回警告 |

## 3. 前端与 API 契约

- `/api/reports/{daily|weekly|monthly}` 均返回顶层 `quality_gate` 与 `window_spec`。
- 前端须对 `passed_with_warnings` 展示明确提示条，对 `blocked` 展示阻断警示，不得静默吞掉异常。
