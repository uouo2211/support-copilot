# 数据库迁移

| 文件 | 职责 |
| --- | --- |
| [env.py](env.py) | Alembic 环境与连接配置 |
| [versions/0001_initial.py](versions/0001_initial.py) | 初始迁移入口，创建 vector 扩展并加载冻结 SQL |
| [schema_v1.sql](schema_v1.sql) | 初始模型生成的 SQL 快照，独立于后续模型变更 |

当前迁移尚未在运行中的 PostgreSQL 上验证。数据库创建、迁移、回滚和恢复均属于显式环境操作，不因打开或整理 repo 自动执行。

后续 schema 变更添加新迁移，不覆盖 `schema_v1.sql`。`scripts/freeze_schema.py` 只用于初始快照生成，默认维护流程不执行它。初始 downgrade 被有意禁用，不能当作普通清理工具；正式恢复方案需备份及验证。
