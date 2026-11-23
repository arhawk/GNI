# 来源注册表规范（SOURCE_REGISTRY）

**版本：** 0.1  
**相关文件：** [source_registry_template.csv](source_registry_template.csv)、[source_candidates.csv](source_candidates.csv)、[COMPLIANCE.md](COMPLIANCE.md)

---

## 1. 目标

建立可审计、可扩展的跨国媒体/政府传播来源体系。分类必须有证据，禁止仅凭名称猜测。

---

## 2. 来源类别

| 代码 | 名称 | 说明 |
|------|------|------|
| state_controlled | State-owned / State-controlled Media | 国有或受政府实质控制 |
| public_service | Public Service Media | 公共服务媒体；须结合治理与编辑独立性 |
| gov_comms | Government Communication Sources | 政府部门、新闻办、官方稿 |
| mainstream_independent | Mainstream Independent Media | 主流独立媒体；MVP 后作对照 |

四类**不可默认等价**。公共广播不得仅因「公共」归为政府控制。

---

## 3. 字段规范

### 3.1 核心字段（每个来源至少）

| 字段 | 类型建议 | 说明 |
|------|----------|------|
| source_id | string | 稳定 ID，如 `us_state_gov` |
| name | string | 展示名 |
| country_id | string | ISO 3166-1 alpha-2：US/RU/DE/IN/AU |
| organization_id | string | 所属组织 |
| canonical_url | url | 官网或栏目规范 URL |
| source_type | enum | 上表四类之一 |
| ownership_type | string | 所有权类型 |
| funding_type | string | 资金类型（可 TBD） |
| government_control_level | enum | none / low / medium / high / unknown |
| editorial_independence | enum | high / medium / low / unknown |
| language | string | 主语言 BCP-47，如 en、ru、de、hi |
| timezone | string | IANA，如 America/New_York |
| access_method | enum | rss / api / web / other |
| adapter_type | string | rss_adapter / api_adapter / web_adapter |
| terms_url | url/null | 服务条款或版权页 |
| robots_checked_at | datetime/null | UTC |
| compliance_status | enum | pending / allowed_internal / restricted / blocked |
| evidence_url | url/null | 分类依据链接 |
| classification_confidence | enum | high / medium / low |
| reviewed_at | datetime/null | 最近审核 UTC |
| reviewed_by | string/null | 审核人角色或标识 |
| active_status | enum | candidate / active / paused / retired |
| notes | string | 备注 |
| verification_status | enum | unverified / in_progress / verified / failed |
| feed_or_api_url | string | **未核验前必须为 TBD** |

### 3.2 关联表（逻辑）

- `source_reviews`：审核意见、结论、时间、审核人  
- `source_attribute_history`：属性变更前后值、原因、时间  
- `source_health`：成功率、最近成功/失败、错误信息  

建议每 **6–12 个月**复核；所有权或治理变化时提前复核。

---

## 4. 准入优先级

1. 稳定 RSS / API / 开放 Feed  
2. 无需登录且结构稳定的公开网页  
3. 其他方式须单独可行性与合规评估  

**暂不纳入 MVP：** 强反爬、登录/付费墙、结构频繁变更、条款或法律风险无法评估的站点。

不得为凑齐 15–25 个来源而降低标准。规模以真实可采集性为准。

---

## 5. MVP 国家与接通顺序

| 顺序 | 国家 | country_id | 风险备注 |
|------|------|------------|----------|
| 1 | 美国 | US | 优先；英语 RSS 相对丰富 |
| 2 | 俄罗斯 | RU | 可达性/合规/语言高风险 |
| 3 | 德国 | DE | 德语；公共广播须仔细标注独立性 |
| 4 | 印度 | IN | 多语言；结构与合规需逐源评估 |
| 5 | 澳大利亚 | AU | 英语；相对靠后接通 |

扩展池：**加拿大（CA）** 等，不进本轮短名单。

---

## 6. 候选评估流程

1. 在 `source_candidates.csv` 登记候选（名称、国家、类型假设、官网）  
2. 人工打开条款 / robots（记录检查时间，**robots ≠ 法律授权**）  
3. 查找并**实测** RSS/API；成功才写入 `feed_or_api_url` 并标 `verified`  
4. 填写分类证据与 `classification_confidence`  
5. `compliance_status` 达 `allowed_internal` 且技术核验通过后，方可 `active`  

Phase 0：**禁止编造** feed 地址或「已可采集」状态。CSV 中未核验项一律 `TBD` / `unverified`。

---

## 7. Source Health（与舆情分隔离）

监控：最近成功采集时间、成功率、发现量异常、正文提取率、发布时间缺失率、重复率、Adapter 错误类型。  

**来源健康只衡量数据源质量，不参与舆情分数。**
