# GNI 报告系统已知局限与后续事项（Task 6）

## 1. 已实现 vs 部分实现 vs 暂时无法验证

| 项目 | 当前状态 | 说明 |
|---|---|---|
| 统一 Orchestrator + 缓存版本失效 + 局部重试 | **已实现** | 经 152 项单测与模拟 LLM 验证全绿 |
| 时间窗口（自然日/滚动 7 天/自然月/MTD/滚动 30 天）与三态质量门禁 | **已实现** | 经闰年、跨年、月中 MTD 与阻断/警告测试验证 |
| 确定性证据精选、统一 `ReportPackageContract`、`visualizations`、Markdown 导出 | **已实现** | 已通过真实本地数据库 `2026-11-26` 样本抽检 |
| 前端三类报告视图外壳与 5 类纯 SVG 图表 | **已实现** | `npm run build` 与 `npm run lint` 0 error |
| 真实外部 LLM API 端到端压测（DeepSeek 线上全量 9 任务并发） | **暂时无法验证** | 本地测试环境使用确定性 Stub LLM，未在自动化测试中消耗线上 API 额度 |
| 月报 6 个月以上长期结构基线 | **部分实现（受当前数据积累限制）** | 代码已支持 6+ 个月文章级重算并在基线不足 6 个月时于附录诚实披露；当前本地库历史积累尚不足 6 个完整月 |
| `NarrativeStatusMatrix` 跨月叙事生命周期热力矩阵 | **计划中** | 待多月历史数据积累充足后启用完整跨月叙事迁移可视化 |
| `tests/unit/test_editorial_focus.py` | **历史遗留（未改动）** | 原仓库已存在的独立测试文件，未纳入本次报告重构改动范围 |

## 2. 运营与使用注意事项

- 若生产环境切换 `LLM_MODEL` 或升级 `ASSESSMENT_SCHEMA_VERSION`，系统将自动失效旧缓存并触发重算，请提前评估 Token 预算。
- 前端首次部署后需确保后端 `gni api serve` 已重启至最新版本，以便返回 `window_spec`、`quality_gate`、`visualizations` 与 `report_package`。
