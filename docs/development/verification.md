# 仓库整理验证

日期：2026-10-21（Asia/Shanghai）。范围仅为本轮工程归类、文档和静态检查器，不是产品验收。

## 命令

```sh
python3 -B scripts/check_repo.py
python3 -B -m unittest discover -s tests/unit -p 'test_repo_structure.py'
```

## 实际结果

| 检查 | 实测结果 |
| --- | --- |
| `python3 -B scripts/check_repo.py` | 通过，扫描 59 个源码、文档和数据文件 |
| `python3 -B -m unittest discover -s tests/unit -p 'test_repo_structure.py' -v` | 14 项测试全部通过 |
| 非历史文档的旧路径搜索 | 未发现原 deployment/environment-status 路径残留；历史代码块按原文保留 |

执行环境为本机已有 `python3`，无第三方依赖。测试包括链接解析、代码块内历史链接排除、缺失路径、越界路径、固定版本格式、Python 只解析不执行、JSON/CSV 错误报告，以及当前 repo 全量静态检查。

Markdown 链接检查只验证内联本地目标文件，不验证锚点和远程站点。requirements 检查仅验证固定版本格式，不验证所有依赖兼容性或与锁文件的完整语义一致性。既有业务代码的语法解析不等于权限、事务和行为测试；先前 ruff 未使用导入提示也不因本轮检查通过而自动解决。

## 不在本轮范围内

- Docker 构建、Compose 启动、数据库连接、迁移与种子执行。
- 应用后端与安全测试、Playwright 桌面/手机验证。
- 40 条业务评估、mock/live 效果、延迟、采纳率、成本或真实平台能力。

检查器不读取 `.env`，忽略 `.venv`、缓存及报告目录，不导入应用模块，不访问网络，不创建服务或修改系统配置。
