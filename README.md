# Global Narrative Intelligence（GNI）

**Agent 驱动的官方媒体对华舆情监测系统**：以 China 为固定研究对象，持续监测、理解、量化、发现与报告。

**设计权威：** [docs/BLUEPRINT_V4.md](docs/BLUEPRINT_V4.md)（§22+ 冲突时优先）  
**当前工程进度：** Phase 1-A/B 已验收；P1-C～F 待授权。

## 文档入口

- [Blueprint V4](docs/BLUEPRINT_V4.md) · [筛选 Addendum A1](docs/BLUEPRINT_V4_ADDENDUM_A1.md) · [V4 审计](docs/PHASE0_REPOSITORY_AUDIT_V4.md)
- [Blueprint V3](docs/BLUEPRINT_V3.md)（历史）
- [PRD](docs/PRD.md) · [指标](docs/METRICS.md) · [Dashboard](docs/DASHBOARD.md) · [Alerts](docs/ALERTS.md)
- [Provisional 标定](docs/PROVISIONAL_CALIBRATION.md)（P1-C 起临时默认 + 公开评测代理）
- [Phase 1 任务书（监测型 A～F）](docs/PHASE1_TASK_BRIEF.md) · [P1-A 验收](docs/PHASE1A_ACCEPTANCE.md) · [P1-B 验收](docs/PHASE1B_ACCEPTANCE.md)
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

### 看板（P1-E）

```bash
source .venv/bin/activate
pip install -e ".[dashboard]"
# Postgres 若缺 P1-B/C 列：看板启动会自动 ensure_schema；也可 gni db upgrade / gni db init
gni dashboard
```

浏览器：`http://localhost:8501`

### Playwright E2E

```bash
pip install -e ".[dev,dashboard]"
python -m playwright install chromium
pytest tests/e2e -m e2e
```

## 阶段边界

| 阶段 | 状态 |
|------|------|
| Phase 0 + V3/V4 文档对齐 | 完成 |
| P1-A～P1-E | 完成 |
| P1-F 报告/预警/重大新闻候选 | 待授权 |

## 许可证

Proprietary — 内部研究。合规见 [docs/COMPLIANCE.md](docs/COMPLIANCE.md)。
