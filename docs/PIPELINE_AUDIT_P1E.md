# 处理/分析管线审计（P1-E 后）

**日期：** 2026-11-24  
**库：** Postgres `localhost:5432/gni`  
**更新：** 数据五层核心 Schema 见 [DATA_LAYERS.md](DATA_LAYERS.md)；`articles.pipeline_state` + `raw_documents` / `discovered_articles` / `collection_tasks`。

---

## 结论（一句话）

**不是“不能做”，而是之前没对 Postgres 跑过 process/analyze**；schema 修好后管线可跑。主要质量风险是：仅 `--skip-fetch` 时 RSS stub 过短 → L2 `insufficient_text` → relevance=`uncertain`（不进核心 KPI）。

**补充（数据五层）：** ingest 写 raw/discovered；process/analyze 推进 `pipeline_state`；与 `processing_status`/`analysis_status` 双轨兼容。

---

## 审计前快照

| 字段 | 分布 |
|------|------|
| articles | 381 |
| processing_status | 全部 `pending` |
| analysis_status | 全部 `pending` |
| quality_status | 全部 `rss_stub` |
| versions / analyses | 0 |
| content_clean | 0；content_original ≈ 373 |

→ 看板 KPI 为空是**数据未加工**，不是指标公式坏了。

---

## 试跑结果

| 操作 | 结果 |
|------|------|
| `process --skip-fetch` | 成功；多数 `processed_stub` |
| `analyze --provider heuristic` | 成功；依赖 `processing_status=done` |
| **真人 fetch**（trafilatura） | 涉华稿可抽到 2k–7k 字 → L2 `china_related` → core/substantial |
| DoD 等部分 URL | HTTP 403 → `insufficient_text` / stub |

试跑后（约）：process `done`≈106；L2 `china_related`≈29；level core/substantial/secondary 合计约 29。

---

## 阻塞点分级

### A. 运营缺口（主因）
1. 采集后未调度 `gni process run` / `gni analyze run`
2. Alembic 曾落后；列缺失时看板炸了，容易误以为整条管线不可用

### B. 产品/口径
1. `analyze` **只选** `processing_status=done`（设计如此）
2. Dashboard 默认纳入 `core/substantial/secondary`；`uncertain`（含正文不足）**不计** Article Count
3. `--skip-fetch` 适合冒烟，**不适合**正式涉华召回

### C. 工程摩擦
1. 日志曾打到 **stdout**，与 CLI JSON 混在一起（已改为 stderr）
2. 个别源 403 / WAF；需 UA/适配器或接受 stub

---

## 建议操作

```bash
source .venv/bin/activate
# 正式：拉正文再分析
gni process run --limit 100
gni analyze run --provider heuristic --limit 100
gni dashboard
```

离线冒烟才用：`gni process run --skip-fetch --limit 20`
