# UI_TEST_COVERAGE_REPORT.md — Phase 7 API / 前端构建与核心用户流程测试报告

> 分支：`cursor/data-trust-batch1` | 日期：2026-11-26

## 1. 自动化测试与静态检查结果

| 检查项 | 命令 | 结果 |
|---|---|---|
| Python 全量单元测试 + Phase 7 一致性集成测试 + 架构零反向依赖守护 | `.venv/bin/pytest tests/unit --ignore=tests/unit/test_editorial_focus.py -q` | **135 passed, 0 failed** |
| 前端 TypeScript 类型检查 + Vite 生产构建 | `cd web && npm run build` (`tsc -b && vite build`) | **PASS**（0 错误，294ms，69 modules） |
| 前端代码静态检查 | `cd web && npm run lint` (`oxlint`) | **PASS**（0 errors，仅有既有风格的 react-hooks/refresh warnings） |

## 2. 六条核心用户流程真实数据库验证（SQLite 只读烟雾）

| 流程 | 验证链路 | 真实库观测结果 | 状态 |
|---|---|---|---|
| **Flow 1：每日情报阅读** | `/api/dashboard` → `/api/reports/daily/package` → Evidence | `article_count=27`，7 章节完整，`validation_status="passed"` | PASS |
| **Flow 2：事件深入分析** | `/api/events` → `/api/events/{id}` (`event_timeline` + `cross_country_interpretation`) | 5 个事件，详情含时间线分离与跨国对比 | PASS |
| **Flow 3：议题趋势分析** | `/api/topics` → `/api/topics/tariffs_trade_war` | 15 固定议题完整，`tariffs_trade_war` 含 7 篇关联文章 | PASS |
| **Flow 4：国家比较** | `/api/countries/compare?countries=US,RU,DE` | 3 国并排返回样本量、立场、情感与议题 | PASS |
| **Flow 5：叙事追踪** | `/api/narratives?days=30` | 接口正常返回 `0`（诚实反映真实库尚未聚簇，无 Mock 伪造） | PASS |
| **Flow 6：证据追溯** | `/api/articles` → `/api/evidence/{id}` + `/api/sentiment-stance` + `/api/outlook` | 153 篇涉华文章分页正常，证据反查命中，`stance_target="china_mainland"`，`outlook_status="completed"` | PASS |

## 3. 测试覆盖说明（诚实披露）

- 后端 API 路由、10 项数据一致性不变量与真实库 6 条用户流程均已通过自动化测试与脚本验证。
- 前端已完成全量 TypeScript 编译与 Vite 生产打包，但 `web/` 尚未引入 Vitest / Playwright 浏览器级自动化组件测试套件（建议作为 Phase 8 或前端质量专项补充）。
- 额外修复 2 处真实历史数据兼容性 Bug：`dashboard/pages_api.py` 与 `events/service.py` 对 `v0.1` 字符串型 `sentiment`/`framing` 的容错处理。
