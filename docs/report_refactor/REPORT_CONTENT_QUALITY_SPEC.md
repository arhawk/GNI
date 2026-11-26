# GNI 报告内容、证据精选与分析质量规范（Task 4）

## 1. 三类报告内容架构统一（`src/gni/reports/package_composer.py`）

三类报告均输出统一 `ReportPackageContract`（`report_package` 字段）与确定性图表数据（`visualizations` 字段），并支持 `/api/reports/{daily|weekly|monthly}/package?format=json|markdown` 导出：

- **Daily（快速监测，6 章 + 附录）**：`chapter_1_executive_judgment` → `chapter_6_outlook_watchlist` + `appendix`
- **Weekly（解释变化，8 章 + 附录）**：`chapter_1_weekly_executive` → `chapter_8_outlook_priorities` + `appendix`
- **Monthly（理解长期格局，8 章 + 附录）**：`chapter_1_monthly_executive` → `chapter_8_strategic_outlook` + `appendix`（当有效历史基线 `< 6` 个月时在附录诚实标注局限）

## 2. 确定性证据精选器（`curate_finding_evidence`）

在 `src/gni/reports/narrative/evidence.py` 中新增 `curate_finding_evidence()`：
- 严格按 `article_id` 与归一化标题去重；
- 强制国家（`country_code`）、信源（`source_name`）与事件（`event_id`）多样性上限，防止单一媒体或单一热点垄断正文证据位；
- 每条重要发现精选 2–3 篇代表支持证据，并自动匹配不同立场的反证/对照视角（`counter_evidence`）。

## 3. 确定性图表数据结构（`visualizations`）

所有图表数据均由后端确定性 V1.0 统计层生成（严禁由 LLM 编造）：
1. `trend_line`：涉华报道量趋势（基于 `Article Count` + `published_at`）
2. `country_bar`：国家分布横向条形图（按信源国家，附 `stance_coverage_rate`）
3. `topic_delta`：议题分布与环比变化（显式声明跨议题允许重叠）
4. `stance_stacked`：立场四分类堆叠分布（`Unclassified` 独立展示且不进正/中/负比例分母）
5. `event_timeline`：重点事件时间线（严格取自 `Event.event_time`，不明确为 `null`，绝不用 `published_at` 替代）

## 4. 真实本地数据库样本验收记录（采样日期：`2026-11-26`）

| 报告类型 | 周期 | 去重涉华文章数 | 立场覆盖率 | 门禁状态 | 章节数 | 精选证据与多样性 |
|---|---|---:|---:|---|---:|---|
| **Daily** | `2026-11-26` | 38 | 31.6% | `passed_with_warnings`（低覆盖率 + 当日进行中） | 7（6 章 + 附录） | 完整挂载 `visualizations` 5 组确定性图表 |
| **Weekly** | `2026-11-20_2026-11-26` | 205 | 51.7% | `passed_with_warnings` | 9（8 章 + 附录） | 精选 3 篇代表证据，覆盖 `['IN', 'RU', 'US']` 3 国不同信源 |
| **Monthly** | `2026-11` | 295 | 43.7% | `passed_with_warnings`（月中 MTD 公平环比） | 9（8 章 + 附录） | 精选 3 篇代表证据，覆盖 `['IN', 'RU', 'US']` 3 国；附录明确标注历史月度基线不足 6 个月 |

- 单元测试：`tests/unit/test_report_package_composer.py` 及全部报告测试 **17/17 通过**。
