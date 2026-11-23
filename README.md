# Global Narrative Intelligence（GNI）

全球官方媒体舆论信号采集与叙事监测研究系统。

**当前阶段：Phase 0（需求冻结与工程骨架）**  
尚未实现生产采集、完整 LLM 分析或事件聚类。授权前请勿当作 Phase 1 已交付。

## 文档入口

- [产品需求 PRD](docs/PRD.md)
- [产品范围](docs/PRODUCT_SCOPE.md)
- [开发计划](docs/DEVELOPMENT_PLAN.md)
- [架构](docs/ARCHITECTURE.md)
- [Phase 0 审计](docs/PHASE0_REPOSITORY_AUDIT.md)
- [Phase 0 验收](docs/PHASE0_ACCEPTANCE.md)

MVP 国家短名单：美国、俄罗斯、德国、印度、澳大利亚（接通顺序：美→俄→德→印→澳）。

## 环境要求

- **推荐 Python 3.12**（Docker/CI 以此为准）
- 本机若为 3.14，请优先使用 3.12 虚拟环境
- Docker（可选，用于 PostgreSQL）

## 快速开始

```bash
cd /Users/zl/gh/Global_Narrative_Intelligence
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env

# 冒烟测试（不访问外网 LLM、不采集）
pytest
gni health
gni version
```

启动本地数据库（可选）：

```bash
docker compose up -d db
```

## Phase 0 边界

| 允许 | 禁止 |
|------|------|
| 文档、ADR、ERD、Schema 草案 | 生产级多源采集 |
| 可安装包、配置、日志、CLI health | 真实付费 LLM 调用 |
| pytest 冒烟 | 正式日报发送 / Agent |

## 许可证

Proprietary — 内部研究用途。合规见 [docs/COMPLIANCE.md](docs/COMPLIANCE.md)。
