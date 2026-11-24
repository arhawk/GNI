# AI 分析规范（AI_ANALYSIS）

**版本：** analysis_design_v0.5（对齐 Blueprint V4 §23–25 + 数据五层）  
**相关：** [ARTICLE_ANALYSIS_SCHEMA.json](ARTICLE_ANALYSIS_SCHEMA.json)、[TAXONOMY.md](TAXONOMY.md)、[METRICS.md](METRICS.md)、[DATA_LAYERS.md](DATA_LAYERS.md)

**输入前提（数据层）：** 标准化正文（Layer 2）+ 涉华筛选/片段（Layer 3）；分析结果写入 Layer 4（`article_analyses` **追加**，保留 model/prompt 版本）。筛选 L1/L2/L3 ≠ 本节「分析单位三层」。

---

## 1. 三层边界

| 层 | 含义 | 阶段 |
|----|------|------|
| Article | 单篇文章涉华内容表达了什么 | MVP |
| News candidate | 规则/相似度热点簇 | MVP（非完整事件） |
| Event / Narrative | 跨来源事件与长期叙事 | Phase 2+ |

禁止把单篇结论直接升格为国家级叙事结论。

---

## 2. 推荐流程（含三级筛选）

详见 [BLUEPRINT_V4_ADDENDUM_A1.md](BLUEPRINT_V4_ADDENDUM_A1.md)：

`采集持久化 → 规范化 → L1 标题初筛（调度） → 正文提取 → L2 正文涉华判断 → L3 片段提取 → Relevance Level/Weight → Topic/Target → Sentiment/Stance → Frame/Claims/Evidence → 质检 → 聚合`

- L1：**不**终裁；`no_match` 不永久丢弃（P1-B 规则实现）  
- L2/L3 + Weight：P1-C  
- **不得**先压缩成摘要再只根据摘要打全部标签  

---

## 3. 分级处理

1. **规则层：** URL、HTML、语言、时间、Hash 去重  
2. **轻量模型层：** Embedding、相似召回（P1 可选 / P2 重点）  
3. **LLM 结构化层：** 涉华片段、Weight 特征、Topic、Sentiment、Stance、Frame、Entities、Evidence  
4. **复杂分析层：** 跨文章比较、完整事件关系 — **按需 / Phase 2+**  

预算触顶：**优先采集与存储**，暂停低优先级分析。

---

## 4. China Relevance Weight

| 字段 | 说明 |
|------|------|
| level | core / major / moderate / minor / incidental / not_relevant |
| weight | `w ∈ [0,1]`，由规则映射，版本化 |
| estimated_share | 涉华内容比例估计；**≠** 最终 weight |
| 特征 | title/lead prominence、primary_subject、argument_centrality 等 |
| rationale / confidence | 必填可审计 |

MVP 用可解释规则/等级映射；**provisional** 中点与纳入规则见 [PROVISIONAL_CALIBRATION.md](PROVISIONAL_CALIBRATION.md)。公开集（如 GDELT_chinaNews）仅作评测代理。低相关（incidental）默认保留库内但排除核心舆情纳入。

---

## 5. 文章级分析字段（MVP）

| 组 | 内容 | 约束 |
|----|------|------|
| 相关度 | level、weight、特征、理由 | 与计数分离 |
| 主题 | primary / secondary | taxonomy_v0.4 |
| 情感 | label、可选 score∈[-1,1]、intensity | ≠ 立场；优先基于涉华片段 |
| 立场 | target_id + stance | 必须绑定 Target；区分媒体叙述 vs 引述 |
| 框架 | primary / secondary | v0.4 Frame 词表 |
| 实体 / Claims | 原文与规范化 | |
| 证据 | quote + 定位 + 关联字段 | 可定位原文 |
| 状态 | known / unknown / ambiguous / mixed / insufficient_evidence / not_applicable | 禁止强行填满 |

Schema 详见 JSON Schema（`article_analysis_v0.2` 草案字段含 weight/level）。

---

## 6. 模型抽象

```text
BaseLLMProvider
  analyze(article, schema, prompt_version) -> StructuredResult
  generate(...)  # 报告润色等，非统计计算
  embed(...)     # Phase 2 重点；Phase 1 可后接
```

业务代码不得直接绑定某一供应商。

---

## 7. 版本与成本

每次分析写入：model / prompt / schema / taxonomy / **relevance_weight_version** / analysis_status / token / cost / confidence / structured_result。

**禁止静默覆盖**旧结果；新版本追加。

---

## 8. 证据与质量

重要判断必须附原文片段与定位。正文失败 → 数据质量；模型错误 → 分析质量；分开统计。

---

## 9. 明确禁止

- 用 LLM 直接输出 Attention / Weighted Score / Alert 触发值等正式指标  
- 把引用第三方观点自动当作媒体自身立场  
- 用负面分代替重大新闻判断  
- 无版本信息的分析结果进入正式报告  
