# ARTICLE_INTELLIGENCE_IMPLEMENTATION.md — Phase 3 文章级情报分析实施报告

> 分支：`cursor/data-trust-batch1` | 日期：2026-11-26 | 依据：GNI Architecture & Implementation Specification V2.0（Phase 3）

## 1. 十大文章级能力状态总览

| # | 能力项 | 实现文件 | 状态 | 关键约束落实情况 |
|---|---|---|---|---|
| 1 | China Relevance | `src/gni/analysis/l2_fulltext.py`, `relevance.py` | `implemented` | 仅分析涉华内容；L2 门控清晰拦截 `not_china_related` 并同样产出规范契约 |
| 2 | Relevant Passage Extraction | `src/gni/analysis/l3_spans.py` | `implemented` | 段落级抽取 + `validate_span_quote()` 原文子串与偏移核验 |
| 3 | Topic Classification | `src/gni/analysis/heuristic.py`, `deepseek.py`, `metrics/taxonomy_v1.py` | `implemented` | 锁定四大板块 × 15 议题，基于正文/涉华片段多标签归类，同议题去重 |
| 4 | Sentiment Analysis | `heuristic.py`, `deepseek.py`, `service.py` | `implemented` | 与 Stance 独立存储，含 `sentiment_target`、`confidence`、`reasoning`、`evidence_refs` |
| 5 | Stance Analysis | `heuristic.py`, `deepseek.py`, `stance_util.py`, `service.py` | `implemented` | 绑定 `target="china_mainland"`，区分 `expression_owner ∈ {media, quoted_actor, unclear}`；`extract_v1_china_stance()` 强制将 `quoted_actor` 隔离为 `Unclassified` |
| 6 | Narrative Extraction | `heuristic.py`, `deepseek.py` | `implemented` | 输出结构化 `narratives[]`（`frame`/`claim`/`actor`/`target`/`attribution`/`tone`/`evidence_refs`），保留矛盾叙事不压平 |
| 7 | Entity Extraction | `heuristic.py`, `deepseek.py` | `implemented` | 输出 `entities[]`（`entity_id`/`canonical_name`/`entity_type`/`mentions`/`roles`），兼容旧键 `text`/`type` |
| 8 | Event Candidate Extraction | `heuristic.py`, `deepseek.py` | `implemented` | 输出 `event_candidates[]`（支持单篇多事件、`event_relation`），未知 `event_time` 严格保持 `null` |
| 9 | Evidence Management | `src/gni/analysis/service.py` (`validate_and_enrich_article_intelligence`) | `implemented` | 对 `evidence[]` 与 `stance_evidence[]` 执行原文偏移对齐，绑定 `article_version_id` 与 `validated`；未命中原文标 `unverified_stance_quote` + `needs_review=True` |
| 10 | Quality Assessment | `src/gni/analysis/service.py` (`ArticleQualityContract`) | `implemented` | 确定性计算 `completeness`、`language_quality`、`extraction_quality`、`classification_quality`、`needs_review`、`quality_flags` |

> 说明：DeepSeek 路线（`deepseek_analyze_v1.1`）已完成 Prompt、结构化解析、契约归一化与单测 Mock 验证；在离线无 API Key 环境下自动降级为 `heuristic_v1.1`。历史存量文章可通过 `gni analyze run --reanalyze-legacy` 按批增量重跑。

## 2. 九类边界案例验收（`tests/unit/test_article_intelligence_boundaries.py`）

