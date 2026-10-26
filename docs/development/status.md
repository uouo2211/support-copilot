# 当前开发状态

更新于 2026-10-26（Asia/Shanghai）。**演示可用，不可对外生产使用。**

本次在原工程基础上补齐了缺失的运行入口，并把演示运行时切到 SQLite，使完整业务闭环可以在本机真实跑通。
PostgreSQL + pgvector 的容器化部署路径保留在 `Dockerfile` 与 `compose.yaml`，但本次未在该路径上验证。

## 本轮补全内容

| 位置 | 补了什么 |
| --- | --- |
| `app/main.py` | 应用入口、静态资源挂载、健康检查、统一错误页（原 Dockerfile 已引用但模块缺失） |
| `app/api/web.py` | 页面路由：工作台、会话、草稿编辑确认、知识审核、资讯、操作留痕 |
| `app/api/health.py` | `/health/live` 与 `/health/ready` 探针（原 compose 依赖但未实现） |
| `app/templates/` | Jinja2 + Bootstrap 5.3 界面，含中文工作台 |
| `scripts/seed_demo.py` | 演示数据种子，幂等可重复执行 |
| `scripts/verify_*.py` | 场景与闭环的自动验证脚本 |
| `app/repositories/access.py` | 修复一处权限查询缺陷（详见下方） |

## 已验证通过

运行 `python scripts/verify_demo.py` 与 `python scripts/verify_closed_loops.py` 实测：

- 版本相关问答能命中对应版本证据，并排除其他版本文档
- 产品版本未知时返回澄清，不硬答
- 跨客户数据查询被拦截（`CUSTOMER_SCOPE`）
- 同一版本正式证据冲突时转技术，不在矛盾中二选一（`EVIDENCE_CONFLICT`）
- 高风险操作请求转技术并声明不执行数据库命令（`HIGH_RISK`）
- 提示词注入被拒绝（`UNTRUSTED_INSTRUCTION`）
- 群聊候选知识：审核前不进索引 → 发布后被引用 → 撤销后不再被引用
- 撤销后，引用了失效证据的未确认草稿在确认时被拦截（HTTP 409）
- 编辑 → 确认 → 标记人工已回复，且改动后确认状态失效需重新确认
- replay 资讯快照 A/B 幂等去重

## 未验证 / 未完成

- `AI_MODE=live` 真实模型调用，以及 embedding + pgvector 向量检索：代码已实现，本机未接真实接口，未实机验证
- 评估集 40 条固定样本（`evals/` 目录仍为空）
- 业务效果数据（采纳率、处理时长、成本）无试用数据，不估算、不编造
- Docker Compose 容器化路径未在本目录验证
- 浏览器兼容性、移动端布局未做系统检查

## 本轮修复的原有缺陷

`Access.customer()` 原先调用 `scope(Customer)`，而 `Customer` 实体本身没有 `customer_account_id` 字段，
任何走到 `Access.evidence()` 的路径都会抛出 `AttributeError`。已改为按客服分配关系直接校验客户归属，
授权语义不变：客户范围由服务器维护，不信任调用方传入的客户标识。

该缺陷的存在说明原仓库代码在运行本文提到的补全之前从未被实际执行过。
