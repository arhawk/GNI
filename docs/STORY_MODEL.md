# Story 概念模型（逻辑层）

**状态：** 概念冻结 · **无独立 Story 表**（Phase-1 / Batch3）  
**相关指标：** Unique Story Count（当前为 **hash MVP**）

---

## 1. 层级关系（多对多，非严格流水线）

```text
Article ──┐
          ├── Story ──┐
Article ──┘           ├── Event ──┐
                      │          ├── Narrative
Article ──────────────┘          │
                                 └── Narrative
```

| 层 | 含义 | 本阶段实现 |
|----|------|------------|
| **Article** | 一篇报道 | 表已有 |
| **Story** | 同一「新闻故事」的跨源/跨语言聚类（改写、转载、同题异写） | **仅概念**；Unique Story Count ≈ title/content hash 去重 |
| **Event** | 可指认的现实/政策行动（Actor–Action–Object + 时间/地点） | Fingerprint + `events` 表 |
| **Narrative** | 对事件的框架化讲述（frame / 立场 / 主题） | 分析结构化字段 + narrative clusters |

要点：

- **Story ≠ Event**：同一故事可覆盖多个事件；同一事件可被多个故事线追踪。
- **Article → Story → Event → Narrative** 是逻辑依赖，不是强制 ETL 顺序。
- 跨语言对齐、改写检测、正式 Story 服务 → **Phase 2+**。

---

## 2. Unique Story Count 局限（必须旁注）

当前实现：

- 单语（以英文种子为主）title/content **hash 聚类**
- **不**做跨语言、近义改写、图片/视频同源

因此指标旁注与报告文案应写明「hash MVP」，禁止写成「全球唯一故事数」。

---

## 3. 产品文案

- 监测范围：**MVP 五国监测样本**（美/俄/德/印/澳官媒与政府传播等）
- 禁止夸大：「全球舆论」「全世界对华态度」等
- 来源展示桶：国家控制媒体 / 公共服务媒体 / 政府传播（`ownership_type` + `government_control_level` + `feed_scope`）
- `GOVERNMENT_RELEASES` 可进事件，**不进入媒体情感主统计**（分栏）
