# Phase 0 验收报告

**日期：** 2026-11-23  
**结论：** Phase 0 交付物已齐备，**停止**；进入 Phase 1 须用户明确授权。

---

## 1. 完成交付物

### 产品与研究

| 交付物 | 路径 |
|--------|------|
| 仓库审计 | docs/PHASE0_REPOSITORY_AUDIT.md |
| PRD | docs/PRD.md |
| 产品范围 | docs/PRODUCT_SCOPE.md |
| 开发计划 | docs/DEVELOPMENT_PLAN.md |
| 竞品分析 | docs/COMPETITIVE_ANALYSIS.md |
| 来源规范 | docs/SOURCE_REGISTRY.md |
| 合规 | docs/COMPLIANCE.md |
| 注册表模板 | docs/source_registry_template.csv |
| 候选来源表 | docs/source_candidates.csv（均为 unverified / TBD） |

### 分析与工程设计

| 交付物 | 路径 |
|--------|------|
| Taxonomy | docs/TAXONOMY.md |
| AI 分析 | docs/AI_ANALYSIS.md |
| 指标 | docs/METRICS.md |
| 可视化 | docs/VISUALIZATION_SPEC.md |
| 架构 | docs/ARCHITECTURE.md |
| 数据库 | docs/DATABASE.md |
| 数据 Schema 总览 | docs/DATA_SCHEMA.md |
| ERD | docs/ERD.mmd |
| 文章分析 JSON Schema | docs/ARTICLE_ANALYSIS_SCHEMA.json |
| 报告治理 | docs/REPORT_GOVERNANCE.md |
| ADR | docs/ADR/0001–0004 |

### 工程骨架

| 交付物 | 路径 |
|--------|------|
| 包定义 | pyproject.toml |
| 源码包 | src/gni/ |
| 环境样例 | .env.example |
| Docker Compose | docker-compose.yml |
| 测试 | tests/unit/ |
| README | README.md |
| .gitignore | .gitignore |

---

## 2. 未完成项及原因

| 项 | 原因 |
|----|------|
| 已核验的 15–25 个 RSS/API | 任务书禁止编造；核验属 Phase 1-A |
| Alembic 初版迁移 | Phase 0 仅占位 migrations/；表结构在文档冻结 |
| 真实 LLM / 采集 | Phase 0 明确禁止 |
| Git 远程与 Issues | 无 remote；未要求本阶段创建 |
| 加拿大来源 | 已移出短名单，仅扩展池一行 |

---

## 3. 最终技术选型（冻结）

- Modular Monolith + FastAPI + Streamlit + PostgreSQL  
- 调度：Cron / APScheduler（未实现完整调度）  
- LLM：DeepSeek 抽象；Embedding/pgvector：Phase 2  
- Python：3.12（推荐）；本机 3.14 非推荐  

---

## 4. MVP 数据模型摘要

来源治理 + 文章 + 分析版本/证据 + taxonomy + metric_runs + reports/claims/evidence + ingestion_jobs。  
事件与 story_clusters **仅规划，不预建空表**。

---

## 5. 来源候选评估进度

- 短名单：US / RU / DE / IN / AU  
- 接通顺序：美 → 俄 → 德 → 印 → 澳  
- CSV 已登记候选名称与官网 hint；**feed 全部 TBD，verification_status=unverified**  
- 俄、印标 high risk  

---

## 6. 未解决问题（TBD）

1. 各候选源实测 RSS/API 与条款摘录  
2. 「中国相关」文章过滤规则细则  
3. 正文/证据保留天数  
4. 印地语等 taxonomy 译名  
5. User-Agent 字符串与请求速率默认值  

---

## 7. 测试与启动命令

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
gni health
gni version
# 可选：docker compose up -d db
```

### 测试结果（2026-11-23）

```text
pip install -e ".[dev]"  # 成功
pytest                   # 6 passed in 1.07s
gni health               # status=ok, llm_api_configured=false
gni version              # 0.1.0
```

说明：本机执行环境为 Python 3.14.6；项目推荐使用 3.12（见 README）。未启动 Docker、未连接真实 LLM、未进行媒体采集。

---

## 8. Git 变更摘要

Phase 0 新增 docs/、src/gni/、tests/、pyproject.toml、docker-compose.yml、README 等。  
**未自动 commit / push**（除非用户另行要求）。

---

## 9. Phase 1 建议任务拆分

1. 按顺序核验美国候选 RSS/API，至少接通 5 源中的首批  
2. Source Registry CRUD + 审核字段落库  
3. RSS Adapter + ingestion_jobs  
4. Processing 管道与 articles 入库  
5. LLM Provider 实装 + article_analyses（含预算）  
6. 基础 metric_runs + Streamlit 四页  
7. 日报/周报 + report_claims 证据校验  

---

## 10. 验收清单勾选

### 产品与研究

- [x] 产品定位和目标用户明确  
- [x] Phase 1/2/3 边界明确  
- [x] MVP 功能与非目标明确  
- [x] 竞品分析完成  
- [x] 首批国家与来源候选有评估依据（候选表，未伪造 feed）  
- [x] 来源治理和合规流程明确  

### 分析与指标

- [x] 三层边界明确  
- [x] Sentiment 与 Stance 分离  
- [x] Stance Target 词表明确  
- [x] Topic Taxonomy 初版  
- [x] 指标分母/Unknown/去重口径有定义  
- [x] Dashboard 页面与图表类型明确  
- [x] 综合指数不属于 MVP  

### 技术与数据

- [x] Modular Monolith 明确  
- [x] 选型有 ADR  
- [x] 时间统一 UTC  
- [x] 去重分阶段策略明确  
- [x] MVP ERD 完成  
- [x] 文章分析 Schema 草案完成  
- [x] 版本管理明确  
- [x] LLM 成本控制策略明确  
- [x] 报告证据约束明确  

### 工程

- [x] 未无理由覆盖既有业务文件（绿场）  
- [x] Python 包可安装（见测试）  
- [x] 配置和日志入口存在  
- [x] `.env.example` 无真实密钥  
- [x] pytest 可运行  
- [x] 本地启动方式写入 README  
- [x] 本验收报告完成  
- [x] **未擅自开始 Phase 1 业务实现**  

---

**Phase 0 结束。等待用户明确授权后再开始 Phase 1。**
