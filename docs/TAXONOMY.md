# 主题与目标对象 Taxonomy

**版本：** taxonomy_v0.1  
**状态：** Phase 0 草案；变更须升版本并记录生效时间  
**原则：** Topic 与 Stance Target 分离；不把 China 写死为唯一目标对象类型

---

## 1. 版本管理

| 字段 | 说明 |
|------|------|
| taxonomy_version | 如 `taxonomy_v0.1` |
| effective_from | UTC 生效时间 |
| changelog | 新增/停用/合并/拆分记录 |

历史分析绑定当时的 `taxonomy_version`，禁止静默改旧标签定义导致口径漂移。

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

### 2.3 多语言与同义词（TBD 结构）

每标签支持：`label_zh`、`label_en`、`synonyms[]`、`parent_id`、`status`（active/deprecated）。

**TBD（需人工确认）：** 印地语等标签译名表；「中印关系」是否单列二级主题。

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

`specific_entity` 须在分析中另填 `target_surface_form` 与可选 `normalized_entity_id`。

Stance **必须**绑定 Target；一篇文章可对多个 Target 持不同立场。

---

## 4. 叙事框架初始词表（Framing）

| frame_id | 中文名 | 英文名 |
|----------|--------|--------|
| economic_competition | 经济竞争 | Economic Competition |
| national_security | 国家安全 | National Security |
| technology_competition | 技术竞争 | Technology Competition |
| geopolitical_rivalry | 地缘政治竞争 | Geopolitical Rivalry |
| ideology_values | 意识形态与价值观 | Ideology and Values |
| cooperation | 合作 | Cooperation |
| human_rights | 人权 | Human Rights |
| global_development | 全球发展 | Global Development |
| environmental_transition | 环境与绿色转型 | Environmental Transition |
| domestic_politics | 国内政治 | Domestic Politics |
| unknown | 未知/证据不足 | Unknown |

允许多标签；新框架须进人工审核流程后升版本纳入。

---

## 5. 情感与立场枚举（分析用，非主题）

**Sentiment：** positive / negative / neutral / mixed / unknown  

**辅助情绪（可选）：** fear / concern / anger / optimism / praise / criticism / uncertainty  

**Stance：** supportive / opposing / critical / cautious / neutral / ambiguous / unknown  

---

## 6. 与中国中心视角的关系

- 首期**筛选与报告**聚焦「与中国相关」文章（相关性规则 Phase 1 定义）。  
- Taxonomy 中 Target 以中国相关为主，但模型字段保持通用（未来可增加其他国家 Target 集）。  
