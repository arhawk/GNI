# 报告时间窗口与缓存机制审计（Time Window & Cache Audit）

> 依据：`src/gni/reports/daily.py`、`src/gni/reports/weekly.py`、`src/gni/reports/monthly.py`、`src/gni/infrastructure/models.py`、`src/gni/reports/narrative/runner.py`、`src/gni/reports/narrative/assessment.py`

## 1. 三类报告时间窗口现状审计

| 报告类型 | 实现位置 | 时区 | 边界规则 | 实际周期语义 | 发现的问题与风险 |
|---|---|---|---|---|---|
| **Daily** | `daily.py:shanghai_day_window` | `GNI_REPORT_TIMEZONE`（默认 `Asia/Shanghai`） | 左闭右开 `[D 00:00, D+1 00:00)` | 自然日；若 `day=None` 且当日涉华文章为 0，最多向前回溯 7 天（`daily.py:348-354`） | 显式传入 `date=D` 时不回溯，行为清晰；`day=None` 自动回溯时需在界面清晰提示实际返回的 `period`。 |
| **Weekly** | `weekly.py:_week_window` (L49-63) | `Asia/Shanghai` | 左闭右开 `[end-6d 00:00, end+1d 00:00)` | **滚动 7 个自然日**（`end-6d` 至 `end`），环比前一个滚动 7 日 | 当前为滚动 7 日而非 ISO 自然周（周一～周日）；与前端日历点击任意日期 `D` 联动自然契合，但需在元数据中显式标注 `window_mode="rolling_7d"`，避免读者误解为自然周。 |
| **Monthly** | `monthly.py:_month_window` (L49-83) | `Asia/Shanghai` | 1) `end_day` 模式：`[end-29d 00:00, end+1d 00:00)`<br>2) `month=YYYY-MM` 模式：`[1日 00:00, 月末+1日 00:00)` | 同时支持滚动 30 天（前端日历使用）与自然月（API `month=` 使用） | **高风险（自然月月中对比失真）**：若在月中（如 11 月 15 日）请求 `month=2026-11`，当前月仅有 15 天数据，却直接与上月完整 31 天（10 月）计算 `delta`，导致环比严重偏低；且 `historical_v1_stats` 中未将当月标记为 `is_partial=True`，容易被误读为完整月份暴跌。 |

### 1.1 时间字段口径核查
- 文章归入窗口均使用 `Article.published_at`（经 `_in_window` / `_in_range` 转换为 `Asia/Shanghai`），符合既定口径；未将 `first_seen_at` 用于核心舆情统计。
- 事件时间线字段 `event_time` 与 `published_at` 分离原则在 prompt 硬规则中已有声明，但在后续 Task 3/4 需补充自动化校验，防止缺失 `event_time` 时被隐式回填为 `published_at`。

## 2. 缓存身份与失效机制审计

### 2.1 当前缓存表结构（`src/gni/infrastructure/models.py:712-747`）
`ReportNarrativeTask` 唯一约束 `uq_report_narrative_task_key` 仅包含 4 列：
```text
(report_type, period, task_type, prompt_version)
```
### 2.2 审计发现的 4 个缓存缺陷

1. **缺少关键版本维度**：缓存键未包含 `model_version`、`schema_version`、`methodology_version`、`taxonomy_version`。当切换模型（如 `deepseek-chat` → `deepseek-reasoner`）或升级统计方法论/议题分类体系时，若 `prompt_version` 与 `evidence_hash` 未变，旧缓存会被错误复用。
2. **Legacy 与 Canonical 读取行为不一致**：
   - `runner.py:load_cached_intelligence()` (L139-163) **不校验** `evidence_hash` 匹配，仅在返回体中标记 `stale: true`，前端可能仍展示过期研判。
   - `assessment.py:run_assessment_task()` (L564-579) 校验 `evidence_hash == ev_bundle.evidence_hash`，但同样不校验 `model_version` / `methodology_version` / `taxonomy_version`。
3. **同名 `event_analysis` 跨引擎共表风险**：Legacy（`daily_event_v1.0`）与 Canonical（`assess_event_v2.0`）共享 `task_type="event_analysis"`，虽因 `prompt_version` 不同暂未触发主键冲突，但维护成本高且易误查。
4. **自然月与滚动月缓存 `period` 格式区分**：当前自然月 `period="2026-11"`，滚动 30 天 `period="2026-10-28_2026-11-26"`，两者天然隔离，不会碰撞。

## 3. 改进建议（供 Task 3 实施）

1. **自然月公平对比**：在 `monthly.py` 中检测 `now_local < win_end` 时设置 `is_partial_period=True`，并计算同天数对齐基准（MTD vs 上月同天数 MTD）作为主要环比，同时在 `historical_v1_stats` 显式标记 `is_partial: true`。
2. **完整缓存指纹**：在 `ReportNarrativeTask` 新增 `cache_fingerprint`（或扩展查询条件），将 `report_type + period + task_type + evidence_hash + prompt_version + model_version + schema_version + methodology_version + taxonomy_version` 纳入命中判断；保留 `force=true` 与 `tasks=[...]` 局部重试能力。
