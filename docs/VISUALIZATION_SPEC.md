# 可视化规格（VISUALIZATION_SPEC）

**版本：** 0.4（对齐 V4；页面定义见 [DASHBOARD.md](DASHBOARD.md)）  
**原则：** 图表服务监测问题；标注样本量与加权样本量；raw 与 weighted 并列。

---

## 1. Phase 1 页面与主图

| 页面 | 主图建议 |
|------|----------|
| Overview | KPI 条、加权情感趋势、国家排名横条、正负面代表文、新闻候选与预警列表 |
| Countries | 量/加权量趋势、raw+weighted 情感分布、Topic/Frame、来源贡献 |
| News & Events | 候选簇表、覆盖国家/来源、关联文章 |
| Articles | 可筛选文章表 + 详情证据 |
| Reports | 列表 + 证据展开 |
| Alerts | 规则触发表 + 证据 |
| Sources & Quality | 状态表、成功率、费用；不与舆情主结论混排 |
| Research | 可后置；跨国热力图等 |

---

## 2. 约束

1. 情感与立场**不得**共用一张含义不清的图  
2. 原始 Article Count 与 Weighted Article Volume **并列**，不可互相替代  
3. 不用一张图混合主题+情感+立场+框架  
4. 时间趋势必须显示样本量（与加权量）  
5. Attention Share 分母不可靠时不展示正式值  
6. 冷启动期降权「异常/风险」视觉  
7. 地图仅辅助  
8. Streamlit MVP  

---

## 3. 下钻

`Overview / Alerts → Country / News candidate → Segment → Articles → Evidence → Report`
