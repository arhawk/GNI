# API_INTEGRATION_SPEC.md — Phase 7 API 解耦与领域接口规范

> 分支：`cursor/data-trust-batch1` | 日期：2026-11-26 | 入口：[src/gni/api/app.py](src/gni/api/app.py)（`api_version: "v2.0-phase7"`）

## 1. 架构解耦成果

1. **彻底消除历史跨层反向依赖**：将 `overview_payload()` 从 `src/gni/events/service.py` 迁移至 [src/gni/dashboard/overview.py](src/gni/dashboard/overview.py)，移除了 `tests/unit/test_imports.py` 中最后 1 条 `known_legacy` 白名单；底层包（`core`/`infrastructure`/`ingestion`/`processing`/`analysis`/`metrics`/`events`）对上层（`reports`/`api`/`dashboard`）的反向导入数为 **0**。
2. **领域路由拆分**：原单文件 `src/gni/api/app.py` 拆分为 9 个 FastAPI `APIRouter`（`src/gni/api/routers/*.py`），100% 保留全部既有路由路径与响应结构。

## 2. 资源端点清单（含实现状态）

| 资源域 | 路由文件 | 新增 / 增强端点 | 兼容保留端点 | 状态 |
|---|---|---|---|---|
| Dashboard | `routers/dashboard.py` | `GET /api/dashboard` | `GET /api/overview` | 已完成并运行 |
| Reports | `routers/reports.py` | `GET /api/reports/list`, `GET /api/reports/daily/package` (`json` / `markdown`) | `GET /api/reports/daily\|weekly\|monthly`, `POST /api/reports/{type}/analyze` | 已完成并运行（Weekly/Monthly 仍为旧结构） |
| Assessments | `routers/assessments.py` | `GET /api/assessments`, `GET /api/assessments/{task_type}`, `POST /api/assessments/{task_type}/run` | — | 已完成并运行 |
| Events | `routers/events.py` | `GET /api/events/{id}`（增补 `event_timeline`/`coverage_timeline`/`cross_country_interpretation`/`evidence_segments`/`event_assessment`）, `POST /api/events/{id}/split` | `GET /api/events`, `POST /api/events/rebuild\|lock\|merge` | 已完成并运行（`split` 目前为 API-only，UI 留给 Phase 8 治理） |
| Topics | `routers/topics.py` | `GET /api/topics`, `GET /api/topics/{topic_id}` | — | 已完成并运行 |
| Countries | `routers/countries.py` | `GET /api/countries/compare` | `GET /api/countries`, `GET /api/countries/{id}`, `GET /api/countries/{id}/china-attitude` | 已完成并运行 |
| Narratives | `routers/narratives.py` | `GET /api/narratives`, `GET /api/narratives/{narrative_id}` | — | 已完成并运行 |
| Sentiment & Stance / Outlook | `routers/sentiment_stance.py` | `GET /api/sentiment-stance`, `GET /api/outlook` | — | 已完成并运行 |
| Articles & Evidence | `routers/articles.py` | `GET /api/articles`（分页+8 维筛选）, `GET /api/articles/{id}`, `GET /api/evidence/{evidence_id}` | `POST /api/articles/trace` | 已完成并运行 |
| Alerts & System | `routers/alerts_system.py` | — | `GET /api/alerts`, `POST /api/alerts/*`, `GET /api/search`, `GET /api/trends`, `GET /api/system/status` | 已完成并运行 |

## 3. 版本兼容与错误规范

- `/health` 返回 `api_version: "v2.0-phase7"`，所有新端点通过增量字段或新资源路径提供，零破坏性变更。
- 非法时间返回 `400`，未知 `topic_id`/`event_id`/`article_id`/`evidence_id`/`task_type` 返回 `404`，分页接口统一返回 `{ items, pagination: { page, page_size, total, total_pages }, sort }`。
