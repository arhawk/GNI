# 事件情报信息架构（Event / Geography / Narratives）

**版本：** 0.1（2026-11-24）  
**权威对齐：** [BLUEPRINT_V4.md](BLUEPRINT_V4.md)、[DASHBOARD.md](DASHBOARD.md)、[TAXONOMY.md](TAXONOMY.md)  
**原则摘要：** 地图答 Where；国家视图答 Who reports；叙事视图答 How they frame；三者共享一个 Event。

---

## 1. 三分概念（禁止混用）

| 概念 | 回答的问题 | 示例 |
|------|------------|------|
| 事件发生地 | 事情在哪里发生 / 宣布 / 影响？ | 北京、布鲁塞尔、台湾海峡 |
| 事件参与方 | 谁参与了这件事？ | 中国、欧盟 |
| 媒体叙事来源 | 哪个国家的哪家媒体如何报道？ | 美国 VOA、德国 DW |

**媒体所属国家 ≠ 媒体观点 ≠ 该国政府立场。**

因多国报道而复制多个 Event ID → **禁止**。  
把报道来源国当成事件发生地钉在同一语义图层 → **禁止**。

---

## 2. 六条设计原则

1. 一个真实事态只建立一个核心 **Event ID**。  
2. 地理位置是事件**属性**，不是分类主键；可多地点，也可无明确物理坐标。  
3. 国家是媒体**来源维度**，不代表官方立场；保留媒体级差异。  
4. 叙事是独立维度；国家↔叙事 **多对多**。  
5. 每个叙事必须追溯到具体文章与证据片段。  
6. 地图 / 国家比较 / 叙事 / 时间线共享同一 Event 数据体系。

---

## 3. 核心对象

```text
Event
  ├── event_locations (typed)
  ├── event_participants
  ├── event_articles → article_analyses
  └── narrative_clusters → event_narrative_evidence → articles/spans
```

### 3.1 地点类型（`event_locations.location_type`）

| 类型 | 含义 |
|------|------|
| `EVENT_LOCATION` | 事件实际发生地点 |
| `ANNOUNCEMENT_LOCATION` | 政策或声明发布地点 |
| `PARTICIPANT_LOCATION` | 参与方所在地 |
| `AFFECTED_AREA` | 受到影响的区域 |
| `RELATED_LOCATION` | 其他关联地点 |

无明确物理发生地时：可只记宣布地 / 影响范围标签，或**不钉坐标**；禁止把发布城市解释为「整个事件的地理范围」。

### 3.2 Parent / Sub-event

长期争端可建 `parent_event_id`：主题事件下挂多个有独立时间与结果的子事件（Phase 2 完善生命周期）。

---

## 4. 双地图模式（互斥）

| 模式 | 展示 | 问题 |
|------|------|------|
| 全球事件地图 | 事件地点钉（按 location_type） | 全球发生了哪些涉华事件？ |
| 国家报道分布地图 | 报道来源国热力/气泡 | 哪些国家的媒体在关注？ |

不得在同一图层混用「发生地」与「报道来源国」。

---

## 5. 事件详情三视图 + 时间线

同一 Event ID：

1. **地理 (Where)** — 分类型地点  
2. **国家 (Who reports)** — 国家 → 媒体 → 文章（不压成单一国家立场）  
3. **叙事 (How they frame)** — 叙事簇；跨国共享 + 一国多叙事；证据可点回  

**时间线：** 发生 / 各国首次报道 / 叙事漂移 / 后续发展；报道时滞本身是研究信号。

---

## 6. 阶段边界

| 阶段 | 能力 |
|------|------|
| **Phase 1 / P1-F** | 规则型重大新闻候选 = **proto-Event**（一簇多文、可挂地点类型、可无坐标）；UI 按三视图实现 |
| **Phase 2** | 完整事件聚类、跨语言、Parent/Sub-event、叙事聚合校准 |
| Phase 1 | **不宣称**已具备完整事件图谱 |

主题词表一律 `taxonomy_v0.4`；**不用**威胁情报八类（Social/Military/Cyber…）作事件类型图例。  
**不做** US-Aligned / China-Aligned 站队着色。

---

## 7. 相关文档

- 页面壳与总览五块：[DASHBOARD.md](DASHBOARD.md)  
- 表结构：[DATA_SCHEMA.md](DATA_SCHEMA.md)  
- 可视化约束：[VISUALIZATION_SPEC.md](VISUALIZATION_SPEC.md)  
