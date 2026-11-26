# GNI 情报处理与监测聚合链路映射（INTELLIGENCE_PIPELINE_MAPPING）

> 本文件覆盖 V2.0 规范第 1、3、6 节中的 **Layer 1（采集与预处理）→ Layer 2（文章级情报处理）→ Layer 3（确定性监测统计与事件/叙事聚合）**，逐节点核实当前代码输入输出、口径守恒情况与异常处理机制。

---

## 1. Layer 1：数据采集与预处理链路

| 阶段 | 代码模块与函数 | 输入 | 输出与持久化 | 确定性 / LLM | 现状问题 |
|---|---|---|---|---|---|
| 源配置种子 | `src/gni/sources/seed.py:seed_sources()` | `configs/sources.yaml` | `countries`, `organizations`, `sources`, `source_reviews` | 确定性 | `sources.yaml` 近期新增了 US/IN/AU 源，导致既有单测 `test_editorial_focus.py` 2 项规则断言过期 |
| RSS 采集 | `src/gni/ingestion/service.py:run_ingestion()` + `rss_adapter.py:RssAdapter` | 活跃 `Source` 列表 | `raw_documents`（append-only）、`discovered_articles`、`articles(RAW_STORED)`、`source_health`、`ingestion_jobs`、`collection_tasks` | 确定性 | 仅支持 `rss_adapter`；原始载荷截断上限 256,000 字符 |
| URL 规范化 & L1 标题初筛 | `src/gni/processing/service.py:process_article()` + `title_l1.py:screen_title()` | `Article.title` + `content_original` | `article_screenings(stage='title')`、`articles.title_screening_label/priority` | 确定性规则 | 仅用于优先级与日志，**不直接拦截**文章进入正文提取（防止漏召回） |
| 正文抓取与清洗 | `src/gni/processing/extractor.py:fetch_and_extract()` + `normalize.py` | `Article.url` 或离线 HTML / RSS stub | `article_versions`（`version_no`, `content_clean`, `char_count`, `quality_status`）、`articles.content_clean` | 确定性 | 支持 `skip_fetch` 离线模式；正文过短标记 `insufficient_text` |
| 去重与语言识别 | `processing/service.py:_find_duplicate()` + `language.py:detect_language()` | 同源 `articles`、`content_hash`、规范化标题 | 重复文章置 `duplicate_of_article_id` + `exclude_from_metrics=True`；`pipeline_state=DEDUPLICATED` | 确定性 | **仅做同源去重**；跨源转载/重复 URL 去重目前由 `metrics/v1_stats.py` 在统计期动态完成，未回写持久化 |

---

## 2. Layer 2：文章级情报处理（Article Intelligence）

核心入口：`src/gni/analysis/service.py:analyze_article()` 与批处理入口 `run_analysis()`。

### 2.1 当前执行流水线 vs V2.0 规范对照

