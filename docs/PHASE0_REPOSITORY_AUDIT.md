# Phase 0 仓库审计报告

**项目：** Global Narrative Intelligence（GNI）  
**审计日期：** 2026-11-23  
**审计类型：** 只读（Step 0）  
**权威依据：** Blueprint V2 + Phase 0 实施任务书

---

## 1. 当前项目结构

| 路径 | 说明 |
|------|------|
| `/Users/zl/gh/Global_Narrative_Intelligence` | 工作区根目录 |
| `.git/` | Git 仓库已初始化 |
| `.cursor/` | 空目录 |
| `.DS_Store` | macOS 系统文件（应忽略） |

审计时点：**无** `README`、`pyproject.toml`、`src/`、`docs/`、`tests/`、`docker-compose.yml`、`.env`。

结论：绿场（greenfield）空仓库。

---

## 2. Git 状态

| 项 | 值 |
|----|-----|
| 分支 | `main` |
| 提交 | 无（尚无首次 commit） |
| Remote | 无 |
| 工作区 | 仅有未跟踪的 `.DS_Store`（审计时） |

---

## 3. 运行环境

| 项 | 值 |
|----|-----|
| 本机 Python | 3.14.6（`/opt/homebrew/bin/python3`） |
| 依赖管理 | 无 `pyproject.toml` / `requirements.txt` |
| Docker | 未配置 |
| 测试 | 无 pytest |
| 密钥文件 | 未发现 `.env`（仅检查存在性，未读取内容） |

**风险：** 本机 Python 3.14 可能与部分依赖不兼容。工程应钉 Docker/CI 为 **Python 3.12**，README 标明推荐版本。

---

## 4. 可复用内容

无业务代码、无既有文档、无既有配置可复用。仅保留空 Git 仓库壳。

---

## 5. 缺失内容（相对 Phase 0 交付要求）

- 产品与范围文档（PRD、PRODUCT_SCOPE、DEVELOPMENT_PLAN）
- 竞品、来源治理、合规文档
- Taxonomy、指标、可视化、AI 分析、架构、数据库、ADR
- 工程骨架（`src/gni`、配置、日志、pytest、Docker Compose）
- `.env.example`、README、验收报告

---

## 6. 潜在冲突

无既有技术栈冲突。与 Blueprint V2 / 任务书的「不一致」表现为**能力与文件完全缺失**，而非选型冲突。

原稿 `writing-block.md` 与 V2 冲突处以 **V2 为准**（三期切分、Cron/APScheduler、综合分后置、冷启动、合规、证据硬约束）。

---

## 7. 风险

1. 空库冷启动：无历史基线，Phase 1 初期不得发布确定性异常结论。  
2. Python 版本：本机 3.14 vs 项目目标 3.12。  
3. 来源核验未完成：不得编造 RSS/API；候选表状态为 TBD。  
4. 俄/印来源：可达性、语言、合规风险较高，接通顺序靠后需审慎评估。

---

## 8. 建议保留 / 调整 / 新增

| 动作 | 内容 |
|------|------|
| 保留 | `.git`、仓库名 `Global_Narrative_Intelligence` |
| 忽略 | `.DS_Store`、`.env`、密钥（写入 `.gitignore`） |
| 新增 | `docs/` 全套 Phase 0 文档、`src/gni/` 骨架、`tests/`、`pyproject.toml`、`docker-compose.yml`、`.env.example`、`README.md` |

---

## 9. 已确认产品决策（审计后冻结）

| 决策 | 值 |
|------|-----|
| MVP 国家短名单 | 美国、俄罗斯、德国、印度、澳大利亚（US / RU / DE / IN / AU） |
| 首批接通顺序 | 美 → 俄 → 德 → 印 → 澳 |
| 文档/报告语言 | 中文（专有名词可保留英文） |
| 执行节奏 | D 三段式 |
| 综合舆情总分 | MVP 不做；Phase 3 可配置指数 |

---

## 10. 审计结论

仓库为空，可安全按任务书从零建立文档与最小工程骨架。  
**下一步：** 段 1 产品文档 → 段 2 分析与架构 → 段 3 骨架与验收；Phase 0 完成前不进入 Phase 1 业务实现。
