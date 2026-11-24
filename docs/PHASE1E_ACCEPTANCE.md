# P1-E 验收报告

**日期：** 2026-11-24  
**状态：** 通过  
**依据：** [DASHBOARD.md](DASHBOARD.md)、[PHASE1_TASK_BRIEF.md](PHASE1_TASK_BRIEF.md)

---

## 1. 交付目标

Streamlit V4 八页导航 + 全局筛选（默认 Target=China）；raw/weighted 并列；可下钻文章。

---

## 2. 验收清单

- [x] Overview / Countries / News / Articles / Reports / Alerts / Sources / Research 可切换  
- [x] 全局筛选可用；情感与立场分图  
- [x] 质量与舆情分区（Sources & Quality）  
- [x] 图表标注样本量、加权量、分母/版本  
- [x] Attention Share 不可靠时不展示正式值  
- [x] News / Reports / Alerts：P1-F 前为空态占位列表  
- [x] **未**实现完整报告生成与规则预警引擎（P1-F）

---

## 3. 启动

```bash
pip install -e ".[dashboard]"
gni dashboard
# 或: streamlit run src/gni/dashboard/app.py
```

## 4. 主要产物

| 模块 | 路径 |
|------|------|
| App | `src/gni/dashboard/app.py` |
| Data | `src/gni/dashboard/data.py` |
| Pages | `src/gni/dashboard/pages_view.py` |
| CLI | `gni dashboard` |

**版本：** package `0.1.5`  
**停止线：** 不自动进入 P1-F，除非用户明确授权。
