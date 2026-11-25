# 第三批产品接口说明（编码后置）

**状态：** **已实现**（Batch3：Meili 回退 ilike、周/月报 schema v1、Story 文档、来源文案）  
**对应：** 搜索、周月报、Story 概念、来源分区文案

---

## 1. Search

```text
Search API → Meilisearch（索引）→ Article/Event IDs → PostgreSQL（权威）
```

- 前端不直连 Meilisearch  
- 须有：增量同步、失败重试、全量重建  
- 当前 `ilike` 检索保留为过渡

---

## 2. Weekly / Monthly

按 [WEEKLY_REPORT_SPEC.md](WEEKLY_REPORT_SPEC.md)、[MONTHLY_REPORT_SPEC.md](MONTHLY_REPORT_SPEC.md) 实现；日报事实快照可落 `report_snapshots`。

---

## 3. Story 概念（逻辑层，非独立服务）

```text
Article → Story → Event → Narrative   （多对多，非严格流水线）
```

- Story ≠ Event  
- Unique Story Count 现为 hash MVP；文档须标明跨语言/改写局限  
- 正式 Story 表后置

---

## 4. 来源分区展示

报告与 Dashboard 区分：国家控制媒体 / 公共服务媒体 / 政府传播 /（未来）主流独立对照。  
政府公告可进事件，不与媒体报道混算情感/叙事。  
文案：**MVP 五国监测样本**，禁止写成「全球对华舆论」。
