# Phase 0 / V3 仓库审计报告（只读对照）

**审计日期：** 2026-11-24  
**对照权威：** [BLUEPRINT_V3.md](BLUEPRINT_V3.md)、[PHASE0_BRIEF_V3.md](PHASE0_BRIEF_V3.md)  
**原则：** V3 为对齐修订，**不**推倒重做已完成的 Phase 0 骨架与 P1-A 采集。

---

## 1. 项目结构

```text
Global_Narrative_Intelligence/
├── alembic/                 # P1-A 迁移
├── configs/sources_seed.yaml
├── docs/                    # Phase 0 文档 + V3 原文 + 本审计
├── src/gni/
│   ├── core/                # 配置、日志
│   ├── sources/             # seed / list
│   ├── ingestion/           # RSS adapter + jobs
│   ├── infrastructure/      # SQLAlchemy models / db
│   ├── analysis|metrics|processing|reports|api|dashboard/  # 占位
│   └── cli.py
├── tests/unit/
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

约 23 个 Python 源文件；docs 含 Blueprint/Brief V3 及既有 PRD/架构/指标等。

---

## 2. 技术栈与入口

| 项 | 现状 |
|----|------|
| Python | ≥3.12（本机常见 3.14；推荐 3.12） |
| 包 | `gni` 0.1.1，`pip install -e ".[dev]"` |
| CLI | `gni health|version|db|sources|ingest` |
| DB | PostgreSQL 16（Colima + docker-compose）或 SQLite 回退 |
| 迁移 | Alembic `20261123_0001` |
| 采集 | httpx + feedparser + tenacity |
| 未启用 | FastAPI/Streamlit 业务页、LLM、Prefect、Kafka、pgvector |

与 V3 MVP 栈一致；无需为 V3 换栈。

---

## 3. 现有功能 / 模块

| 模块 | 状态 |
|------|------|
| Source Registry seed / list | 已实现（YAML → DB） |
| RSS Adapter + ingest jobs / health | 已实现（P1-A） |
| articles `rss_stub` | 已实现（全量 feed 条目，利于 Attention Share 分母） |
| 正文清洗 / 近重（P1-B） | 未实现 |
| LLM 对华分析（P1-C） | 仅 `NullLLMProvider` 占位 |
| 七项指标 / Dashboard / 报告 | 未实现 |

**活跃来源（工作区种子，含未提交五国补源）：** US/RU/DE/IN/AU 五国，≥8 个 active RSS（以 `configs/sources_seed.yaml` 为准）。

---

## 4. Git 工作区

| 项 | 值 |
|----|-----|
| 分支 | `main`，ahead of `upstream/main` |
| 已推送提交 | `91036c4` Phase 0；`b88dd0e` P1-A |
| 未提交 | 五国验收（RU/IN seed、UA、PRD 门槛）、以及本次 V3 文件入库与对齐修订 |

---

## 5. 可复用内容

- 全部 P1-A 采集与 DB 模型（勿重写）
- Phase 0 文档骨架与 ADR（在其上做 V3 口径修订）
- 测试：RSS/CLI/config 冒烟可继续扩展

---

## 6. V3 vs 现状：差异与处置

| 主题 | V3 | 现状 | 处置 |
|------|----|------|------|
| 产品表述 | 对华舆情；Central Target=China；Country×Source×Topic×Target×Time | 有中国中心，总览偏「全球议题」 | 修订 PRD / PRODUCT_SCOPE / Dashboard |
| Phase 1 指标 | **7 项核心指标** | METRICS 六维叙事，Attention 分母未写清 | 重写 METRICS |
| Attention Share | 对华量 / 同源全量有效报道 | 已存全量 stub；缺 china_relevance | 口径定文档；实现放 P1-D |
| Dashboard | 总览+国家+**跨国比较**+质量 | 缺跨国页；无 DASHBOARD.md | 新增 DASHBOARD.md，修订可视化 |
| Phase 1 切分 | A…F（指标/Dash/报告拆开） | P1-D 捆在一起 | PHASE1_TASK_BRIEF 拆 D/E/F |
| Phase 0 Brief | Phase 0 不做生产采集 | 已完成 P1-A | **不回退** |
| 来源规模 | 3–5 国，按可行性 | 五国各 ≥1 源 | 保持 |
| 技术栈 | Modular monolith 等 | 已对齐 | 不改栈 |

---

## 7. 风险与缺口

1. **口径漂移：** 旧 METRICS/可视化若不同步，P1-D 会按错误分母实现。  
2. **Attention Share：** 依赖「全量入库 + 对华过滤」；P1-C 必须产出可靠 `china_relevance`。  
3. **印度 UA：** 部分官网 WAF 拒研究 UA；已用 per-source UA + `X-GNI-Client`（见 COMPLIANCE）。  
4. **未提交改动：** 五国补源与 V3 对齐应一并审查后再 commit。  
5. Brief V3 要求「先审计等确认」——本仓库 Phase 0/P1-A 已先行；本次以对齐代替重开。

---

## 8. 建议执行计划（已采纳）

1. 入库 V3 原文（本轮已做）。  
2. 本审计落盘。  
3. **文档对齐：** PRD、PRODUCT_SCOPE、METRICS（7 项）、DASHBOARD.md、VISUALIZATION_SPEC、PHASE1_TASK_BRIEF（A–F）、DEVELOPMENT_PLAN / README 权威说明。  
4. **不**重做 P1-A；P1-B+ 另授权后按新任务书推进。

---

## 9. Phase 0 / Phase 1 是否修改？

| 范围 | 建议 |
|------|------|
| Phase 0 工程 | **不重做** |
| Phase 0 文档 | **V3 对齐修订**（非从零） |
| P1-A 代码 | **保持**；表述改为对华样本 + 五国门槛 |
| P1-B～F | **按 V3 任务书**再开发 |

**最终原则（V3）：** 研究中心始终是中国；国家是观察维度；主题是切面；Target 是评价对象；时间是变化维度。
