# P1-B 验收报告

**日期：** 2026-11-24  
**结论：** P1-B 通过（抽取/清洗/去重/规则 L1）；**停止**。进入 P1-C（L2/L3/Weight）须用户明确授权。  
**依据：** [PHASE1_TASK_BRIEF.md](PHASE1_TASK_BRIEF.md)、[BLUEPRINT_V4_ADDENDUM_A1.md](BLUEPRINT_V4_ADDENDUM_A1.md)

---

## 1. 交付物

| 项 | 说明 |
|----|------|
| Addendum 入库 | [BLUEPRINT_V4_ADDENDUM_A1.md](BLUEPRINT_V4_ADDENDUM_A1.md) |
| 等级词表 | provisional_v0.2：core/substantial/secondary/incidental/none/uncertain |
| ORM + Alembic | `article_versions`、`article_screenings`、`processing_jobs`；articles 扩展字段 |
| 处理管线 | `src/gni/processing/`（extract/normalize/language/dedup/L1） |
| 词典 | [configs/china_entity_dictionary_v0.1.yaml](../configs/china_entity_dictionary_v0.1.yaml) |
| CLI | `gni process run --once [--skip-fetch] [--limit N]` |
| 测试 | pytest unit **23 passed** |

---

## 2. 验收清单

- [x] 正文提取（trafilatura → BS4 回退）；失败 → `insufficient_text`  
- [x] 清洗、语言检测、URL 规范化、content/title hash  
- [x] `article_versions` 落库；不静默覆盖旧版本（递增 version_no）  
- [x] 同源 content_hash / 规范化标题近重 → `duplicate_of` + `exclude_from_metrics`  
- [x] 规则 L1：`explicit_relevant / likely_relevant / no_match / uncertain`；`no_match` 不删除  
- [x] 单篇失败不中断整批  
- [x] **未**实现 L2/L3/LLM Weight（P1-C）  

---

## 3. 本地试跑（SQLite，`--skip-fetch`）

对 `data/gni_p1a.db`：`gni db init` 补列后 `gni process run --limit 8 --skip-fetch` → 8/8 ok，写入 screenings + versions。正式全文抓取需网络：`gni process run --limit 20`（勿加 skip-fetch）。

Postgres：`alembic upgrade head`（revision `20261124_0002`）。

---

## 4. 不做 / 下一段

- L2 正文涉华 LLM、L3 片段、Relevance Weight 评估 → **P1-C**  
- Dashboard / 指标 / 预警 → P1-D+  
