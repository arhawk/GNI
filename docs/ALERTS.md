# 预警规范草案（ALERTS）

**版本：** alerts_v0.1（对齐 Blueprint V4 §27.6–27.7）  
**阶段：** Phase 1 规则型预警；统计校准与学习反馈深化在 Phase 2  
**原则：** 确定性规则触发；LLM 只可解释，不可编造触发值；质量类与舆情类分开。

---

## 1. MVP 预警类型

| 规则 ID | 含义 | 备注 |
|---------|------|------|
| VOLUME_SPIKE | 国家/来源/Topic 涉华量相对基线突增 | 冷启动禁用正式异常断言 |
| NEGATIVE_SHARE_RISE | 负面占比或加权负面量明显上升 | |
| POSITIVE_SHARE_RISE | 正面占比或加权正面量明显上升 | |
| SENTIMENT_SHIFT | 加权情感分数相对自身基线显著变化 | |
| MULTI_COUNTRY_COVERAGE | 同一候选事件多国集中报道 | 依赖重大新闻候选 |
| SOURCE_BURST | 单一来源短期集中发布 | |
| TOPIC_EMERGENCE | 某涉华议题快速上升 | |
| MAJOR_EVENT_CANDIDATE | 重大新闻候选被识别 | |
| SOURCE_HEALTH_FAILURE | 采集异常 | **数据质量提醒，非舆情** |

阈值（σ / 百分比）、窗口与冷启动禁用规则 **待标定**，见 [PHASE0_REPOSITORY_AUDIT_V4.md](PHASE0_REPOSITORY_AUDIT_V4.md)。

---

## 2. 每条预警必须包含

- 规则 ID 与版本  
- 观察窗口、比较基线、阈值  
- 原始样本数、加权样本量  
- 国家 / 来源 / Topic / Target 范围  
- 代表文章与证据链接  
- 置信度与限制说明  
- 状态：new / confirmed / investigating / resolved / false_positive  

---

## 3. 去重与升级

- 同对象、同规则、相邻窗口：合并或抑制  
- 信号增强、扩国或新证据：可升级  
- 记录首次/最近触发与解除时间  
- 支持订阅与误报反馈；不得为提高数量而降阈值  

---

## 4. 与 Agent / Phase 边界

- MVP：流水线 + 规则引擎产出 Alerts；可选轻量编排调用  
- 开放式研究 Agent、复杂调查链路 → Phase 3  
- Dashboard：**Alerts** 页；报告可引用已校验预警摘要  
