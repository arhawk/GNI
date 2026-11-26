# GNI 研判引擎映射与目标任务契约（ASSESSMENT_MAPPING）

> 本文件将现有 `src/gni/reports/narrative/`（报告情报研判层）映射到 **V2.0 规范第 4、5 节**（研判引擎 Assessment Engine 与证据包 Evidence Package），并给出面向 Phase 5 的目标任务编排与契约设计（**严格遵循 Task-based Assessment，不新增多个独立 Agent**）。

---

## 1. 现状盘点：`src/gni/reports/narrative/` 真实能力

现有研判层集中在 `src/gni/reports/narrative/` 的 5 个核心模块中，已经具备 V2.0 研判引擎的雏形（Task-based、Evidence Bundle、DB Cache、3-Layer Validator）：

| 现有文件 | 核心类 / 函数 | 实际职责 |
|---|---|---|
| `evidence.py` | `EvidenceBundle`、`prepare_evidence_bundle()`、`compute_payload_fingerprint()` | 从 DB + 报告规则载荷组装证据包：V1.0 统计、4周/6月细粒度历史序列（含 Top 国家/议题）、事件详情（含 `timeline`/`by_country_views`/`locations`/`participants`/`narrative_clusters`）、URL+`content_hash` 去重选文（按相关性+置信度+片段+时间排序）、显式 `counter_examples`（与主导立场相反的少数派文章）、Daily `orphan_articles`、跨国叙事汇总与 `for_task(task_type)` 按任务切片 |
| `schemas.py` | `EvidenceRef`、`Finding`、`EventInterpretation`、`TopicTrendItem`、`CrossCountryItem`、`StanceInterpretation`、`OutlookSignal`、`NarrativeTaskOutput` | 统一 Pydantic v2 结构化任务输出契约，支持枚举归一化与 `needs_review`/`validation_notes` |
| `prompts.py` | `TaskPromptSpec`、`_build_registry()`、`list_report_tasks()`、`get_task_prompt_spec()` | 注册了 **3 套报告 × 6 类任务**共 15 个版本化 Prompt（日报 3 任务、周报 6 任务、月报 6 任务） |
| `runner.py` | `run_report_intelligence()`、`load_cached_intelligence()`、`_build_user_prompt()` | 基于 `ReportNarrativeTask` 按 `(report_type, period, task_type, prompt_version)` 缓存与 `evidence_hash` 过期检测；结构化逐级瘦身避免 JSON 截断（最大 26,000 字符）；独立报告 LLM 预算检查；支持 `tasks` 子集局部重试与失败降级 |
| `validator.py` | `validate_task_output()`、`_check_numeric_grounding()`、`_check_evidence_refs()`、`_check_reasoning_discipline()` | **3 层确定性校验**：Layer 1 数字落地（核对统计/历史/时间窗口数字，覆盖 `summary`/`findings`/`important_changes`/`main_drivers`/`cross_country`/`event_interpretations`/`topic_trends`/`stance_analyses`）、Layer 2 证据引用真实性校验（剔除虚构 `article_id`/`event_id`，无证据 `Fact` 自动降级为 `Hypothesis`，无引用专项条目自动标 `needs_review=True`）、Layer 3 推理纪律（拦截“代表民意/政府官方立场/协调传播”等越界表述） |

---

## 2. 现有 6 类任务 → V2.0 九类核心研判任务映射

V2.0 规范第 4.3 节定义了 9 类核心研判任务。**原则：绝不为 9 类任务建立 9 个独立 Agent，而是基于现有 `TaskPromptSpec` + `NarrativeTaskOutput` 按报告周期按需编排与增量拆分**：

