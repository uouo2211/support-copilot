# 第三方静态资源

固定版本资源随 repo 本地保存，未来页面不依赖 CDN 在线加载。本轮不下载新资源或改写上游文件。

| 文件 | 固定版本 | 上游项目 |
| --- | --- | --- |
| `bootstrap-5.3.3.min.css` | Bootstrap 5.3.3 | https://github.com/twbs/bootstrap/tree/v5.3.3 |
| `bootstrap-5.3.3.bundle.min.js` | Bootstrap 5.3.3 | https://github.com/twbs/bootstrap/tree/v5.3.3 |
| `htmx-2.0.4.min.js` | HTMX 2.0.4 | https://github.com/bigskysoftware/htmx/tree/v2.0.4 |
| `lucide-0.468.0.min.js` | Lucide 0.468.0 | https://github.com/lucide-icons/lucide/tree/0.468.0 |

保留文件内上游声明。完整许可证收集、供应链检查和浏览器验证尚未完成，不能据此宣称具备发布条件。升级时应显式更新版本、锁定文件来源，并执行页面回归，不直接修改压缩文件。
