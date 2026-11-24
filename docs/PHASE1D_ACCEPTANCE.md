# P1-D 验收报告

**日期：** 2026-11-24  
**状态：** 通过  
**依据：** [PHASE1_TASK_BRIEF.md](PHASE1_TASK_BRIEF.md)、[METRICS.md](METRICS.md)

---

## 1. 交付目标

- 七项研究核心：Article Count、Unique Story Count、Attention Share、Sentiment / Stance / Frame Distribution、Topic Share  
- 加权/运营：Weighted Volume/Score/Distribution、N/P、Sentiment Coverage、Source/Country Coverage  
- **原始 + 加权双视图**；LLM **不**算正式指标  
- Attention Share 分母门禁（不可靠则 `unavailable`）

---

## 2. 验收清单

- [x] 每项含 numerator / denominator / 范围 / 去重 / 版本  
- [x] Attention Share：分母 = 同源全量有效报道；空分母 → `unavailable`  
- [x] raw / weighted 并列输出（`results.views`）  
- [x] `metric_runs` 落库；CLI `gni metrics run`  
- [x] pytest 覆盖口径  
- [x] **未**实现 Streamlit 看板（属 **P1-E**）

---

## 3. CLI

```bash
gni metrics run --days 7
gni metrics run --country US --source src_id --days 30
```

## 4. 看板从哪一步开始？

| 段 | 看板 |
|----|------|
| P1-A → P1-D | **无看板**（采集 / 处理 / 分析 / **指标 JSON+库表**） |
| **P1-E** | **开始有看板** — Streamlit V4 导航（Overview / Countries / News / Articles / …） |
| P1-F | 报告、预警、重大新闻候选（看板可挂入口） |

**结论：看板从 P1-E 开始。**

## 5. 主要产物

| 模块 | 路径 |
|------|------|
| 计算 | `src/gni/metrics/compute.py` |
| 编排 | `src/gni/metrics/service.py` |
| Migration | `alembic/versions/20261124_0004_p1d_metrics.py` |

**版本：** package `0.1.4` · `metric_definition_version=metrics_v0.4`  
**停止线：** 不自动进入 P1-E，除非用户明确授权。
