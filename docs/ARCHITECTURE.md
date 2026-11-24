# 技术架构（ARCHITECTURE）

**版本：** 0.4（对齐 Blueprint V4）  
**权威：** [BLUEPRINT_V4.md](BLUEPRINT_V4.md)（§22+ 冲突优先）  
**风格：** Modular Monolith + Asynchronous Data Pipeline  
**研究查询路径：** `Country × Source × Topic × Target × Time`（默认 Target=China）  
**非目标：** 微服务、Kafka、Neo4j、Prefect（MVP 非强制）、Celery、Redis（非必要不引入）

---

## 1. 原则

1. 模块边界清晰，经明确接口交互  
2. 任务异步/可重试，单篇失败不中断整批  
3. PostgreSQL 为事实存储  
4. Adapter 插件化；来源配置进 Registry  
5. 模型供应商可替换  
6. 分析结果可追溯、可版本化  
7. 指标与预警阈值由可测试模块计算，非 LLM 直接出数  
8. 先可运行可测试，再增加分布式复杂度  
9. **Agent = 受控编排**，不是无限制聊天机器人  

---

## 2. 逻辑分层

```text
Source Layer        国家/组织/来源/合规属性
     ↓
Ingestion Layer     RSS / API / Web Adapter
     ↓
Processing Layer    提取、清洗、语言、时间、去重、质检
     ↓
Intelligence Layer  涉华片段、Relevance Weight、文章分析；Embedding/事件（Phase 2+）
     ↓
Metrics / Alert     确定性聚合、规则预警、重大新闻候选打分
     ↓
Storage Layer       PostgreSQL（+ pgvector Phase 2）
     ↓
Application Layer   FastAPI、Streamlit、报告投递、轻量任务编排
```

---

## 3. Agent / 编排边界（MVP）

| 角色（职责边界，非独立服务） | MVP |
|------------------------------|-----|
| Monitoring | 调度采集、重试、健康 |
| Article Intelligence | 调用分析管线 |
| News/Event Triage | **规则型**候选簇 |
| Trend & Alert | **规则引擎** |
| Reporting | 模板 + 可选 LLM 润色 + 证据校验 |
| Evidence QA | 数字/链接/引用核对 |

**开放式多步骤研究 Agent → Phase 3。** 工具调用须审计；Agent 不得改写原文、覆盖历史分析或静默改指标定义。

建议模块接口（ADR 草案，待标定）：Intelligence / Metrics / Alert / Reporting。

---

## 4. MVP 技术栈

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
| Scheduling | Cron / APScheduler | |
| LLM | DeepSeek 抽象层 | 可替换 |
| Embedding | BGE-M3 等 | Phase 2 重点 |
| Test | pytest | |
| Deploy | Docker Compose | |

---

## 5. 包结构

```text
src/gni/
  core/             配置、日志、异常
  sources/          来源注册与治理
  ingestion/        Adapter 与采集任务
  processing/       清洗与去重
  analysis/         LLM 分析 + relevance weight
  metrics/          指标计算
  alerts/           规则预警（P1-F）
  news/             重大新闻候选（P1-F）
  reports/          报告与证据校验
  api/              FastAPI
  dashboard/        Streamlit
  infrastructure/   DB 会话等
```

P1-A 已交付部分保持稳定；新增包在后续授权段引入。

---

## 6. Adapter 接口（设计）

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

---

## 7. 数据流（监测型 MVP）

`Fetch → Parse → Normalize → Extract → Relevance → Analyze → Quality Gate → Metrics → News Triage → Alerts → Report → Evidence Validation → Delivery`

每步可观测；ingestion_jobs / analysis_runs / metric_runs / alerts 留痕。

---

## 8. 时间

- 存储：UTC  
- 展示：用户或报告指定时区  
- 区分：event_time、published_at、first_seen_at、analyzed_at、updated_at  

---

## 9. 相关 ADR

- [0001 模块化单体](ADR/0001-modular-monolith.md)  
- [0002 数据库与向量扩展](ADR/0002-database-and-vector-extension.md)  
- [0003 调度](ADR/0003-scheduling.md)  
- [0004 模型抽象](ADR/0004-model-provider-abstraction.md)  
