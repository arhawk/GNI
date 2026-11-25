# 第二批接口说明（编码后置于 P1-F1/F2 验收后）

**状态：** **已实现**（Batch2）  
**对应：** P1-F3 + 指纹增强、Attention 门禁、地理精度

---

## 1. 持久化 Alerts

### 表

| 表 | 职责 |
|----|------|
| `alert_rules` | 规则 ID、版本、阈值 JSON、启用开关 |
| `alerts` | 告警实体：status、deduplication_key、first/last_triggered_at、trigger_count、severity、category |
| `alert_events` | 状态迁移：OPEN→ACKNOWLEDGED→RESOLVED→CLOSED（及 reopen） |
| `alert_evidence` | article_id / event_id / metric 快照引用 |

### API（拟定）

```text
GET  /api/alerts                 # 读库；支持 window_start/window_end
POST /api/alerts/{id}/acknowledge
POST /api/alerts/{id}/resolve
POST /api/alerts/{id}/close
POST /api/alerts/run             # 规则引擎 upsert（同 dedupe_key 不换 UUID）
```

`build_alerts_payload(session, window_start=..., window_end=...)`：日报必须传入报告日窗口。

---

## 2. Event merge / split 审计

```text
event_revisions (id, event_id, action=merge|split|correct, payload, actor, created_at)
```

人工 `confirmed`/`locked` 事件不可被自动删除。

---

## 3. Source.feed_scope

枚举：`GENERAL_NEWS | INTERNATIONAL_NEWS | CHINA_FOCUSED | TOPIC_SPECIFIC | GOVERNMENT_RELEASES`  
Attention Share 仅当 scope 允许可靠分母时发布；否则 `unavailable` + 覆盖说明。

---

## 4. 地理精度

Location 增加：`geographic_precision`（city|region|country|maritime|unknown）、`confidence`、`evidence`。  
海域/争议区禁止绑国家 centroid 冒充发生点。

---

## 5. Fingerprint 多语言

统一 action taxonomy + 实体别名；抽取失败 → `INSUFFICIENT_INFORMATION`；禁止 token 排序假 Actor/Action。
