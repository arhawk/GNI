# Phase 1 任务书（P1-A ～ P1-D）

**产品：** Global Narrative Intelligence（GNI）  
**状态：** 已授权启动；本文件为 Phase 1 执行与验收总纲  
**依据：** [PRD.md](PRD.md)、[PRODUCT_SCOPE.md](PRODUCT_SCOPE.md)、[DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md)、Blueprint V2  
**接通顺序：** 美 → 俄 → 德 → 印 → 澳  
**文档语言：** 中文  

---

## 0. 总原则

1. 按 **P1-A → P1-B → P1-C → P1-D** 顺序交付；每段验收通过后再开下一段。  
2. **禁止编造** RSS/API 地址或「已可采集」状态。  
3. 不为凑数降低来源准入；俄/印高风险源失败则记录，不强爬。  
4. 情感 ≠ 立场；立场必须绑定 Target；综合舆情总分 **不做**。  
5. LLM **不得**直接生成正式统计指标数值。  
6. 无证据的事实性结论不得进入正式报告。  
7. DB 存 UTC；所有库变更必须有 Migration。  

```text
P1-A 来源与采集 → P1-B 处理与入库 → P1-C 文章分析 → P1-D 指标/Dashboard/报告
```

---

## P1-A：来源注册与采集

### 目标

建立可审计的来源体系与可插拔采集，优先 RSS，支持作业状态、重试与来源健康监控。

### 输入依赖

- Phase 0 文档与工程骨架  
- [source_candidates.csv](source_candidates.csv)、[SOURCE_REGISTRY.md](SOURCE_REGISTRY.md)、[COMPLIANCE.md](COMPLIANCE.md)  

### 范围 / 交付物

| 项 | 说明 |
|----|------|
| 来源核验 | ≥5 个真实可访问 RSS；更新候选表与种子配置 |
| 数据表 | countries、organizations、sources、source_reviews、source_attribute_history、source_health、ingestion_jobs、articles（RSS stub） |
| Adapter | BaseAdapter + RssAdapter；Api/Web 仅占位 |
| 编排 | 按 active 源采集 → job 记录 → upsert articles → 更新 health |
| CLI | `gni db upgrade`、`sources seed/list`、`ingest run/health` |
| 调度 | CLI `--once` + cron 文档；APScheduler 可选 |

### 明确不做

全文 HTML 深度提取、近重、LLM、指标/Dashboard/报告、事件聚类。

### 验收清单

- [x] ≥5 个 `verified` 且可 `active` 的 RSS 源  
- [x] `gni ingest run --once` 写入 job + articles stub + health  
- [x] 失败可在 job/health 定位；重试可测  
- [x] pytest 通过  
- [x] [PHASE1A_ACCEPTANCE.md](PHASE1A_ACCEPTANCE.md) 完成  
- [x] **未**实现 P1-B/C/D 业务  

### 退出标准

验收报告通过后停止；等待用户明确授权 P1-B。详见 [PHASE1A_ACCEPTANCE.md](PHASE1A_ACCEPTANCE.md)。

---

## P1-B：文章处理与存储

### 目标

将 RSS stub / 原始抓取规范为可研究文章层：正文提取、清洗、语言、UTC、去重与质量检查。

### 输入依赖

- P1-A 验收通过；articles stub 可持续写入  

### 范围 / 交付物

| 项 | 说明 |
|----|------|
| 处理管道 | Fetch 正文（若需）→ Extract → Normalize → Language → Time → Dedup → Persist |
| 去重 | URL 规范化、content/title Hash、单语言近似去重 |
| 版本 | article_versions；原始与清洗分存 |
| 质量 | quality_status、字段完整率进 source_health / 质量统计 |
| CLI | `gni process run`（或等价） |

### 明确不做

跨语言转载识别（Phase 2）、LLM 分析、报告。

### 验收清单

