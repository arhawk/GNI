# GNI 报告系统集成验收与回归测试报告（Task 6）

**日期**：2026-11-26  
**分支**：`main`（本地工作区，未执行 `git push`）

---

## 1. 测试命令与结果汇总

| 测试套件 | 命令 | 结果 |
|---|---|---|
| **后端全量单元测试 + 统计口径 9 条红线集成测试** | `.venv/bin/pytest tests/unit --ignore=tests/unit/test_editorial_focus.py -q` | **152 passed, 0 failed**（18.16s） |
| **前端 TypeScript + Vite 生产构建** | `cd web && npm run build` | **0 errors**（288ms） |
| **前端 Oxlint 静态检查** | `cd web && npm run lint` | **0 errors**（新增组件 0 warnings） |
| **本地真实数据库样本验收** | `build_daily_report` / `build_weekly_report` / `build_monthly_report`（`2026-11-26`） | Daily 38 篇 / Weekly 205 篇 / Monthly 295 篇，全部通过门禁与多国证据抽样校验 |

> 注：`tests/unit/test_editorial_focus.py` 为历史遗留测试文件（非本次报告重构改动范围），沿用 Task 1 基线策略单独排除。

---

## 2. 统计口径 9 条红线自动化核验（`tests/unit/test_report_system_integration.py`）

1. **全球唯一去重**：4 篇唯一文章 → `global.article_count == 4`（通过）。
2. **多议题重叠 + 议题内去重**：同篇文章含重复 `tariffs_trade_war` 标签仅计数 1 次，同时归入 `tech_competition`（通过）。
3. **多板块遵守同规则**：`boards` 严格按板块内去重（通过）。
4. **跨议题之和不等于全球总量**：`sum(topic_counts) > global.article_count`，前端图表明确提示且不堆叠求和（通过）。
5. **Unclassified 口径**：`quoted_actor` 不被误判为媒体立场，归入 `Unclassified`；计入总文章数，**不计入** `positive_rate` / `neutral_rate` / `negative_rate` 分母（通过）。
6. **`stance_coverage_rate` 分母口径**：`3 / 4 = 0.75`（通过）。
7. **国家按信源国家归属**：`US: 2, GB: 2`（通过）。
8. **`published_at` 与 `event_time` 分离**：文章聚合使用 `published_at`，事件时间线使用 `event_time`（通过）。
9. **`event_time = NULL` 不伪造**：未定日期事件在 `visualizations.event_timeline` 中严格保持 `None`（通过）。

---

## 3. 验收结论与合并/部署建议

- **已通过验收**：
  - 统一 Canonical Assessment Engine 与 `ReportOrchestrator`（Task 2）
  - 统一时间窗口（含闰年、跨年、月中 MTD 公平环比）、完整版本感知缓存身份与三态质量门禁（Task 3）
  - 确定性证据精选器、统一 Daily/Weekly/Monthly `ReportPackageContract`、确定性图表数据与 Markdown 导出（Task 4）
  - 前端独立视图外壳、5 类纯 SVG/CSS 数据驱动图表、门禁/周期提示与废弃代码清理（Task 5）
  - 全链路回归与 9 条统计口径自动化核验（Task 6）
- **部署与回滚说明**：
  - 本次重构**无破坏性数据库 DDL 变更**（缓存治理字段兼容存储于现有 `ReportNarrativeTask` 与 JSON 载荷），API 完整向后兼容。
  - 部署顺序：先重启后端 `gni api serve`，再构建/发布前端 `web/dist`；若需回滚，直接切回原提交并重启服务即可，无数据迁移回滚风险。
- **合并/部署建议**：**建议合并与本地部署**（全部核心门禁与 152 项后端测试 + 前端 build/lint 全绿）。
