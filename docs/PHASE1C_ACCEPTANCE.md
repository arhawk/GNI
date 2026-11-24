# P1-C 验收报告

**日期：** 2026-11-24  
**状态：** 通过（规则启发式默认；DeepSeek 可选）  
**依据：** [PHASE1_TASK_BRIEF.md](PHASE1_TASK_BRIEF.md)、[BLUEPRINT_V4_ADDENDUM_A1.md](BLUEPRINT_V4_ADDENDUM_A1.md)、[ARTICLE_ANALYSIS_SCHEMA.json](ARTICLE_ANALYSIS_SCHEMA.json)  
**数据五层补充：** 筛选结果属 Layer 3、分析属 Layer 4；见 [DATA_LAYERS.md](DATA_LAYERS.md)。

---

## 1. 交付目标

- L2 正文涉华判断（`china_related / not_china_related / uncertain / insufficient_text`）
- L3 涉华片段 + 原文定位校验
- China Relevance Level / Weight（provisional_v0.2）
- 六维结构化结果（Topic / Sentiment / Stance / Frame / Entities / Evidence）
- 版本与预算；LLM 可选（无 Key 时规则启发式）

---

## 2. 验收清单

- [x] L2 结果写入 `article_screenings`（stage=fulltext），可追溯
- [x] L3 spans 可在 `content_clean` 中定位；失败标 `validation_status`
- [x] relevance level/weight 与 Article Count 分存（`china_relevance_level` / `china_relevance_weight` + assessments 表）
- [x] Stance 绑定 Target；Schema `article_analysis_v0.2` 合规（启发式产出）
- [x] model/prompt/schema/taxonomy/weight 版本入库（`analysis_runs` / `article_analyses`）
- [x] 预算触顶停止分析、不阻断采集（`daily_article_limit` / LLM budget）
- [x] pytest 通过
- [x] **未**实现 Dashboard / 正式指标聚合（P1-D/E）

---

## 3. CLI

```bash
gni analyze run --once --limit 20
# 离线规则：默认 Heuristic；有 GNI_LLM_API_KEY 时可用 --provider deepseek
```

## 4. 主要产物

| 模块 | 路径 |
|------|------|
| L2 | `src/gni/analysis/l2_fulltext.py` |
| L3 | `src/gni/analysis/l3_spans.py` |
| Weight | `src/gni/analysis/relevance.py` |
| Heuristic 六维 | `src/gni/analysis/heuristic.py` |
| DeepSeek 可选 | `src/gni/analysis/deepseek.py` |
| 编排 | `src/gni/analysis/service.py` |
| Migration | `alembic/versions/20261124_0003_p1c_analysis.py` |

**版本：** package `0.1.3`  
**停止线：** 不自动进入 P1-D，除非用户明确授权。
