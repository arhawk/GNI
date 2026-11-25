# Global Narrative Intelligence（GNI）

**Agent 驱动的官方媒体对华舆情监测系统**：以 China 为固定研究对象，持续监测、理解、量化、发现与报告。

**设计权威：** [docs/BLUEPRINT_V4.md](docs/BLUEPRINT_V4.md)（§22+ 冲突时优先）  
**当前工程进度：** 见权威表 [docs/PHASE_STATUS.md](docs/PHASE_STATUS.md)（P1-A～E 完成；P1-F1 Fingerprint / P1-F2 Daily Brief 已落地；P1-F3 Alerts 持久化与 P1-F4 周月报待办）。

## 文档入口

- [阶段状态（权威）](docs/PHASE_STATUS.md) · [Blueprint V4](docs/BLUEPRINT_V4.md) · [筛选 Addendum A1](docs/BLUEPRINT_V4_ADDENDUM_A1.md)
- [Event Intelligence IA](docs/EVENT_INTELLIGENCE_IA.md) · [Dashboard](docs/DASHBOARD.md) · [Data Schema](docs/DATA_SCHEMA.md)
- [报告产品](docs/REPORT_PRODUCTS.md) · [指标](docs/METRICS.md) · [Alerts](docs/ALERTS.md)
- [Provisional 标定](docs/PROVISIONAL_CALIBRATION.md) · [第二批接口](docs/BATCH2_INTERFACES.md) · [第三批接口](docs/BATCH3_INTERFACES.md)
- [Phase 1 任务书](docs/PHASE1_TASK_BRIEF.md) · [P1-A 验收](docs/PHASE1A_ACCEPTANCE.md) · [P1-B 验收](docs/PHASE1B_ACCEPTANCE.md)
- [开发计划](docs/DEVELOPMENT_PLAN.md) · [种子配置](configs/sources_seed.yaml)

MVP 国家：美 / 俄 / 德 / 印 / 澳。**P1-A 门槛：≥5 监测国家**各 ≥1 个 active 源。

## 环境要求

- 推荐 Python 3.12；Colima + docker-compose（PostgreSQL 16）

## Phase 1-A 快速开始

```bash
cd /Users/zl/gh/Global_Narrative_Intelligence
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env

colima start
docker-compose up -d db
gni db upgrade
gni sources seed
gni ingest run --once --allow-partial
gni ingest health
pytest
```

无 Colima 时：`GNI_DATABASE_URL=sqlite+pysqlite:///./data/gni_p1a.db` + `gni db init`。

Cron：`gni ingest run --once --allow-partial`

### 目标 UI（React + Event Intelligence）

```bash
source .venv/bin/activate
pip install -e ".[api,dev]"
gni events rebuild          # P1-F proto-Events（一簇多文；无坐标不强行钉点）
gni api serve               # http://127.0.0.1:8000
cd web && npm install && npm run dev   # http://127.0.0.1:5173（代理 /api）
```

地图两模式互斥：**Event geography (Where)** vs **Reporting sources (Who)**。事件详情三视图：Where / Who reports / How they frame + 时间线。

### 调试看板（Streamlit / P1-E）

```bash
pip install -e ".[dashboard]"
gni dashboard   # http://localhost:8501
```

### Playwright E2E

```bash
pip install -e ".[dev,dashboard,api]"
python -m playwright install chromium
# Streamlit debug shell
pytest tests/e2e/test_dashboard_playwright.py -m e2e
# React Event Intelligence UI (needs web/node_modules)
cd web && npm install && cd ..
pytest tests/e2e/test_web_react_playwright.py -m e2e
```

## 阶段边界

权威细节见 [PHASE_STATUS.md](docs/PHASE_STATUS.md)。摘要：

| 阶段 | 状态 |
|------|------|
| Phase 0 + V3/V4 文档对齐 | 完成 |
| P1-A～P1-E | 完成 |
| P1-F1 Fingerprint / 事件 UI | 原型完成（持续加固） |
| P1-F2 Daily Brief v2 | 已实现 |
| P1-F3 持久化 Alerts | 待办 |
| P1-F4 周报/月报 | 规格完成、编码待办 |
| Phase 2 跨语言事件/叙事 | 后续 |

## 许可证

Proprietary — 内部研究。合规见 [docs/COMPLIANCE.md](docs/COMPLIANCE.md)。