| V2.0 研判任务 | 现有对应任务（`prompts.py`） | 现状覆盖度 | 映射策略与具体差距 |
|---|---|---|---|
| **A. Overall Situation Assessment** | `executive_analysis`（日/周/月报均包含） | **已覆盖（80%）** | 日报 `daily_exec_v1.0` 已明确要求同时输出总体态势与重点变化；缺口：缺少独立结构化 `data_coverage_limitations` 块与显式 `supporting_metrics[]` 字段 |
| **B. Change Detection Assessment** | 混合在 `executive_analysis`（`important_changes`）与规则 `anomalies` 中 | **部分覆盖（40%）** | 缺独立的确定性变化候选输入（样本量保护、历史基线偏离、采集覆盖变动识别）与“真实变化 vs 小样本波动 vs 采集波动”显式归因 |
| **C. Event Assessment** | `event_analysis`（日/周/月报均包含） | **已覆盖（85%）** | `EventInterpretation` 已覆盖背景/进展/事件本体变化/关注度变化/跟进时间/各国差异/媒体观点/状态/影响/观察点，基本对齐 V2.0 七环节；缺口：缺结构化 `timeline[]` 节点渲染与反例对照 |
| **D. Topic Assessment** | `topic_trend_analysis`（周/月报包含；日报不包含） | **已覆盖（75%）** | 严格区分 Attention ≠ Stance ≠ Structure 并标记 `persistence`；缺口：缺少议题间关联分析及与关联事件/叙事的显式绑定 |
| **E. Cross-country Assessment** | `cross_country_analysis`（周/月报包含） | **已覆盖（80%）** | 已包含 `common_focus`、`country_frames`、`major_differences`、`insufficient_sample_countries`；缺口：未在每个国家条目强制输出精确样本量 `n` 与覆盖率，同事件跨国差异强依赖上游事件多国聚类质量 |
| **F. Narrative Assessment** | **无独立任务**（仅散落在 `cross_country_analysis` 和月报规则 `narrative_landscape`） | **缺失（15%）** | **P1 核心缺口**。需在上游 `NarrativeCluster` 落地后，在周/月报新增 `narrative_analysis` 任务（复用同一 `runner.py` 调度器），分析主导/新兴/衰退/分化/冲突叙事及其正反证据 |
| **G. Sentiment & Stance Assessment** | `stance_analysis`（周/月报包含） | **已覆盖（75%）** | 已要求区分比例与绝对数量、说明覆盖率限制；缺口：未将 `Sentiment` 与 `Stance` 分列对照解释，且受限于上游 84.8% 旧分析导致覆盖率低 |
| **H. Risk & Signal Assessment** | 与 Outlook 合并在 `emerging_signals`（日/周/月报均包含） | **部分覆盖（65%）** | 现有 `OutlookSignal` 已含 `signal`/`reasoning`/`potential_trigger`/`what_to_monitor`/`uncertainty`；**缺口**：缺显式 `alternative_explanation`（替代解释）与规则触发指标 `trigger_metrics` 绑定 |
| **I. Outlook Assessment** | 与 Signal 合并在 `emerging_signals` 中 | **部分覆盖（65%）** | **设计决策**：保持日报合并为一个 `emerging_signals` 任务以控制延迟（当前 3 任务约 20s）；周/月报可在 `OutlookSignal` 契约中补齐 `alternative_scenario` 与 `observation_object`，避免无必要增加串行调用轮数导致超时 |

---

## 3. Evidence Package 现状 vs V2.0 规范对照

