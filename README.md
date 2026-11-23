# Global Narrative Intelligence（GNI）

全球官方媒体舆论信号采集与叙事监测研究系统。

**当前阶段：Phase 1-A（来源注册与 RSS 采集）**  
P1-B/C/D 仅见任务书，尚未实现。授权前请勿当作完整 MVP。

## 文档入口

- [Phase 1 任务书（A～D）](docs/PHASE1_TASK_BRIEF.md)
- [P1-A 验收](docs/PHASE1A_ACCEPTANCE.md)
- [产品需求 PRD](docs/PRD.md)
- [开发计划](docs/DEVELOPMENT_PLAN.md)
- [来源候选表](docs/source_candidates.csv)
- [种子配置](configs/sources_seed.yaml)

MVP 国家短名单：美国、俄罗斯、德国、印度、澳大利亚（接通顺序：美→俄→德→印→澳）。  
P1-A 已核验并激活的源以 `configs/sources_seed.yaml` 为准（俄/印本轮未接通）。

## 环境要求

- **推荐 Python 3.12**（Docker/CI 以此为准）
- Docker（PostgreSQL 16）

## Phase 1-A 快速开始

```bash
cd /Users/zl/gh/Global_Narrative_Intelligence
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env

# 推荐：Colima + PostgreSQL
colima start   # 若尚未运行
docker-compose up -d db
# .env 默认 GNI_DATABASE_URL=postgresql+psycopg://gni:gni@localhost:5432/gni
gni db upgrade

# 无 Colima 时回退 SQLite：
# export GNI_DATABASE_URL=sqlite+pysqlite:///./data/gni_p1a.db
# gni db init

gni sources seed
gni sources list --active
gni ingest run --once --allow-partial
gni ingest health
pytest
```

调度建议：系统 cron 每小时执行 `gni ingest run --once --allow-partial`（与 ADR 0003 一致）。

## 阶段边界

| 阶段 | 状态 |
|------|------|
| Phase 0 | 完成 |
| P1-A 来源 + RSS 采集 | 本阶段 |
| P1-B 正文处理去重 | 未开始 |
| P1-C LLM 分析 | 未开始 |
| P1-D 指标/Dashboard/报告 | 未开始 |

## 许可证

Proprietary — 内部研究用途。合规见 [docs/COMPLIANCE.md](docs/COMPLIANCE.md)。
