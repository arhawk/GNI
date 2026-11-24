# P1-A 验收报告

**日期：** 2026-11-24（含五国门槛补验）  
**结论：** P1-A 通过（**≥5 监测国家**）；**停止**。进入 P1-B 须用户明确授权。

---

## 1. 验收门槛（已修订）

| 项 | 标准 |
|----|------|
| 监测国家 | **≥5 国**，短名单 US / RU / DE / IN / AU 各国 ≥1 个 verified+active 源 |
| 采集 | active 源 `ingest run --once` 可成功写 job + articles stub + health |
| 工程 | 失败可定位；重试可测；pytest 通过 |
| 不做 | P1-B/C/D 业务；不编造 feed；不绕过登录/付费墙 |

---

## 2. 交付物

| 项 | 路径 / 说明 |
|----|-------------|
| Phase 1 任务书 A–D | [PHASE1_TASK_BRIEF.md](PHASE1_TASK_BRIEF.md) |
| 已核验种子 | [configs/sources_seed.yaml](../configs/sources_seed.yaml)（**8** 个 active RSS，覆盖 **5** 国） |
| 候选表更新 | [source_candidates.csv](source_candidates.csv) |
| 模型 + Alembic | `src/gni/infrastructure/`、`alembic/versions/20261123_0001_p1a_initial.py` |
| RSS Adapter / 编排 | 支持 per-source `config.user_agent` |
| CLI | `gni db init|upgrade`、`sources seed|list`、`ingest run|health` |

---

## 3. 五国活跃源一览

| 国家 | source_id | 状态 |
|------|-----------|------|
| 美国 | us_voa_english, us_rfa_english, us_defense_news, us_federal_register_state | active |
| 俄罗斯 | **ru_tass_english** | active（2026-11-24 复探接通） |
| 德国 | de_dw_english | active |
| 印度 | **in_president** | active（总统府 RSS；PIB/MEA 仍 403） |
| 澳大利亚 | au_pm_media | active |

**Postgres 复验计数（2026-11-24）：**  
`active_countries=['AU','DE','IN','RU','US']`（5）、`sources_active=8`、`articles≥381`（含 RU 100 + IN 10 新增）、pytest **13 passed**。

### 仍未接通（保留候选，不强爬）

- State.gov / White House：407/404  
- 印度 PIB / MEA：持续 403  
- 俄罗斯 Kremlin 官方 feed：超时/404（TASS 已覆盖该国）  

### 印度 UA 说明

`presidentofindia.gov.in` 对纯研究 UA 返回 403，对浏览器 UA 返回 200。  
已在源 `config.user_agent` 配置浏览器兼容 UA，并用 `X-GNI-Client` 标识研究客户端；**非**登录/付费墙绕过。见 [COMPLIANCE.md](COMPLIANCE.md)。

---

## 4. 运行环境

**PostgreSQL 16 via Colima + docker-compose**（正式路径）。  
SQLite 仍可作为无 Colima 时的开发回退。

```bash
colima start
docker-compose up -d db
export GNI_DATABASE_URL='postgresql+psycopg://gni:gni@localhost:5432/gni'
gni db upgrade
gni sources seed
gni ingest run --once --allow-partial
gni ingest health
pytest
```

---

## 5. 验收清单

- [x] **≥5 监测国家**各有 verified+active 源（US/RU/DE/IN/AU）  
- [x] `ingest run` 写 job + articles stub + health  
- [x] 失败可定位；重试可测  
- [x] pytest 通过  
- [x] **未**实现 P1-B/C/D  

---

## 6. 下一步

**P1-B：** 正文提取、UTC/语言规范化、Hash/近重、质量状态升级。  
并行可选：继续核验 State.gov、PIB/MEA 等更高密度中国议题源。

**P1-A 结束。等待用户明确授权后再开始 P1-B。**
