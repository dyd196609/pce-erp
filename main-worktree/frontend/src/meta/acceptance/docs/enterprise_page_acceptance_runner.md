# PCE-ERP 页面验收自动运行器

版本：V1.14.2.8.4.22  
状态目标：`PAGE_ACCEPTANCE_RUNNER_READY`

## 架构

CLI 或调用方提供页面 URL 和运行模式。Runner 按固定顺序执行：创建 Run、解析页面、匹配模板、建立 Evidence Plan、调用 V21 Evidence Engine、规则判定、报告生成和不可变归档。

页面解析优先读取业务页面权威注册表。模板匹配顺序为 pageCode 精准匹配、moduleCode 匹配、公共母模板；页面身份未登记时保持 `UNKNOWN`，不会猜测模板。

## 运行状态

运行实例只允许 `CREATED → RUNNING → COMPLETED → ARCHIVED`，任一步骤异常进入 `FAILED`。运行记录包含页面、模板、模式、采集器数量、证据数量和最终结果。

## 安全边界

Runner 必须以 `readonly=true` 启动。`create`、`update`、`delete`、`submit`、`approve`、`execute` 和 `post` 被业务动作门禁阻断。浏览器采集只读取页面、GET API、服务端事实、DOM、性能和刷新状态，不触发业务按钮。

数据库 Hash 基线在认证上下文建立后获取，页面验收结束后再次计算。归档仅在 `businessWriteCount=0`、`productionUserDataWritten=false` 的只读证据上下文中生成。

## CLI

正式模式：

```text
node scripts/runEnterprisePageAcceptance.mjs --url /scm/purchase-request --mode production
```

金丝雀模式：

```text
node scripts/runEnterprisePageAcceptance.mjs --url /scm/purchase-request --mode canary --scenario HAPPY_PATH
```
