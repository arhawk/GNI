# 对华舆情日报格式与生成规则（冻结 v1）

**版本：** daily_report_schema_v1  
**对齐：** [REPORT_GOVERNANCE.md](REPORT_GOVERNANCE.md)、[METRICS.md](METRICS.md)、七段舆情骨架  
**原则：** **规则算数 → 结构化 JSON →（可选）LLM 只写叙述句**；LLM **不得**改写任何数字、ID、标签计数。

---

## 1. 报告固定七段（每次必须生成）

| # | 章节 | 必须回答的问题 | 数据来源（规则） | LLM 可写？ |
|---|------|----------------|------------------|------------|
| 1 | 口径 | 这是什么样本？不是什么？ | 固定文案 | 否（固定句） |
| 2 | 今日对华关注 | 多少篇？占比？各国覆盖？缺分析多少？ | metric + 分国计数 | 可写 1 句「读数提示」 |
| 3 | 语气与立场（分国） | 各国情感表、立场表 | 已分析涉华文章聚合 | 可写各国差异 1 句 |
| 4 | 议题与说法 | 主议题 TopN、主框架 TopN | topic/frame primary 计数 | 可写差异 1 句 |
| 5 | 事件主线 | 为何变化？按时间的事件 + 多源证据 | events + articles | 可写事件摘要句（须挂 evidence） |
| 6 | 代表证据 | 每国 3–5 条可点原文 | 抽样文章 | 否（只列 Fact） |
| 7 | 质量与限制 | 积压、源健康、无样本国 | queue/health | 可写限制说明，不得美化缺口 |

**禁止：** 合成「对华舆情总分」；把媒体样本写成国家立场/民意；无 `article_id` 的事实句。

---

## 2. 结构化 JSON 形状（`daily_report_schema_v1`）

```text
disclaimer          # §1 固定口径
sections.attention  # §2 coverage_by_country, totals, missing_analysis, attention_share?
sections.tone       # §3 by_country sentiment_counts + stance_counts, overall
sections.agenda     # §4 topics_top, frames_top, by_country brief counts
sections.events     # §5 time-ordered events with multi-source evidence (+ sentiment/stance)
sections.evidence   # §6 per-country 3–5 articles with article_id/url
sections.quality    # §7 missing, source_health, countries_without_sample, notes
narratives          # 可选：LLM 生成的短句，键与章节对应；缺省则用规则短句
```

---

## 3. 生成流水线

1. **Rule assemble** — `build_daily_report()` 只读 DB/指标，填满七段数字与证据 ID。  
2. **Rule narratives（默认）** — 用模板拼 1 句差异（例如「RU 中性占比最高」），不调用 LLM。  
3. **Optional polish** — `gni reports daily --polish`：把 JSON 中的计数表交给 LLM，只返回 `narratives.*` 字符串；校验后不得含新数字（简单守卫：禁止出现未在 facts 中出现的整数）。  
4. **Render** — Markdown / Report center 按七段渲染；页面与文件同源 JSON。

---

## 4. 与「图片能力菜单」的映射（进日报的）

进：关注度、情感、立场、议题、框架、媒体覆盖、轻量事件/多源证据。  
不进日报核心：社交声量、冲突伤亡、综合声誉风险分、完整实体图谱。

---

## 5. 验收

- 任意一天生成的 JSON 含齐七段键。  
- §3 情感表与立场表分列。  
- §5/§6 每条 Fact 有 `article_id`。  
- `--polish` 开关关闭时仍可完整出报。
