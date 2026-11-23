# ADR 0002：PostgreSQL 为主库；pgvector 为 Phase 2 扩展

- **状态：** 已接受  
- **日期：** 2026-11-23  

## 背景

需要关系数据、全文检索潜力与未来向量召回（事件聚类）。

## 决策

- **主存储：** PostgreSQL  
- **向量：** pgvector，在 Phase 2 启用；Phase 0/1 不阻塞于向量索引  
- **不用** Neo4j 作为 MVP 依赖  

## 理由

- 单一运维面；JSONB 可承载分析结果  
- pgvector 满足跨语言 embedding 召回原型需求  
- 图数据库对 MVP 叙事研究非必需  

## 后果

- 事件多代表性向量用表 `event_embeddings` + `representation_type`，不为每国加列  
- 复杂图查询若未来需要再评估  

## 备选

独立向量库（Milvus 等）：MVP 否决；专用图库：否决。
