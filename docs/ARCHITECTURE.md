# 技术架构（ARCHITECTURE）

**版本：** 0.1  
**风格：** Modular Monolith + Asynchronous Data Pipeline  
**非目标：** 微服务、Kafka、Neo4j、Prefect（MVP 非强制）、Celery、Redis（非必要不引入）

---

## 1. 原则

1. 模块边界清晰，经明确接口交互  
2. 任务异步/可重试，单篇失败不中断整批  
3. PostgreSQL 为事实存储  
4. Adapter 插件化；来源配置进 Registry  
5. 模型供应商可替换  
6. 分析结果可追溯、可版本化  
7. 先可运行可测试，再增加分布式复杂度  

---

## 2. 逻辑分层

```text
Source Layer        国家/组织/来源/合规属性
     ↓
Ingestion Layer     RSS / API / Web Adapter
     ↓
Processing Layer    提取、清洗、语言、时间、去重、质检
     ↓
Intelligence Layer  文章分析（MVP）；Embedding/事件/叙事（Phase 2+）
     ↓
Storage Layer       PostgreSQL（+ pgvector Phase 2）
     ↓
Application Layer   FastAPI、Streamlit、报告、（Phase 3 Agent）
```

---

## 3. MVP 技术栈

| 层 | 技术 | 说明 |
|----|------|------|
| Language | Python 3.12+（Docker 钉 3.12） | |
| API | FastAPI | |
| Dashboard | Streamlit | |
| Database | PostgreSQL | |
| Vector | pgvector | Phase 2 |
| RSS | feedparser | |
| HTTP | httpx | |
| HTML | BeautifulSoup / 可替换抽取器 | |
| Crawling | Scrapy 可选 | |
| Scheduling | Cron / APScheduler | Phase 0 仅选型 |
| LLM | DeepSeek 抽象层 | 可替换 |
| Embedding | BGE-M3 等 | Phase 2 重点 |
| Test | pytest | |
| Deploy | Docker Compose | |
| Logging | 标准 logging / 结构化日志 | |

---

## 4. 包结构

```text
src/gni/
  core/             配置、日志、异常
  sources/          来源注册与治理
  ingestion/        Adapter 与采集任务
  processing/       清洗与去重
  analysis/         LLM 分析
  metrics/          指标计算
  reports/          日报周报与证据校验
  api/              FastAPI
  dashboard/        Streamlit
  infrastructure/   DB 会话等
```

---

## 5. Adapter 接口（设计）

```python
from abc import ABC, abstractmethod

class BaseAdapter(ABC):
    @abstractmethod
    def fetch(self, source_config):
        raise NotImplementedError

    @abstractmethod
    def parse(self, raw_item):
        raise NotImplementedError

    def health_check(self, source_config):
        return {"status": "unknown"}
```

来源特定逻辑放在 Source Registry 配置中，避免散落 `if/else`。

---

## 6. 数据流（MVP）

`Fetch → Parse → Normalize → Extract → Language Detect → Time Normalize → Deduplicate → Persist → Analyze → Aggregate Metrics → Report`

每步可观测；ingestion_jobs / analysis_runs / metric_runs 留痕。

---

## 7. 时间

- 存储：UTC  
- 展示：用户或报告指定时区  
- 区分：event_time、published_at、first_seen_at、analyzed_at、updated_at  
- 记录：source_timezone、report_timezone、time_precision  

---

## 8. 相关 ADR

- [0001 模块化单体](ADR/0001-modular-monolith.md)  
- [0002 数据库与向量扩展](ADR/0002-database-and-vector-extension.md)  
- [0003 调度](ADR/0003-scheduling.md)  
- [0004 模型抽象](ADR/0004-model-provider-abstraction.md)  
