# 演示数据

这里所有产品能力、客户、文档、群聊和资讯均为演示数据，不是真实产品承诺或实时新闻。开发交流历史位于 `docs/ai-history/`，不得放入此目录或知识索引。

| 文件 | 类型 | 用途和约束 |
| --- | --- | --- |
| [documents.json](documents.json) | 16 篇演示产品文档 | 包含 3.1/3.2、私有、冲突与过期条目；版本事实为 3.1 支持 PG15、3.2 新增 PG16 |
| [wecom.json](wecom.json) | 企微格式的模拟导出 | 客户 A 备份案例，原因为查看了错误 prefix；未审核聊天不能入正式索引 |
| [feishu.csv](feishu.csv) | 飞书格式的模拟导出 | 客户 B 私有巡检示例，不可自动公开 |
| [news.json](news.json) | 模拟 RSS 快照 | A 取前两条，B 取全部三条；缺失发布时间保持 null |

## 导入约定

当前解析器位于 `app/connectors/imports.py`，支持 UTF-8 JSON 数组或带表头 CSV；单文件上限 1 MiB、1 至 500 条消息。HTTP 上传界面尚未实现。

字段为 `platform`、`platform_tenant`、`application_id`、`chat_id`、`message_id`、`sender`、`timestamp`、`reply_to`、`content`。时间必须包含时区；`reply_to` 可为空。`application_id` 用于不同平台应用身份命名空间隔离。

文件不能决定客户归属。平台、租户、应用与群必须匹配服务器授权绑定。不得向示例文件添加真实客户消息、密钥或员工信息。

种子入口为 `python -m scripts.seed`，会写数据库，当前未执行。测试使用 fixtures 时不得把加载文件误报成演示业务已运行成功。
