# Event Fingerprint（事件指纹）MVP

**版本：** 0.1  
**对齐：** [EVENT_INTELLIGENCE_IA.md](EVENT_INTELLIGENCE_IA.md)、[DATA_LAYERS.md](DATA_LAYERS.md)、Blueprint Phase 1 proto / Phase 2 完整事件  
**原则：** 先把新闻压成结构化事件信息再匹配；仅歧义时 LLM 读卡（或必要时回原文）。不宣称完整 Phase 2 图谱。

---

## 1. 两个概念（勿混）

| 对象 | 回答 | 存储 |
|------|------|------|
| **Article Information Card** | 这篇文章报道了什么（六维分析） | `article_analyses.structured_result` |
| **Event Fingerprint** | 文中发生了哪个具体行动节点 | `article_event_candidates` → 归一后进 `events` |

一文可多事件；一事件可多文。

---

## 2. Fingerprint 字段（8 组）

### 核心身份（最重要：Actor + Action + Object）

| 字段 | 含义 |
|------|------|
| actor | 谁行动 |
| action | 做什么 |
| object | 对什么 |
| event_time | 事件发生/宣布时间（≠ published_at） |

### 辅助区分

| 字段 | 含义 |
|------|------|
| target | 针对谁 |
| event_type | 政策宣布 / 外交回应 / … |
| location | 发生地或宣布地（类型化） |
| qualifiers | 政策名、产品、金额、状态等 |

### 描述性（不硬匹配）

`event_summary`、证据句、字段置信度。

---

## 3. 流水线（MVP）

1. **Extract** — 标题 + 涉华 spans → `article_event_candidates`（追加）  
2. **Canonicalize** — 动作同义表 + 小写/token；`actor_key` / `action_key` / `object_key` / `fingerprint_hash`  
3. **Match** — 规则：同 action_key + object 重叠 + \|Δt\|≤72h；**Actor 不同默认不是 SAME**  
4. **Ambiguous** — 中等分才 LLM：`SAME_EVENT | RELATED_SUB_EVENT | SAME_TOPIC_DIFFERENT_EVENT | UNRELATED | INSUFFICIENT`  
5. **Link** — 写 `events` + `event_articles`；可选地点  
6. **Rollup** — 文章情感/立场按篇数占比 → 事件 / 国家×事件；国家对华态度快照  

CLI：`gni events rebuild`（fingerprint 默认）；`--legacy-title` 回退旧标题 Jaccard。

**本轮不做：** Embedding 召回、完整实体 KB。

---

## 4. 地图语义（互斥）

| 模式 | 含义 |
|------|------|
| `event_geography` | 事件发生/宣布地钉（无坐标不进图） |
| `country_china_attitude` | 监测国媒体对华情感汇总色（无样本灰不可点） |

文案必须标明：态度色 = **被监测官媒样本**，非国家官方立场。禁止把报道国当成事件发生地。

---

## 5. 报告口径（数据支撑）

日报/周报：**事件为主线，文章为证据**；同时保留文章量统计。三种时间分清：`published_at` / `event_time` / `first_seen_at`。未聚合文章进 Emerging / Unresolved，不丢弃。
