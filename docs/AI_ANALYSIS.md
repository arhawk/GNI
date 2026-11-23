# AI 分析规范（AI_ANALYSIS）

**版本：** analysis_design_v0.1  
**相关：** [ARTICLE_ANALYSIS_SCHEMA.json](ARTICLE_ANALYSIS_SCHEMA.json)、[TAXONOMY.md](TAXONOMY.md)

---

## 1. 三层边界

| 层 | 含义 | 阶段 |
|----|------|------|
| Article | 单篇文章表达了什么 | MVP |
| Event | 同一事件跨来源如何报道 | Phase 2 |
| Narrative | 国家/来源集合一段时间如何持续描述 | Phase 2 起逐步启用 |

禁止把单篇结论直接升格为国家级叙事结论。

---

## 2. 分级处理

1. **规则层：** URL 规范化、HTML 清洗、语言识别、时间提取、Hash 去重  
2. **轻量模型层：** Embedding、相似召回、简单筛选（Phase 1 可选 / Phase 2 重点）  
3. **LLM 结构化分析层：** 主题、情感、立场、框架、实体、证据  
4. **复杂分析层：** 模糊判断、跨文章比较、事件关系 — **按需触发**  

达到预算上限时：**优先保证采集与存储**，暂停低优先级分析。

---

## 3. 文章级分析字段（MVP）

| 组 | 内容 | 约束 |
|----|------|------|
| 主题 | primary_topic、secondary_topics | 受控词表；多标签 |
| 情感 | sentiment、emotions[]、intensity | ≠ 立场 |
| 立场 | targets[]：target_id、stance、strength | 必须绑定 Target |
| 框架 | primary_frame、secondary_frames | 允许多标签与 unknown |
| 实体 | persons/orgs/countries/policies… | 保留原文与规范化 |
| 证据 | evidence_spans：quote、定位、关联字段 | 可定位原文 |
| 显著性 | topic_prominence | 核心 vs 顺带提及 |
| 置信度 | per_field_confidence | 禁止强行猜测 |
| 状态 | known / unknown / ambiguous / insufficient_evidence / not_applicable | 允许空判 |

Schema 详见 JSON Schema 文件。

---

## 4. 模型抽象

```text
BaseLLMProvider
  analyze(article, schema, prompt_version) -> StructuredResult
  generate(...)  # 报告等，非统计计算
  embed(...)     # Phase 2 重点；Phase 1 可后接
```

业务代码不得直接绑定某一供应商。默认候选：DeepSeek API；Embedding 候选 BGE-M3。

---

## 5. 版本与成本记录

每次分析写入：

- model_name / model_version  
- prompt_version / schema_version / taxonomy_version  
- analysis_status、token_usage / estimated_cost、confidence、created_at  
- structured_result（JSONB）  

**禁止静默覆盖**旧分析结果；新版本追加。

成本控制：Content Hash Cache、Analysis Version Cache、Batch、Retry/Backoff、Failure Fallback、Daily Budget、Per-article Token Limit、Daily Article Limit、Priority Queue。

---

## 6. 证据机制

结论示例：「该文采用国家安全框架」必须附：

- 原文引用片段  
- 段落/偏移或可定位标识  
- 对应标签  
- 置信度  

无证据的字段应标 `insufficient_evidence`，不得编造引用。

---

## 7. 质量评估

建立人工抽样评估集，分别评估：主题、情感、立场、框架、Evidence Span 定位。  

- 正文提取失败 → **数据质量**  
- 模型判断错误 → **分析质量**  

二者分开统计，不得混为单一「准确率」对外宣传。

---

## 8. 明确禁止

- 用 LLM 直接输出 Attention / Narrative Shift / Risk 等正式指标数值  
- 为填满字段强制分类  
- 无版本信息的分析结果进入正式报告  