| V2.0 子任务 | 当前代码实现 | 输入 | 输出 | 状态与差距 |
|---|---|---|---|---|
| **1. China Relevance** | `l2_fulltext.py:screen_fulltext()` + `relevance.py:assess_relevance()` | `ArticleVersion.content_clean` + 实体词典 `china_entity_dictionary_v0.2` | `ArticleScreening(stage='fulltext')` + `ArticleRelevanceAssessment`（`core`/`substantial`/`secondary`/`incidental`/`none`/`uncertain` 及权重） | **已实现**。具备正文级段落扫描，但依赖规则词典，软提及/隐喻涉华仅标 `possible_china` 需复核 |
| **2. Relevant Passage Extraction** | `l3_spans.py:extract_china_spans()` | `content_clean` + L2 命中段落索引 | `ArticleChinaSpan`（`paragraph_index`, `char_start`, `char_end`, `text_original`, `validation_status`） | **已实现**。具备切片一致性校验（`validate_span_quote`），但仅在 `l2.label == "china_related"` 时提取 |
| **3. Topic Classification** | `deepseek.py:DeepSeekLLMProvider.analyze()` / `heuristic.py:_pick_topics_v1()` | 标题 + `spans`（正文涉华片段）+ `taxonomy_prompt_block()` | `structured_result.topics_v1`（0..15 个有效 ID）+ `boards_v1`（由 `boards_for_topics()` 确定性派生） | **已实现 V1.0 口径**。不依赖标题单独分类；缺各 topic 独立 `evidence_refs` 与相关度分级 |
| **4. Sentiment Analysis** | `deepseek.py:analyze()` / `heuristic.py` | 涉华正文/spans | `structured_result.sentiment`（`label`, `score`, `intensity`, `status`） | **部分实现**。已与 Stance 分开存储，但 DeepSeek 未强制输出 `sentiment_target`、`confidence`、`reasoning` 与原文证据 |
| **5. Stance Analysis** | `deepseek.py:analyze()` / `heuristic.py:_china_stance_v1()`；读取由 `stance_util.py:extract_v1_china_stance()` 严格守门 | 涉华正文/spans | `structured_result.china_stance`（`stance_label` ∈ `{Positive, Neutral, Negative, Unclassified}`, `stance_confidence`, `stance_evidence`, `analysis_status`）+ 旧 `stances[]` | **核心缺口（P0）**：1) `china_stance` 未显式输出 `expression_owner`（`media`/`quoted_actor`/`unclear`）与 `target` 字段；2) `stance_evidence[].quote` 未执行原文 offset 校验（防模型编造引文）；3) 历史库 84.8% 为 `v0.1` 存量导致统计期大量归为 `Unclassified` |
| **6. Narrative Extraction** | 仅 `structured_result.framing`（`primary`/`secondary` 8 类固定框架标签），`claims` 恒为空列表 `[]` | 全文/spans | 仅单标签 `framing.primary` | **重大缺口（P1）**。未提取结构化 `frame`/`claim`/`actor`/`target`/`attribution`（提及/引用/支持/反驳）/`tone`/`evidence_refs` |
| **7. Entity Extraction** | 仅 L2 中国实体字典命中 + `heuristic.py:_entities_from_matches()` | 正文 | `structured_result.entities`（仅 Heuristic 填充，DeepSeek Prompt 未要求返回） | **重大缺口（P1）**。缺少非中国实体（外国政府/机构/人物/企业）与角色标注 |
| **8. Event Candidate Extraction** | 不在 `analysis/` 中，独立置于 `events/extract.py:heuristic_extract()` | 文章标题 + `china_spans` | `ArticleEventCandidate`（正则抽取 `actor`/`action`/`object`） | **重大缺口（P1）**。仅靠英文标题正则匹配，中文/非英语召回差，缺 `event_relation`（新事件/更新/背景引用/无关） |
| **9. Cross-field Validation & Quality** | `deepseek.py:analyze()` 内仅校验 `topics_v1` 白名单与 `stance_label` 枚举；无跨字段一致性校验 | LLM JSON 输出 | `analysis_status` + `field_status` | **缺口（P0）**。未校验 `stance_evidence` 是否真实存在于正文、未校验 `china_stance` 与 `expression_owner` 冲突、未产出规范 `quality` 对象 |

### 2.2 异常处理现状核查

| V2.0 异常场景 | 当前代码真实处理方式 | 是否达标 |
|---|---|---|
| 正文缺失 / 过短（<120 字） | `l2_fulltext.py:114-130` 返回 `insufficient_text` → `relevance.py` 置 `relevance_level='uncertain', weight=None` | 达标 |
| 非涉华文章 | `analysis/service.py:152-184` 由 L2 Gate 直接短路写入 `skipped_not_china`，零 LLM 费用 | 达标 |
| 混合立场 / 证据不足 | `deepseek.py:183,214` 与 `stance_util.py:29-35` 强制落入 `Unclassified`，不强行塞入正/中/负 | 达标 |
| 高引用占比（媒体 vs 引述对象） | 仅 Prompt 文本提醒，缺少结构化 `expression_owner` 字段与确定性过滤校验 | **待补齐（P0）** |
| 单字段缺失 / LLM 不可用 | `analyze_with_fallback()` 降级到 `heuristic.py`，并在 `provider`/`prompt_version` 显式标记；但文章级不支持按子任务局部重试 | **待改进（P1）** |

---

## 3. Layer 3：监测与聚合层（Monitoring & Aggregation）

### 3.1 确定性统计监测（Statistical Monitoring）

当前存在**两套统计路径**：

