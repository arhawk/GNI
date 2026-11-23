# ADR 0003：MVP 调度采用 Cron / APScheduler

- **状态：** 已接受  
- **日期：** 2026-11-23  

## 背景

需要定时采集、分析与报告。原稿曾提 Prefect。

## 决策

MVP 使用 **系统 Cron 或 APScheduler**。Prefect / Celery / Redis 队列 **非 MVP 强制依赖**。

Phase 0 **只记录选型**，不实现完整调度器。

## 理由

- 日批/小时批场景足够简单  
- 减少基础设施与心智负担  
- 任务复杂度上升后再评估工作流引擎  

## 后果

- 需自行处理重叠运行与失败告警（Phase 1）  
- 文档与 Compose 中不默认部署 Prefect  

## 备选

Prefect、Celery+Redis、Kafka：推迟。