| V2.0 规范要素 | 现有 `EvidenceBundle` 实现（`evidence.py`） | 差距与改进方向 |
|---|---|---|
| `package_id` & `task_type` | 无独立 `package_id`（仅在 `runner.py` 生成全局 `evidence_hash`） | **Phase 2/5 补齐**：为每个任务切片生成可追溯 `package_id`（如 `{report_type}:{period}:{task_type}:{hash[:12]}`）并写入 `ReportNarrativeTask` 以便端到端审计 |
| `metrics` & `historical_comparison` | `statistical`（V1.0 全局/国家/板块/议题）+ `historical`（4周/6月总览 + Top 国家/议题序列） | 已较好实现；需补充确定性 `change_candidates[]`（附带样本量充分性标志与采集覆盖变化标注） |
| `current_articles` & 代表性/多样性 | 按相关性权重 + 立场置信度 + 片段丰富度 + 发布时间排序；事件内优先覆盖国各 1 篇；URL + `content_hash` 去重 | 已较好实现；后续可增加媒体类型多样性配额（防止单一政府源或官媒挤占全部名额） |
| `events` & `narratives` | `events` 含 `timeline`/`by_country_views`/`locations`/`participants`/`narrative_clusters` | 证据组装管道已就绪，但受限于上游 `event_locations=0` 与 `narrative_clusters=0`，实际传入多为空 |
| `counter_evidence` | 已显式抽取 `counter_examples`（最多 6 篇与全局主导立场相反文章）并在 `for_task` 保留 | **已实现**；需扩展至**按事件/按议题级别**的反例抽取，而不仅是全局主导立场反例 |
| `coverage` & `limitations` | 存在 `quality` 与 `coverage` 字典，但未标准化为结构化 `limitations[]` 提示词列表 | **Phase 5 补齐**：确定性生成标准 `limitations[]`（如 V1.0 分析覆盖率 < 50%、某国样本 n<3、某源采集失败）直接喂给 LLM |
| Token Budget 管理 | `_build_user_prompt()` 实现了 3 级结构化逐级瘦身（≤26,000 字符，实测周报 22,126 字符、月报 25,848 字符均合法闭合） | **已修复硬截断 Bug**；后续可记录实际瘦身日志（裁剪了多少篇次要文章）到任务元数据 |

---

## 4. 目标研判引擎契约与执行编排（Phase 5 落地标准）

### 4.1 依赖关系与模块解耦

- **包边界**：在 Phase 5 将 `src/gni/reports/narrative/` 的核心抽象逐步提升/暴露为 `src/gni/assessment/`（或通过 `src/gni/reports/narrative/` 保留兼容 re-export），使 `assessment` 只依赖 `metrics/`、`events/`、`alerts/`、`analysis/`，**绝不反向依赖 `reports/daily.py` 等具体报告格式化逻辑**。
- **任务依赖与并发执行**：
  - 当前 `runner.py` 采用串行执行（日报 3 任务实测 **20.30s**，推算周/月报 6 任务约 **40–45s**，接近反向代理 60s 风险线）。
  - **目标编排（两阶段有向无环图，不新增任务队列中间件）**：
    - Stage 1（可并行或单批）：`overall_situation`（原 `executive_analysis`）、`event_analysis`、`topic_trend_analysis`、`cross_country_analysis`、`stance_analysis`、`narrative_analysis`（周/月报新增）；
    - Stage 2（消费 Stage 1 摘要 + 确定性变化候选）：`risk_signal_outlook`（原 `emerging_signals`，升级支持 `alternative_explanation` 与 `alternative_scenario`）。
  - 在 DB 会话外执行并发 HTTP 调用（`ThreadPoolExecutor(max_workers=3)`），回主线程统一落库 `ReportNarrativeTask`，可将周/月报 6 任务总耗时从 ~45s 压降至 ~18–22s。

### 4.2 统一 `AssessmentResult` 增量升级要点（兼容 `NarrativeTaskOutput`）

在现有 `NarrativeTaskOutput` 基础上做**向后兼容的增量补齐**（不破坏现有前端读取）：

1. `Finding.classification` 扩展兼容 `"Outlook"`（与 `Fact | Inference | Hypothesis` 并列，对应 V2.0 第 4.2 节四类 `finding_type`）。
2. `Finding` 新增可选字段 `supporting_metrics: list[str]` 与 `counter_evidence: list[EvidenceRef]`。
3. `OutlookSignal` 新增可选字段 `observation_object: str`、`trigger_metrics: list[str]`、`alternative_explanation: str`、`alternative_scenario: str`。
4. `NarrativeTaskOutput.meta` 强制写入 `package_id`、`assessment_schema_version`、`evidence_trim_stats`。
5. `validator.py` 扩展为 **5 层确定性校验**（对齐 V2.0 第 6.4 节）：Schema Validation → Evidence Validation → Metric Consistency Validation → Cross-field Validation（如无证据 `Fact` 降级、引用与结论主体一致）→ Output Completeness Validation。
