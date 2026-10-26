# 测试分层

| 目录 | 范围 | 当前状态 |
| --- | --- | --- |
| `unit/` | 纯函数与模块单元测试 | 仅有仓库静态检查器测试；业务单元测试待补 |
| `integration/` | PostgreSQL、迁移、权限与业务事务 | 占位目录，尚未实现 |
| `e2e/` | Playwright 工作台、审核、资讯和移动端 | 占位目录，尚未实现 |

静态检查器测试只用标准库：

```sh
python3 -B -m unittest discover -s tests/unit -p 'test_repo_structure.py'
```

业务测试继续采用原始需求指定的 pytest，浏览器使用 Playwright。上述标准库测试不是替代方案，只用于无需安装环境的仓库维护检查。

不要连接用户真实数据库。数据库测试需单独隔离的测试库与显式准备；任何清空或重置都必须限制在该测试库。实际通过情况记录在 [验证记录](../docs/development/verification.md)，不以目录或测试名称存在代替执行结果。
