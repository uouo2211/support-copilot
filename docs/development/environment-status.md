# 本次工作环境记录

记录日期：2026-10-21（Asia/Shanghai）。这是历史操作记录，不是安装或清理指令。

用户要求暂停本机改动后，已停止依赖安装和服务启动，仅继续编写仓库配置。

## 暂停前已经发生

- repo 内生成 `.venv/`，使用现有 Codex 工具运行时的 Python 3.12.14，并安装项目依赖；未更换系统 Python。
- repo 内生成 `.env`，包含随机会话密钥；文件权限为 0600，已排除 Git 和 Docker 构建。
- `/private/tmp/support-copilot-uv.tar.gz` 与 `/private/tmp/uv-aarch64-apple-darwin/`：下载并解压 uv 0.9.5。
- `/private/tmp/support-copilot-pg/`：通过现有 conda 安装独立临时环境，含 PostgreSQL 16.15 和 pgvector 0.7.4；没有激活或替换 conda base 环境。
- `/private/tmp/support-copilot-pgdata/`：执行了 `initdb`，创建空数据库集群，未启动数据库服务器。此临时集群使用 trust 认证，仅为之前准备的本地测试，不应作为正式部署数据目录。
- uv/conda 在各自用户缓存目录产生下载和索引缓存，conda 可能记录临时环境注册信息。
- repo 内生成了 `uv.lock`、本地静态资源、迁移 SQL 及 Python 字节码缓存。

## 没有执行

- 没有安装 Docker 或创建 Docker 容器、网络、卷。
- 没有执行 PostgreSQL 服务器启动命令，没有为项目创建业务数据库或执行迁移、种子导入。
- 没有启动 Web/worker，也没有注册开机自启动服务。
- 没有创建云资源，没有连接真实模型 API。
- 没有创建远程仓库、Git commit 或 push。

执行环境不允许读取系统进程列表，因此这里依据实际执行的命令记录，不声称已检查整台 Mac 的全部服务。`initdb` 已正常退出。

## 清理约定

目前保留上述文件，不自动删除。用户明确要求清理后，仅删除本次创建的 repo 虚拟环境或对应临时路径，不清空共享的 uv/conda 缓存、不更改已有系统或 conda base 环境。`uv.lock` 和 requirements 导出属于交付仓库内容，应保留。
