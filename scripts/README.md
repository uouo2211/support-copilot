# 维护脚本

从仓库根目录显式运行；脚本不是自动安装钩子。下表区分只读检查与会改变环境的命令。

| 入口 | 操作范围 | 当前使用边界 |
| --- | --- | --- |
| `python3 -B scripts/check_repo.py` | 只读扫描 repo，不联网、不加载业务模块 | 本轮允许的静态检查 |
| `python3 scripts/init_env.py` | 创建缺失的 `.env`，不覆盖已有文件 | 需要用户同意准备运行配置 |
| `python -m scripts.seed` | 写入数据库中的演示数据 | 环境准备后显式执行；生产禁止 |
| `python -m scripts.freeze_schema` | 覆盖初始 schema SQL 快照 | 只用于初始生成，不用于后续迁移 |

安装依赖与容器启动由部署者选择，不在脚本中自动下载系统工具。`make init` 不只是目录初始化，它还会构建 Docker 镜像；执行前阅读 [部署说明](../docs/deployment/README.md)。
