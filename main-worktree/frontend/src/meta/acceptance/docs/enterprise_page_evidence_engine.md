# PCE-ERP 页面验收证据采集引擎

版本：V1.14.2.8.4.21  
层级：Quality Infrastructure Layer

## 处理链

统一页面验收模板依次生成采集计划、调用只读采集器、形成标准证据、执行规则判定，并按页面验收归档标准写入不可变清单与 Hash。

业务事实只来自服务端事实对象。页面、API、复制诊断、`strictFacts` 与验收证据共享同一事实，不使用上一页缓存，也不在前端重新计算业务状态。

## 只读边界

采集器只允许读取路由、注册表、服务端响应、浏览器状态、文件和数据库 Hash。注册表拒绝声明 `create`、`update`、`delete`、`submit`、`approve`、`execute` 或 `post` 的采集器。

采集失败或证据缺失均记录为 `UNKNOWN`；不会自动转为 `PASS`。`N/A` 保留在报告中，且必须同时提供原因、确认人和证据引用。

## 自动接口

- `createRun(input)`：建立采集运行。
- `collect(runId)`：只读采集证据。
- `getEvidence(runId)`：读取证据。
- `evaluate(runId)`：执行判定。
- `archive(runId)`：归档证据。
- `getReport(runId)`：读取运行报告。

接口统一返回 `{ success, data, error, meta }`。

## 数据保护

浏览器验收在认证上下文建立后记录数据库基线 Hash；正式页面和金丝雀页面只读访问结束后再次计算 Hash。必须同时满足 `databaseHashUnchanged=true`、`businessWriteCount=0` 与 `productionUserDataWritten=false`。
