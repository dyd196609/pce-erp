# PCE-CANARY-OPERATION-DATA-V1.0

版本：V1.14.2.8.4.7.57.1

## 目标

所有需要真实用户操作验收的页面必须具有服务端可持续读取的可操作金丝雀数据。验收数据用于验证页面状态、动作、权限和混合选择规则，不得伪装为正式业务对象。

## 对象契约

每个验收对象必须包含：

- `moduleCode`
- `scenarioCode`
- `objectState`
- `availableActions`
- `expectedAction`
- `preservePurpose`

对象必须同时提供服务端事实标识、证据哈希和组织范围。`availableActions` 与 `expectedAction` 必须引用 Business Action Registry 中已注册的动作编码。

## 数据池规则

1. 数据池必须按模块和状态保持最小可操作容量。
2. 单状态操作、已完成状态操作和混合状态批量选择必须同时可验收。
3. 数据只能写入明确标识的隔离验收数据库；管理命令必须使用设置开关和数据库文件名双重保护。
4. 页面不得把操作数据复制到 `localStorage`，不得修改正式业务对象状态。
5. API、页面、复制诊断和 `strictFacts` 必须复用同一服务端事实。
6. 金丝雀资格点击只验证权限、状态和动作契约；除非版本任务明确授权，不执行正式业务写入。

## 数据保护

禁止创建付款执行、银行任务、付款凭证、核销、总账、过账或银行流水对象。开发数据库和持久金丝雀数据库必须在验收前后比较 SHA-256。

## 归档门禁

只有同时满足以下条件才允许创建不可变检查点：

- 操作池容量满足模块契约；
- API、页面、复制诊断、`strictFacts` 一致；
- IAB 真实浏览器完成全部状态和混合选择场景；
- `businessWriteRequestCount=0`；
- `productionUserDataWritten=false`。
