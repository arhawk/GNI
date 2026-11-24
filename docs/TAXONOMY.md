# 主题与目标对象 Taxonomy

**版本：** taxonomy_v0.4  
**状态：** Phase 0/1 草案；变更须升版本并记录生效时间  
**原则：** Topic 与 Stance Target 分离；Frame 以 V4 候选词表为准；旧 `taxonomy_v0.1` Frame 仅兼容历史分析  

---

## 1. 版本管理

| 字段 | 说明 |
|------|------|
| taxonomy_version | 当前 `taxonomy_v0.4` |
| effective_from | UTC 生效时间 |
| changelog | 新增/停用/合并/拆分记录 |

历史分析绑定当时的 `taxonomy_version`，禁止静默改旧标签定义。

**兼容：** `taxonomy_v0.1` 的旧 Frame 词表（Economic Competition、Technology Competition 等）可映射到 v0.4 或保留只读；新分析默认写 v0.4。

---

## 2. 主题体系（Topic）

### 2.1 一级主题

| topic_id | 中文名 | 英文名 |
|----------|--------|--------|
| politics_governance | 政治与治理 | Politics & Governance |
| economy_trade | 经济与贸易 | Economy & Trade |
| technology | 科技 | Technology |
| security_military | 安全与军事 | Security & Military |
| international_relations | 国际关系 | International Relations |
| society_culture | 社会与文化 | Society & Culture |
| environment_energy | 环境与能源 | Environment & Energy |
| other_unknown | 其他/未知 | Other / Unknown |

### 2.2 二级主题示例（可扩展）

| parent_id | topic_id | 中文名 |
|-----------|----------|--------|
| politics_governance | political_system | 政治制度 |
| politics_governance | governance | 政府治理 |
| politics_governance | foreign_policy_general | 外交政策（通用） |
| economy_trade | macro_economy | 宏观经济 |
| economy_trade | trade | 贸易 |
| economy_trade | investment | 投资 |
| economy_trade | supply_chain | 供应链 |
| technology | ai | 人工智能 |
| technology | semiconductors | 半导体 |
| technology | telecom | 通信 |
| technology | tech_firms | 科技企业 |
| security_military | military | 军事 |
| security_military | national_security | 国家安全 |
| security_military | cyber_security | 网络安全 |
| international_relations | bilateral_us_china | 中美关系 |
| international_relations | bilateral_eu_china | 中欧关系 |
| international_relations | regional_cooperation | 区域合作 |
| society_culture | education | 教育 |
| society_culture | demography | 人口 |
| society_culture | culture | 文化 |
| society_culture | social_governance | 社会治理 |
| environment_energy | climate | 气候 |
| environment_energy | energy | 能源 |
| environment_energy | environment_policy | 环境政策 |

一篇文章可有 **Primary Topic + Secondary Topics**（多标签）。

### 2.3 多语言与同义词（TBD）

每标签支持：`label_zh`、`label_en`、`synonyms[]`、`parent_id`、`status`。印地语等译名待确认。

---

## 3. 立场目标对象（Stance Target）

| target_id | 中文名 | 英文名 |
|-----------|--------|--------|
| china | 中国 | China |
| chinese_government | 中国政府 | Chinese Government |
| ccp | 中国共产党 | Chinese Communist Party |
| chinese_economy | 中国经济 | Chinese Economy |
| chinese_tech_industry | 中国科技产业 | Chinese Technology Industry |
| chinese_military | 中国军队/军事 | Chinese Military |
| chinese_society | 中国社会 | Chinese Society |
| chinese_foreign_policy | 中国外交政策 | Chinese Foreign Policy |
| specific_entity | 特定实体/政策/公司 | Specific Entity / Policy / Company |

`specific_entity` 须另填 `target_surface_form` 与可选 `normalized_entity_id`。Stance **必须**绑定 Target。

---

## 4. 叙事框架词表（Framing）— taxonomy_v0.4

V4 候选体系（试标后可调整）：

| frame_id | 中文名 | 英文名 |
|----------|--------|--------|
| competition_rivalry | 竞争 | Competition / Rivalry |
| security_threat | 安全或威胁 | Security / Threat |
| economic_impact | 经济影响 | Economic Impact |
| cooperation | 合作 | Cooperation |
| governance_ideology | 治理或制度 | Governance / Ideology |
| development_innovation | 发展或创新 | Development / Innovation |
| human_rights | 人权 | Human Rights |
| international_order | 国际秩序 | International Order |
| other_unknown | 其他/未知 | Other / Unknown |

允许多标签；记录 Primary / Secondary。新框架须审核后升版本纳入。

### 4.1 旧版 Frame（taxonomy_v0.1，只读兼容）

`economic_competition`、`national_security`、`technology_competition`、`geopolitical_rivalry`、`ideology_values`、`cooperation`、`human_rights`、`global_development`、`environmental_transition`、`domestic_politics`、`unknown` — 历史结果可保留；新管线默认 v0.4。

---

## 5. 情感与立场枚举

**Sentiment：** positive / negative / neutral / mixed / unknown  

**Stance：** supportive / opposing / critical / cautious / neutral / no_explicit_stance / mixed / ambiguous / unknown  

辅助情绪（可选）：fear / concern / anger / optimism / praise / criticism / uncertainty  

---

## 6. China Relevance Level（相关，非 Frame）

权威词表见 Addendum A1 / [PROVISIONAL_CALIBRATION.md](PROVISIONAL_CALIBRATION.md)：

| level | 说明 | 初始权重区间（provisional） |
|-------|------|------------------------------|
| core | 主要讨论对象 | 0.80–1.00 |
| substantial | 重要参与方/分析对象 | 0.50–0.79 |
| secondary | 实质次要对象/背景 | 0.20–0.49 |
| incidental | 简短提及 | 0.01–0.19（默认不进核心统计） |
| none | 无实质涉华 | 0.00 |
| uncertain | 证据不足 | 不分配正式权重 |

旧名 major/moderate/minor/not_relevant 仅作历史映射。

---

## 7. 与中国中心视角

首期筛选与报告聚焦实质涉华文章；Taxonomy 字段保持通用，便于未来扩展其他 Central Target。
