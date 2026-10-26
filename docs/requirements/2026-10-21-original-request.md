# 原始产品与工程需求

来源：本会话用户初始请求。记录日期：2026-10-21（Asia/Shanghai）。下方保留用户原文；这是需求基线，不是完成报告。后续环境操作限制见 [交流历史](../ai-history/2026-10-21-01-bootstrap-and-boundaries.md)，实现状态见 [开发状态](../development/status.md)。

## 用户原文

你是一名资深全栈工程师，请在当前工作目录实现可提交、可运行、可演示的 support-copilot 仓库。先检查已有文件与项目规范，保留用户已有内容；不要只给方案，要完成实现、测试、文档与运行验证。不要自动创建远程仓库、提交或推送 Git。

【1. 产品定位】
实现“企业客服 AI 助手”，假设服务于虚构 B2B 数据库运维平台 DataPilot，支持监控、备份、告警。所有产品能力、客户和群聊示例必须明确标注为演示数据。
业务闭环：客户提问 → 获取上下文 → 按权限与版本检索 → 生成带引用的草稿 → 客服编辑确认 → 人工回复或转技术 → 记录反馈 → 候选知识审核发布。
企业微信为主要业务场景，飞书为补充知识来源。MVP 使用网页工作台、文件导入和模拟事件，不假设普通群机器人可以读取任意群聊或全部历史，不执行客户数据库命令，不自动对外回复。

【2. 固定技术选型】
Python 3.12、uv、FastAPI、Pydantic v2、SQLAlchemy 2、Alembic、psycopg；PostgreSQL 16 + pgvector。提交依赖锁文件，使用固定兼容版本。
前端使用 Jinja2 + HTMX 2 + Bootstrap 5.3 + Lucide；静态资源固定版本并本地保存，中文界面、系统字体、响应式布局。不要 React，不做营销首页。
检索使用 jieba + rank-bm25；可选真实 embedding API + pgvector，以 RRF 合并排序。MVP 在服务器权限过滤后的候选集合中计算 BM25，不引入 Elasticsearch。
用 httpx 封装生成与 embedding provider，分别配置模型地址、密钥、模型名和超时；Pydantic 校验结构化输出，不引入复杂 Agent 框架。
Docker Compose 只包含 db、web、worker。worker 使用 PostgreSQL 持久化任务表与锁，不引入 Redis/Celery，不在 Web 进程中启动调度器。pytest 测试后端，Playwright 验证关键交互。

【3. 仓库与配置】
目录包含 app/{api,services,repositories,models,schemas,providers,connectors,jobs,templates,static}、migrations/、fixtures/、tests/{unit,integration,e2e}、evals/、docs/、scripts/，以及 Dockerfile、compose.yaml、pyproject.toml、uv.lock、.env.example、Makefile、README.md。
HTTP 层、业务逻辑、数据访问分离；权限过滤统一封装在 repository，避免每个接口各写一套。不要为简单功能建立过度抽象。
提供 make init/up/seed/test/eval/down；迁移和种子导入可重复执行，不重复写入、不覆盖已有 .env。默认 localhost:8000，可通过 APP_PORT 修改；提供存活与就绪检查。
默认 AI_MODE=mock、NEWS_MODE=replay、SEND_MODE=manual。mock 使用真实 BM25 检索和确定性证据摘录，不调用模型、不伪造 embedding，不把离线结果报告为真实模型效果。
live 模式调用真实模型，embedding 单独启用；未配置 embedding 时明确使用 BM25。失败必须显示错误或明确降级，禁止静默使用 mock 冒充模型成功。
配置至少包含 DATABASE_URL、SESSION_SECRET、AI_MODE、LLM_BASE_URL/API_KEY/MODEL、EMBEDDING_BASE_URL/API_KEY/MODEL/DIM、NEWS_MODE、APP_PORT；密钥仅保存在服务端。更换 embedding 模型需重建索引，不能混用向量空间。

【4. 数据与权限】
实现用户、客户、客服分配、会话、消息、知识及修订、来源、检索片段、答案草稿、回复动作、反馈、技术转交、行业资讯、任务和审计记录。
区分 organization_id、customer_account_id 和平台租户 ID；不同平台身份包含平台与应用命名空间。客户绑定由服务器维护，不能信任前端提供的 customer_id 或 role。
提供客服、知识审核员、技术支持三个角色及本地演示账号；使用密码哈希、服务端授权、HttpOnly Cookie、CSRF 防护。生产配置禁止默认凭据。
问答、来源预览、历史、导出和附件接口均校验组织、角色与客户范围；检索前过滤客户范围、可见性、版本、published 状态和有效期。原始聊天不能直接进入正式问答索引。
客户私有知识不能自动变成公共知识，脱敏不等于获得公开授权；公开化需审核员显式批准。提示词、日志、缓存、引用和外发内容也不能跨客户泄漏。缓存若实现，键必须包含授权与知识索引版本。

