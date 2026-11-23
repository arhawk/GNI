# ADR 0004：模型供应商抽象层

- **状态：** 已接受  
- **日期：** 2026-11-23  

## 背景

文章结构化分析依赖 LLM；供应商与价格可能变化。

## 决策

所有模型调用经 `BaseLLMProvider`（analyze / generate / embed）。  
默认配置面向 **DeepSeek API**，但业务代码不绑定具体 SDK 调用散落各处。  
Embedding 候选 **BGE-M3**（Phase 2 重点）。

正式**统计指标禁止**由 LLM 直接生成数值。

## 理由

- 可替换、可测试（Mock Provider）  
- 便于记录 model/prompt/schema 版本与成本  
- 与「证据驱动、可追溯」一致  

## 后果

- Phase 0 仅提供接口占位与 `.env.example`，不连接真实付费 API  
- 须实现缓存、预算、重试与降级（Phase 1-C）  

## 备选

业务内直呼单一 SDK：否决。
