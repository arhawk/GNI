# 数据库迁移

P1-A 起使用 **Alembic**（配置见仓库根目录 `alembic.ini` 与 `alembic/`）。

```bash
gni db upgrade
# 等价：python -m alembic upgrade head
```

逻辑模型见 `docs/DATABASE.md` 与 `docs/ERD.mmd`。  
本目录仅保留说明；实际修订版本在 `alembic/versions/`。