9/9 全部通过：
1. 不涉华文章（`none`）→ `is_china_related=False`，`topics=[]`，`stance=Unclassified`，仍产出规范 `ArticleIntelligenceContract`。
2. 弱涉华文章（`incidental`）→ 识别为弱涉华并保留精确偏移证据。
3. 多议题文章 → 跨板块重叠、同板块/同议题去重。
4. 正负观点混合文章 → 严格判定 `Unclassified`，不强行二选一。
5. 大量引用他人观点文章 → `expression_owner="quoted_actor"`，写入 `quoted_actor_stance_excluded_from_media` 与 `needs_review=True`，V1.0 统计读取器严格返回 `Unclassified`。
6. 缺失/极短正文文章 → `extraction_quality="insufficient"`、`short_or_missing_body`、`needs_review=True`。
7. 事件时间不明确文章 → `event_time=None`，绝不以 `published_at` 替代。
8. 多事件文章 → 提取多个独立 `event_candidates[]`（不同 `actor`/`action`）。
9. 叙事矛盾文章 → 同时保留 `support`/`mention` 与 `refute` 两条相反倾向叙事，且偏移精确切片还原 `ArticleVersion.content_clean`。

## 3. 本地真实数据库抽样与错误案例分析（只读评估 12 篇）

在本地 SQLite 数据库随机抽取 10 篇涉华文章 + 2 篇不涉华文章运行 Phase 3 全链路（heuristic 离线模式，只读不写库）：

| ID | 语言 | 标题截断 | 正文字符 | 涉华级别 | 议题数 | 立场 / Owner | 叙事/实体/事件 | 已核验证据 | Quality Flags |
|---|---|---|---|---|---|---|---|---|---|
| `1fb49734` | `en` | Xi Jinping applauds Anthony Albanese... | 2929 | `core` | 1 | `Positive` / `quoted_actor` | 1 / 7 / 1 | 7 | `quoted_actor_stance_excluded_from_media` |
| `06861af3` | `en` | 'We are really making history': Trump, Xi... | 7173 | `substantial` | 1 | `Unclassified` / `quoted_actor` | 2 / 4 / 0 | 7 | `[]` |
| `28c40722` | `en` | Meetings between leaders of Russia, China... | 2304 | `core` | 2 | `Positive` / `quoted_actor` | 1 / 5 / 1 | 7 | `quoted_actor_stance_excluded_from_media` |
| `aecb7264` | `en` | Nvidia returns to top three most valuable... | 1164 | `substantial` | 1 | `Neutral` / `media` | 1 / 2 / 0 | 3 | `[]` |
| `527eda64` | `en` | Germany news: Metalworkers go on strike... | 17998 | `substantial` | 3 | `Neutral` / `media` | 1 / 1 / 0 | 4 | `[]` |
| `c7192949` | `de` | KI im Klassenzimmer... | 7711 | `secondary` | 0 | `Neutral` / `media` | 1 / 2 / 0 | 3 | `[]` |
| `a821d3df` | `hi` | भारत की राष्ट्रपति... | 5521 | `substantial` | 0 | `Neutral` / `media` | 1 / 1 / 0 | 4 | `[]` |
| `cae5ce47` | `en` | Anthropic's epic $3 trillion debut... | 4371 | `none` | 0 | `Unclassified` / `unclear` | 0 / 0 / 0 | 0 | `[]` |
| `568c93c5` | `en` | As war engulfs the Strait of Hormuz... | 5016 | `none` | 0 | `Unclassified` / `unclear` | 0 / 0 / 0 | 0 | `[]` |

### 暴露出的真实错误/边界案例与后续优化建议

1. **多语种非英中文章（德语 `c7192949`、印地语 `a821d3df`）议题召回偏低**：`heuristic_v1.1` 词典以中/英文为主，非英中文章在离线模式下 `topics_v1=[]`；建议在生产环境对非英中 `core/substantial` 文章优先路由 `deepseek_analyze_v1.1`。
2. **上游语种误标（`2cd99940` 印地语正文被标为 `lang="en"`）**：属于 `processing` 层语种检测问题，不属本批次范围，已登记到 `UPDATED_GAP_ANALYSIS.md`。
3. **超长 Liveblog 聚合页（`527eda64`, 17,998 字符）议题串扰**：Liveblog 包含多条无关快讯，全正文关键词匹配命中了 3 个议题；后续可对 `len(body) > 8000` 且非 `core` 的文章限制仅在 `valid_spans` 内做议题匹配。
