# P1-A 验收报告

**日期：** 2026-11-23  
**结论：** P1-A 通过；**停止**。进入 P1-B 须用户明确授权。

---

## 1. 交付物

| 项 | 路径 / 说明 |
|----|-------------|
| Phase 1 任务书 A–D | [PHASE1_TASK_BRIEF.md](PHASE1_TASK_BRIEF.md) |
| 已核验种子 | [configs/sources_seed.yaml](../configs/sources_seed.yaml)（6 个 active RSS） |
| 候选表更新 | [source_candidates.csv](source_candidates.csv) |
| 模型 + Alembic | `src/gni/infrastructure/models.py`、`alembic/versions/20261123_0001_p1a_initial.py` |
| RSS Adapter / 编排 | `src/gni/ingestion/rss_adapter.py`、`service.py` |
| CLI | `gni db init|upgrade`、`sources seed|list`、`ingest run|health` |
| 单测 | `tests/unit/test_rss_adapter.py`、`test_ingest_service.py` 等 |

---

## 2. 已核验并激活的来源（≥5）

| source_id | 国家 | feed（实测） | 本轮结果 |
|-----------|------|--------------|----------|
| us_voa_english | US | `https://www.voanews.com/api/z-$otevtiq` | success，20 条 |
| us_rfa_english | US | `https://www.rfa.org/english/rss` | success，30 条 |
| us_defense_news | US | defense.gov RSS（301→war.gov） | success，10 条 |
| us_federal_register_state | US | Federal Register State Dept RSS | success，23 条 |
| de_dw_english | DE | `https://rss.dw.com/rdf/rss-en-all` | success，138 条 |
| au_pm_media | AU | `https://www.pm.gov.au/rss.xml` | success，50 条 |

**合计：** 6 jobs 全部 success；入库 **271** 篇 `quality_status=rss_stub` 文章。

### 未接通（如实记录，未伪造）

- State.gov / White House：本环境 407/404  
- 俄罗斯 TASS：ConnectTimeout；Kremlin RSS 404  
- 印度 PIB/MEA：403  
- DFAT：ReadTimeout；德国外交部常见 RSS 路径 404  

---

## 3. 运行环境说明

本机通过 **Homebrew：Docker CLI + Colima + docker-compose** 提供 daemon（非 Docker Desktop）。

| 轮次 | 后端 | 结果 |
|------|------|------|
| 初验 | SQLite（Colima 未启动时） | 6/6 success，271 articles |
| **复验（正式）** | **PostgreSQL 16 via Colima** | **6/6 success，271 articles** |

复验步骤：`colima start` → `docker-compose up -d db` → `gni db upgrade` → seed → ingest。  
顺带修复：Postgres 外键下 seed 须先 `flush` sources 再写 reviews/health（见 `sources/seed.py`）。

---

## 4. 测试结果（PostgreSQL 复验，2026-11-23）

```text
colima start
docker-compose up -d db
gni db upgrade
gni sources seed          # 6 active sources
gni ingest run --once --allow-partial   # 6/6 success
pytest                    # 13 passed
counts: sources_active=6 articles=271 jobs=6 success_jobs=6 failed_jobs=0
```

重试：单元测试覆盖 `httpx.ConnectError` 后成功（tenacity）。  
失败路径：`feed_url=TBD` 抛 `ValueError`；失败会写入 `ingestion_jobs.status=failed` 与 `source_health`。

---

## 5. 启动命令（Postgres / Colima 复现）

```bash
colima start
cd /Users/zl/gh/Global_Narrative_Intelligence
docker-compose up -d db
export GNI_DATABASE_URL='postgresql+psycopg://gni:gni@localhost:5432/gni'
gni db upgrade
gni sources seed
gni ingest run --once --allow-partial
gni ingest health
pytest
```

无 Colima 时可用 SQLite 回退：`gni db init` + `sqlite+pysqlite:///./data/gni_p1a.db`。

Cron 示例：`0 * * * * cd /path/to/repo && gni ingest run --once --allow-partial`

---

## 6. 验收清单

- [x] 任务书含完整 P1-A～D  
- [x] ≥5 个 verified + active RSS（实际 6）  
- [x] `ingest run --once` 写 job + articles stub + health  
- [x] 失败可定位；重试可测  
- [x] pytest 通过（13）  
- [x] **未**实现 P1-B 正文深度提取、P1-C LLM、P1-D Dashboard/报告  

---

## 7. 已知限制 / 下一步

1. VOA 当前 channel 为 Africa 英文流；中国向频道可在后续核验后替换。  
2. Defense 源域名重定向至 war.gov，需在合规复核中记录。  
3. DW / ABC 等公共广播编辑独立性须持续人工审核。  
4. 生产建议切回 PostgreSQL；SQLite 仅作无 Docker 时的开发验收回退。  
5. **P1-B：** 正文提取、UTC/语言规范化、Hash/近重、质量状态升级。  

---

**P1-A 结束。等待用户明确授权后再开始 P1-B。**
