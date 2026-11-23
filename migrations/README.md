# 数据库迁移

Phase 0 **不**提交具体 Alembic 修订。

Phase 1 起使用 Alembic（或等价工具）管理 schema；所有生产库变更必须有 Migration。逻辑模型见 `docs/DATABASE.md` 与 `docs/ERD.mmd`。
