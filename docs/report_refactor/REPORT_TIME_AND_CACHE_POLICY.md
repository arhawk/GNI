# GNI 报告时间窗口与缓存策略规范（Task 3）

## 1. 统一时间窗口解析（`src/gni/reports/window.py`）

所有三类报告统一以 `Asia/Shanghai` 为业务日历时区，采用**左闭右开 `[start, end)`** 边界，彻底消除跨天/月末/年末/闰年重复计入或漏计问题：

| 报告类型 | `window_mode` | 当前窗口 `[start, end)` | 对比基期 `[effective_prev_start, effective_prev_end)` | 特殊规则 |
|---|---|---|---|---|
| **Daily** | `calendar_day` | `[D 00:00, D+1 00:00)` | `[D-1 00:00, D 00:00)` | 严格 1 自然日 |
| **Weekly** | `rolling_7d` | `[D-6 00:00, D+1 00:00)` | `[D-13 00:00, D-6 00:00)` | 显式标注滚动 7 天，前后等长同边界 |
| **Monthly（完整月）** | `calendar_month` | `[M-01 00:00, M+1-01 00:00)` | `[M-1-01 00:00, M-01 00:00)` | 自动处理 28/29（闰年）/30/31 天 |
| **Monthly（月中生成）** | `calendar_month` | `[M-01 00:00, M+1-01 00:00)` | `[M-1-01 00:00, M-1-01 + elapsed_days)` | 自动标记 `is_partial_period=True`，采用**同天数 MTD 公平环比**，禁止不完整当月直接减完整上月 |
| **Monthly（滚动 30 天）** | `rolling_30d` | `[D-29 00:00, D+1 00:00)` | `[D-59 00:00, D-29 00:00)` | 显式标注滚动 30 天，前后等长 30 天 |

### 文章时间与事件时间分离红线
- **文章聚合**：严格使用 `Article.published_at`。
- **事件时间线**：严格使用 `Event.event_time`；若事件发生时间不明确，保持 `NULL`，**严禁**以 `published_at` 替代或伪造。

---

## 2. 完整缓存身份与失效规则

`ReportNarrativeTask` 缓存命中必须同时满足以下全部维度，任一变更即自动失效并记录 `cache_invalidation_reason`：

1. `report_type`（`daily` / `weekly` / `monthly`）
2. `period`（对应窗口唯一周期键）
3. `task_type`（Canonical 9 项任务之一）
4. `prompt_version`（含 `report_type` 命名空间，如 `weekly:assess_event_v2.0`）
5. `evidence_hash`（证据集内容指纹）
6. `requested_model` / `model_version`（切换 LLM 模型自动失效）
7. `schema_version`（`assessment_result_v2.0`）
8. `methodology_version`（`methodology_v1.0`）与 `taxonomy_version`（`taxonomy_v1.0`）

### 失败任务保护
- `status="failed"` 的任务**绝不**被当作有效缓存命中，下次运行或局部重试自动重新执行。
- 数据库迁移策略：治理元数据存储在 `validated_output` JSON 载荷与现有 `ReportNarrativeTask` 列中，**零破坏性 Schema 变更**，天然向后兼容与可回滚。

---

## 3. 验证记录

- `tests/unit/test_report_window_cache_gate.py` 覆盖：闰年 `2024-02`（29 天）、跨年周报 `2025-12-28_2026-01-03`、左闭右开边界、月中 MTD 公平环比（剔除上月后半月文章）、模型版本切换自动失效缓存。
- 结果：**18/18 通过**。
