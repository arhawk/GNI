# 开发实施计划（DEVELOPMENT_PLAN）

**产品：** GNI  
**版本：** Phase 0 冻结稿  
**说明：** 阶段表示能力交付顺序，不是固定人周工期。

---

## 1. 总原则

**数据基建 → 可验证文章分析 → 可比较统计 → 事件与长期叙事 → 研究 Agent**

- 不允许一次实现全部阶段  
- 每次只推进当前授权阶段  
- 不硬编码国家/媒体/模型供应商  
- 不允许 LLM 直接生成正式统计指标数值  
- 无证据的事实性结论不得进入正式报告  

---

## 2. Phase 0：需求冻结与工程初始化（当前）

### 交付

- 仓库审计、PRD、范围、竞品、来源治理、合规  
- Taxonomy、指标、可视化、AI 分析、架构、ERD、ADR  
- 最小可安装工程骨架、pytest、`.env.example`  
- `PHASE0_ACCEPTANCE.md`  

### 不做

生产采集、完整 LLM 流水线、事件聚类、正式日报发送、Phase 1 业务实现。

### 验收

见任务书 Phase 0 验收清单；通过后**停止**，等待用户明确授权 Phase 1。

---

## 3. Phase 1：可信数据与基础分析（MVP）

### P1-A 来源注册与采集

- 来源管理、BaseAdapter、RSS（主）、API/Web 基础  
- 调度（Cron / APScheduler）、重试、健康监控  
- **验收：** ≥5 个来源连续运行；失败可定位可重试  
- **接通顺序：** 美 → 俄 → 德 → 印 → 澳  

### P1-B 文章处理与存储

- 正文提取、规范化、语言、UTC、URL/Hash 去重、单语言近重、质量检查  
- **验收：** 可回溯 URL；关键字段完整；重复不重复进统计  

### P1-C 文章级分析

- Schema、模型抽象、主题/情感/立场/框架/实体/证据、Unknown、版本与预算  
- 人工抽样评估集  
- **验收：** 每条分析有版本；证据可定位原文  

### P1-D 指标、Dashboard 与报告

- 主题/情感/立场/基础框架分布、质量面板、日报周报、证据校验  
- **验收：** 口径/分母/时区清楚；事实有证据；样本不足有提示  

---

## 4. Phase 2：事件与叙事智能

- 跨语言转载、Embedding、事件召回与聚类、关系与生命周期  
- 人工合并/拆分、事件级指标、跨国叙事差异  
- 历史基线、Narrative Shift、基础异常检测  
- **验收：** 标注集评估；优先控制 False Merge；样本条件满足才启用异常判断  

---

## 5. Phase 3：研究型 Agent

- 自然语言查询工具链、跨国比较、专题流程、证据验证器  
- 可配置综合指数与告警  
- **验收：** 不得虚构数据库事实；正式结论经证据验证  

---

## 6. 工程管理建议

| 实践 | 说明 |
|------|------|
| Issues | Epic / Feature / Task / Bug（可选，有 remote 后启用） |
| ADR | 重要技术决策必须记录 |
| Migration | 所有数据库变更有迁移 |
| 测试 | 关键逻辑单测；分析与聚类有评估测试 |
| 合成数据 | 必须标注 Synthetic |

---

## 7. Phase 1 建议任务拆分（Phase 0 结束后参考）

1. 核验 `source_candidates.csv` 中美国优先候选的 RSS/API  
2. 实现 Source Registry CRUD 与审核字段  
3. 实现 RSS Adapter + ingestion_jobs  
4. 实现 processing 管道与 articles 入库  
5. 实现 LLM Provider 抽象与 article_analyses  
6. 实现基础 metric_runs 与 Streamlit 四页  
7. 实现日报/周报生成与 report_claims 校验  

具体 Issue 在授权 Phase 1 后创建。