【5. 客服工作台】
展示会话列表、客户与产品版本、上下文、问题、建议答案、可展开引用、适用范围、缺失信息和处理状态；实现编辑、重新生成、复制、转技术、反馈。
答案结构为 answer、citations、applicability、missing_context、decision、reason_codes；decision 为 suggest/clarify/handoff/deny。引用由服务端解析证据 ID，不允许模型编造链接。
版本未知且影响答案时先澄清；版本使用结构化范围匹配，不能按字符串大小比较。来源权威性、相关性、版本匹配、有效期与证据一致性共同判断，不把模型自评当正确概率。
同版本证据冲突、越权、高风险操作采用硬规则；证据不足明确说明。群聊和网页是非可信数据，不能改变系统指令或触发高风险工具；输出做引用校验、隐私检查和 HTML 转义。
保存原始草稿、人工修改、引用和操作者；确认绑定具体文本版本与会话，修改后重新确认，重复点击幂等。发送前重新校验证据是否撤销或变化。
manual 模式使用“确认并复制”，客服在企微发送后可标记“人工已回复”；复制成功不是平台送达。内部引用与可外发引用区分，不能把内部群链接或敏感证据直接复制给客户。
技术转交记录问题、版本、已做排查、授权证据和缺失信息；人工采纳答案不意味着答案自动成为可信知识。

【6. 群聊知识更新】
实现企微、飞书 JSON/CSV 导入，统一 platform、platform_tenant、chat_id、message_id、sender、timestamp、reply_to、content；提供格式预览、大小限制、错误提示和幂等处理，客户范围由服务器绑定。
按回复链与有限时间窗口关联上下文，区分猜测、临时建议、已验证方案、正式文档；依次实现候选提取、脱敏、重复检测、冲突提示、人工审核、发布与索引更新。
状态包括 draft/pending_review/published/rejected/superseded/revoked；保存来源消息、验证材料、审核人、客户范围、产品版本、有效期及更新时间；未审核候选不能作为正式答案。
知识更新创建不可变修订；准备好检索片段后事务切换有效版本，失败保留旧版本。支持撤销与回滚，撤销立即影响检索和未发送草稿。
来源撤回或授权撤销后停用依赖知识并待复核；删除请求应同步处理原文、片段、向量和缓存，只保留合规所需的最小审计信息。

【7. 行业资讯】
实现 PostgreSQL News RSS https://www.postgresql.org/news.rss 与 AWS Security Bulletins RSS https://aws.amazon.com/security/security-bulletins/rss/feed/；来源白名单，遵守条款、限频及访问控制，禁止绕过 403。
每天 Asia/Shanghai 08:00 调度，持久化任务与游标，唯一任务键避免重复，支持重启补跑；仅对可恢复错误按 5 分钟、30 分钟、2 小时重试。
按 GUID、规范 URL、内容哈希去重；记录来源、原始链接、published_at、collected_at、摘要、分类、状态。发布时间缺失存 null，不用采集时间冒充。
replay 提供固定快照 A/B：A 两条，B 原有两条加一条新增；明确标注模拟资讯。live 失败可手动切换 replay，不能伪装当天有新增。资讯独立管理，不得覆盖 DataPilot 产品事实。

【8. 演示与测试】
准备客户 A/B、隔离客服账号、审核员、技术支持、至少 12 篇产品文档、3.1/3.2 两版本、两组平台消息、私有知识、冲突与过期条目。固定事实：3.1 支持 PostgreSQL 15，3.2 新增支持 PostgreSQL 16；备份案例为“查看了错误 prefix”，不要编造 S3 最终一致性原因。
验收四个场景：①3.2 告警问题检索引用、人工修改确认复制并记录回复；②群聊方案审核前不命中、发布后命中、撤销后停止引用；③RSS A→B→B 的记录数为 2→3→3；④版本缺失澄清、正式证据冲突转交、无依据拒绝编造、A 查询 B 数据及来源接口均被阻止。
建立40条固定评估：常见8、模糊4、版本6、冲突4、无答案4、越权6、注入4、资讯4；另测过期、撤销、幂等、CSRF、索引失败、重复确认。不能通过匹配固定问题硬编码答案。
README 写启动配置、账号、四个演示步骤、导入格式、重置和排障；docs 写 Mermaid 架构、平台权限矩阵、数据模型、安全边界、生产演进、五分钟录像脚本。企微/飞书权限参考官方文档，未实测的历史范围、费用与发送能力标注待验证。
报告区分 mock/live、目标/实测，记录答案与引用准确率、覆盖率、拒答、越权、p50/p95延迟、审核到可检索延迟；采纳率和处理时长无试用数据写未测，成本无实际token或价格写未测，不编造业务收益。
分阶段完成“基础闭环→知识审核→资讯→安全与评估”。实际运行测试和浏览器流程，检查桌面/手机布局和错误状态，所有按钮有真实行为；最后提供本地地址、测试结果、真实/模拟能力清单与已知限制，不能把未验证能力写成成功。