- [ ] 文章可按国家/来源/时间查询，URL 可回溯  
- [ ] 关键字段完整；重复采集不重复进入统计口径  
- [ ] 单篇失败不中断整批  
- [ ] 处理相关单测 + 验收文档  
- [ ] **未**实现 P1-C/D  

### 退出标准

P1-B 验收通过后停止；等待授权 P1-C。

---

## P1-C：文章级 AI 分析

### 目标

对规范化文章输出可版本化、带证据的结构化分析（主题/情感/立场/框架/实体）。

### 输入依赖

- P1-B 验收；[ARTICLE_ANALYSIS_SCHEMA.json](ARTICLE_ANALYSIS_SCHEMA.json)、[TAXONOMY.md](TAXONOMY.md)、[AI_ANALYSIS.md](AI_ANALYSIS.md)  
- 可用的 LLM API Key（默认 DeepSeek 抽象）  

### 范围 / 交付物

| 项 | 说明 |
|----|------|
| Provider | BaseLLMProvider 实装（非 Null）；Mock 用于测试 |
| 表 | article_analyses、article_evidence、analysis_runs、model/prompt_versions、taxonomy 种子 |
| 能力 | 主题、情感、Target-bound Stance、框架、实体、证据、Unknown 状态 |
| 成本 | Hash/版本缓存、日预算、Token 上限、失败降级 |
| 评估 | 小规模人工/合成标注集（Synthetic 须标注） |

### 明确不做

Narrative Shift / Risk 正式计算、事件聚类、综合分、无证据强分类。

### 验收清单

- [ ] 输出符合 Schema；立场绑定 Target  
- [ ] 证据可定位原文；模型/Prompt/Schema/taxonomy 版本入库  
- [ ] 预算触顶时停分析不停采集  
- [ ] 数据质量与分析质量分计  
- [ ] **未**实现完整 Dashboard/正式报告流水线（属 P1-D）  

### 退出标准

P1-C 验收通过后停止；等待授权 P1-D。

---

## P1-D：指标、Dashboard 与报告

### 目标

可解释基础统计 + Streamlit 四页 + 日报/周报，事实结论绑定证据。

### 输入依赖

- P1-C 验收；[METRICS.md](METRICS.md)、[VISUALIZATION_SPEC.md](VISUALIZATION_SPEC.md)、[REPORT_GOVERNANCE.md](REPORT_GOVERNANCE.md)  

### 范围 / 交付物

| 项 | 说明 |
|----|------|
| 指标 | TopicShare、SentimentShare、StanceShare、FrameShare、Attention 基础计数；metric_runs 含分母 |
| Dashboard | 全球总览、国家分析、数据质量、报告 |
| 报告 | 日报/周报；report_claims + 证据校验器 |
| 冷启动 | 0–30 天不发布确定性异常结论 |

### 明确不做

黑盒综合分、Narrative Shift 正式基线异常、研究型 Agent、事件页（Phase 2）。

### 验收清单

- [ ] 比例展示分母、时区、来源范围、metric 版本  
- [ ] 质量面板与舆情结论分区  
- [ ] 正式报告事实结论有证据；无证据被拒绝  
- [ ] 样本不足有提示  
- [ ] MVP Phase 1 总验收对照 [PRD.md](PRD.md) §7  

### 退出标准

P1-D 通过即 **Phase 1 / MVP** 完成；Phase 2 须另行授权。

---

## 跨段禁止项（全程）

- 微服务 / Kafka / Neo4j / Prefect（非必要）  
- 伪造新闻作为正式数据  
- 静默覆盖分析结果或指标定义  
- 把采集失败造成的样本变化解释为舆情变化  

---

## 建议授权节奏

| 回合 | 交付 |
|------|------|
| 当前 | 本任务书 + **P1-A 实现与验收** |
| 下次 | 用户授权后 P1-B |
| 其后 | P1-C → P1-D |

---

## 相关验收文档

- P1-A：`PHASE1A_ACCEPTANCE.md`（本轮产出）  
- P1-B/C/D：各自 `PHASE1{B,C,D}_ACCEPTANCE.md`（对应段结束时产出）  