1. **V1.0 权威统计引擎（`src/gni/metrics/v1_stats.py` + `metrics/service.py:run_v1_stat_snapshots()`）**
   - **完全符合 V2.0 第 0.3 节不可变统计口径**：
     - 严格按 `published_at` 过滤时间窗（绝不用 `first_seen_at`）；
     - 严格按 `Source.country_id` 归属国家；
     - 窗口内三级去重：`canonical_url`（剔除 UTM 等追踪参数）→ `content_hash` → `(source_id, title_hash)`；
     - 严格按 `CHINA_INCLUDE_LEVELS`（`core`/`substantial`/`secondary`）纳入；
     - 固定 4 板块×15 议题多标签（`configs/taxonomy_v1.yaml`），同板块内跨议题按 `article_id` 去重，不同议题间允许重复计数；
     - 立场仅读取 `schema_version == "article_analysis_v1.0"` 的 `china_stance`，历史旧分析不强转，统一记入 `Unclassified`；
     - 正/中/负比例分母严格为 `classified_count = Positive + Neutral + Negative`，同时输出 `stance_coverage_rate = classified_count / article_count` 与可追溯 `article_ids[]`。
   - **缺口**：尚缺 `MEDIA` 维度快照、缺内置确定性 `Growth Rate` / `Historical Baseline` / `Concentration` / `Small-sample Guard` 变化检测模块（目前环比/趋势变化分散在 `weekly.py`、`monthly.py`、`evidence.py` 和 `alerts/rules.py` 中各自计算）。

2. **旧版多维指标引擎（`src/gni/metrics/compute.py` + `metrics/service.py:run_metrics()`）**
   - 输出 `MetricRun`（`metrics_v0.4`），包含 `weighted_article_volume`（辅助指标）、旧 7 议题、旧情感均值、源采集健康率。
   - **问题**：仍被 `dashboard/data.py`（Overview/Trends）与部分日报辅助区块读取；其中 `alerts/rules.py:269` 仍读取旧 `structured.get("topics").get("primary")` 而非 `topics_v1`，造成监测与报告口径割裂。

### 3.2 事件聚合监测（Event Monitoring）

核心链路：`events/extract.py` → `events/fingerprint.py` → `events/match.py` → `events/rollup.py` → `events/service.py`。

- **输入与匹配**：读取 `ArticleEventCandidate` 为 `FingerprintCard`，用 `(actor_key, action_key, object_key, event_time)` 计算确定性 `fingerprint_hash`；`resolve_relation()` 在规则高置信时直接合簇，边界候选（0.45–0.75）可选调用 LLM 判定 `SAME_EVENT`；严守 `event_time` 不被 `published_at` 替代（`match.py:44`）。
- **Rollup**：`rollup_event_metrics()` 计算 `event_metric_snapshots`（文章数、媒体数、国家数、情感/立场分布、分国视图）；`rollup_country_china_attitude()` 计算 30 天国家对华态度快照。
- **核心差距**：
  1. **覆盖面低**：实库 1,799 篇文章 → 347 条候选 → 仅 32 个事件、32 条 `event_articles`（几乎全为 1 事件 1 文章，跨文章聚类能力弱）；
  2. **地理打点缺失**：`event_locations` 实库为 **0 行**，仅靠 `geo.py` 静态词表难以提取真实事件地点；
  3. **演化状态缺失**：`Event.status` 仅 `proto/active/closed/locked`，未计算 `emerging`/`escalating`/`de_escalating`/`dormant` 等生命周期状态，也无持久化事件时间线节点表/结构。

### 3.3 叙事聚合监测（Narrative Monitoring）

- **现状**：**完全缺失（0 行写入）**。虽然 `models.py` 已建 `narrative_clusters` 与 `event_narrative_evidence`，但无任何聚合服务生成跨文章叙事簇，也无法区分“同议题不同叙事”、“支持证据 vs 反例”或“跨国叙事演变”。目前月报 `narrative_landscape` 仅是对 `framing.primary` 固定 8 分类做简单计数。

### 3.4 规则异常与信号检测（Alerts → Change Detection & Signals）

- **现状**：`alerts/rules.py` 实现了 5 类情报预警（`volume_spike`、`sentiment_shift`、`stance_shift`、`narrative_shift`、`major_event`、`transnational`）与 5 类系统运维告警。
- **口径偏差与缺口**：
  1. `_article_time(a)` 使用 `a.published_at or a.first_seen_at`（回退了 `first_seen_at`，与 V1.0 严格 `published_at` 口径不一致）；
  2. `narrative_shift` 读取旧 `topics.primary` / `framing.primary`，未对接 V1.0 15 议题；
  3. `stance_shift` 读取旧 `stances[]` 的 `critical/opposing`，未对接 V1.0 `china_stance`；
  4. 缺少对“小样本百分比暴涨”与“采集覆盖变动”的联合过滤，尚未沉淀为可供研判层直接消费的 `ChangeCandidate` 结构。
