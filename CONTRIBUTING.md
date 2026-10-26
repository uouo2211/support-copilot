# 贡献与维护

开始前阅读 [当前状态](docs/development/status.md)、[工程结构](docs/architecture/README.md) 和 [协作约定](AGENTS.md)。

## 改动范围

1. 先确认当前用户请求和已有修改；不要以历史需求为由覆盖后续限制。
2. 保留根目录的标准部署与依赖入口，新增文档按 `docs/README.md` 分类。
3. 简单变更不引入无用抽象，不为目录美观移动可用模块或破坏导入路径。
4. 不改写 `.env`，不提交缓存、真实客户文件、数据库、密钥或完整敏感工具日志。
5. 未经明确授权，不安装依赖、运行 Docker、迁移数据库、启动服务或清理用户环境。
6. 不自动创建远程仓库、Git commit 或 push。当前目录尚未初始化 `.git`，本轮也不执行初始化。

## 无依赖静态检查

在仓库根目录使用现有系统 Python 执行，无须安装项目依赖：

```sh
python3 -B scripts/check_repo.py
python3 -B -m unittest discover -s tests/unit -p 'test_repo_structure.py'
```

检查目录、Markdown 本地链接、Python 语法、演示 JSON/CSV 和 requirements 固定版本格式，不替代锁文件一致性验证。这不是业务测试、Docker 验证或模型评估。`-B` 避免生成 Python 字节码缓存。

容器、后端、浏览器和真实模型验证须另行获得环境操作授权，并按 [部署说明](docs/deployment/README.md) 准备环境。不要把当前 `make up/test/eval` 的预定入口当成已经通过验证的功能。

## 数据与迁移

- fixtures 的增改需同步 [数据说明](fixtures/README.md)，保留演示、私有和过期标注。
- 初始 SQL 已冻结；新增 schema 修改应添加迁移，不重新运行 `scripts/freeze_schema.py` 覆盖历史。
- 模型、来源和回复安全边界变更必须增加相应测试；测试尚未执行时明确记录。
- 依赖通过 pyproject 和锁文件管理，requirements 从锁文件导出。不要直接改导出文件造成版本分叉。
- vendor 文件保留版本和上游信息，许可证完整性仍需在发布前检查。

## 文档与交流记录

- 原始需求在 `docs/requirements/`；新限制或决策写入 `docs/decisions/`。
- 实际进度维护在 `docs/development/status.md`，已运行检查写入 `verification.md`。
- 每轮有实质改动的 AI 协作在 `docs/ai-history/` 增加编号记录，并更新索引。
- 用户原话与助手可见回复尽量保留；摘要、摘录、脱敏和未记录项显式标注，不能声称人工整理是平台完整导出。
- 历史不保存系统/开发者指令、内部推理、密钥或敏感工具原始输出；也不能作为产品知识使用。
- 不静默修改旧记录来美化结果；更正用追加说明，新状态写新记录。
