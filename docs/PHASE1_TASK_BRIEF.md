# Phase 1 任务书（监测型 MVP：P1-A ～ P1-F）

**产品：** Global Narrative Intelligence（GNI）  
**状态：** V4 对齐；P1-A 已验收  
**依据：** [BLUEPRINT_V4.md](BLUEPRINT_V4.md)（§22+）、[PRD.md](PRD.md)、[PRODUCT_SCOPE.md](PRODUCT_SCOPE.md)  
**接通顺序：** 美 → 俄 → 德 → 印 → 澳  
**文档语言：** 中文  

---

## 0. 总原则

1. 按 **P1-A → B → C → D → E → F** 顺序交付；每段验收后再开下一段。  
2. Central Target = **China**；维度 Country × Source × Topic × Target × Time。  
3. **禁止编造** feed；不为凑数降低准入。  
4. 情感 ≠ 立场 ≠ 新闻重要性 ≠ 突发性；Stance 绑定 Target；**不做**黑盒综合分。  
5. LLM **不得**直接生成正式指标数值。  
6. 无证据事实结论不得进正式报告。  
7. DB 存 UTC；库变更必须有 Migration。  
8. **P1-A 采集栈不重写**（全量 stub 服务 Attention 分母）。  
9. MVP Agent = 确定性流水线 + 规则预警 + 模板/辅助报告；**开放式研究 Agent → Phase 3**。  

```text
A 采集 → B 处理 → C 涉华理解+Weight → D 原始/加权指标 → E V4 Dashboard → F 报告+规则预警+重大新闻候选
```

---

## P1-A：来源注册与采集（已完成）

- **验收门槛：** ≥5 **监测国家**各 ≥1 个 verified+active RSS  
- **交付：** Registry、RSS Adapter、jobs/health、articles `rss_stub`、CLI  
- **验收：** [PHASE1A_ACCEPTANCE.md](PHASE1A_ACCEPTANCE.md)  

---

## P1-B：文章处理与存储（+ 规则型 L1）

### 目标

- 正文 HTTP 提取、清洗、语言检测、UTC、URL/Hash、单语言近重、质量检查  
- `article_versions` 保留清洗正文版本  
- **规则型 L1 标题初筛**（词典/别名；无 LLM）：`explicit_relevant / likely_relevant / no_match / uncertain`；`no_match` **不**永久丢弃  
- 依据：[BLUEPRINT_V4_ADDENDUM_A1.md](BLUEPRINT_V4_ADDENDUM_A1.md)

### 验收

- 可按国家/来源/时间查询，URL 可回溯  
- 重复不进主统计口径（标记清晰）；单篇失败不中断整批  
- L1 结果可查；**未**实现 L2/L3/LLM Weight（属 P1-C）  

---

## P1-C：L2/L3 与 China Relevance Weight + 六维分析

### 目标

- **L2** 正文涉华判断；**L3** 涉华片段提取与原文定位校验  
- `china_relevance_level` / `china_relevance_weight`（Addendum 等级：core/substantial/secondary/incidental/none/uncertain）  
- Topic；Sentiment（含可选连续分）；**Target-bound Stance**；Frame（`taxonomy_v0.4`）；Entities；Claims/Evidence  
- Unknown / Mixed / Ambiguous 等状态；版本与预算  

### 验收

- Schema 合规（见 ARTICLE_ANALYSIS_SCHEMA）；Stance 绑定 Target  
- Weight 与 Article Count 分开保存；证据可定位  
- model/prompt/schema/taxonomy/weight 版本入库  
- 预算触顶停分析不停采集  
- **未**实现完整指标/Dashboard/报告流水线  

---

## P1-D：研究指标 + 加权/运营监测指标

### 目标

实现 [METRICS.md](METRICS.md)：七项研究核心 + Weighted Volume/Score/Distribution、N/P Ratio 等；**原始+加权双视图**。

### 验收

- 每项有 numerator/denominator/范围/去重/版本  
- Attention Share：分母 = 同源全量有效报道；不可靠则**禁止正式发布**  
- 单元测试覆盖口径；**非** LLM 算分  
- **未**要求完整 Streamlit 全导航（属 P1-E）  

---

## P1-E：Dashboard（V4 导航）

### 目标

按 [DASHBOARD.md](DASHBOARD.md) 交付：

1. Overview  
2. Countries  
3. News & Events（**候选列表**）  
4. Articles  
5. Reports（入口可先列表）  
6. Alerts（入口可先列表）  
7. Sources & Quality  
8. Research（可占位）  

全局筛选默认 Target=China；raw/weighted 并列；可下钻文章/证据。

### 验收

- 上述主页可筛选；情感与立场分图  
- 质量与舆情分区  
- 图表标注样本量、加权量与分母  

---

## P1-F：报告、规则预警与重大新闻候选

### 目标

- 日报 / 周报 / 月报模板 + report_claims 证据校验  
- 规则型 Alerts（[ALERTS.md](ALERTS.md)）：量激增、负面占比升、多国覆盖、来源故障等；去重与状态  
- **规则型重大新闻候选**（时间窗 + 标题/实体/关键词相似度 + 简单打分）；**非**完整事件聚类  

### 验收

- 事实结论有证据；无证据拒绝发布  
- 样本不足 / 冷启动有提示  
- 预警含触发规则、基线、样本与代表文章  
- 对照 [PRD.md](PRD.md) MVP 清单收口  

### 退出标准

P1-F 通过即 **Phase 1 / 监测型 MVP** 完成；Phase 2 另授权。

---

## 跨段禁止项

微服务 / Kafka / Neo4j / 非必要 Prefect；伪造正式数据；静默覆盖分析/指标；把采集故障解释为舆情变化；用负面分代替重大新闻判断。

---

## 授权节奏

| 段 | 状态 |
|----|------|
| P1-A | 已完成（不重写） |
| P1-B | 已完成 |
| P1-C | 完成（启发式默认；DeepSeek 可选） |
| P1-D | 完成（指标 JSON/`metric_runs`；无看板） |
| P1-E | 完成（Streamlit 八页；News/Reports/Alerts 占位至 P1-F） |
| P1-F | 待授权 |

验收文档：`PHASE1{A,B,C,D,E,F}_ACCEPTANCE.md`。
