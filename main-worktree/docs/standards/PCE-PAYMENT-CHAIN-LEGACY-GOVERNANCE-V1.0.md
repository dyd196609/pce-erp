# PCE-PAYMENT-CHAIN-LEGACY-GOVERNANCE-V1.0

治理版本：V1.14.2.8.4.7.56

## 1. 适用范围

本规范适用于付款链全部遗留模块。治理是对既有状态、动作和事实来源的收敛，不得借治理之名重放业务动作、重新生成对象或修改生产数据。

扫描必须覆盖 `backend` 与 `frontend/src`，并固定输出：

- `stateMachineCoverageReport.json`
- `businessActionCoverageReport.json`
- `factConsistencyGapReport.json`

报告必须逐模块记录文件证据、风险等级和 `migrationStatus`。允许的迁移状态只有：

- `migrated`
- `partially_migrated`
- `legacy_observability_gap`

存在遗留缺口时必须如实进入 backlog，不得用全局公共能力存在来宣称全部模块已迁移。

## 2. 状态机治理

所有正式业务状态的初始化和后续变化必须由服务端统一状态转换服务在数据库事务内完成。每次真实转换必须写入 `BusinessStateTransition`，并完整记录：

- `sourceStatus`
- `targetStatus`
- `operator`
- `timestamp`
- `reason`
- `version`
- `auditReference`

实现层字段可使用 `sourceState`、`targetState`，但对外事实语义必须保持一致。

禁止：

- 页面直接修改业务状态；
- service 直接 `save()` 状态字段；
- `QuerySet.update(status=...)`；
- `bulk_update(..., ["status"])`；
- 使用 `localStorage` 保存或恢复正式业务状态；
- 客户端重新计算状态转换历史或数量；
- 对 `statusTransitionCount` 使用 `Number(value || 0)`、固定 `0` 或其他默认值。

强制满足：

`statusTransitionCount === statusTransitionHistory.length`

不满足时 `stateMachineConsistent=false`，页面、资格和后续动作必须阻断。

## 3. 业务动作治理

所有生命周期动作、跨模块动作和批量动作必须来自 `BusinessActionRegistry`。每个动作必须声明：

- `actionCode`
- `displayName`
- `allowedRoles`
- `allowedStatus`
- `singleOrBatch`
- `serverEligibilityCheck`

Vue 页面不得硬编码按钮名称、状态矩阵、批量动作名称、下一模块路由或权限结论。页面只提交服务端当前事实、当前选择和动作意图。

批量动作必须同时校验选择数量、所有选中对象状态、组织权限和服务端资格。状态变化后必须重新解析 Registry。

## 4. 页面事实治理

API、页面、复制诊断和 `strictFacts` 必须复用同一服务端事实对象，并共同声明：

`currentStateSource=server`

四表面必须保持：

- API 数量 = 页面数量；
- 页面数量 = 诊断数量；
- 诊断数量 = `strictFacts` 数量；
- 状态、转换历史、转换数量和一致性结论逐项相等。

页面不得以路由参数、页面内存、Store、`localStorage` 或测试注入对象补齐正式事实。

## 5. 页面动作与错误恢复

页面必须继承 `PCE-WEB-ACCEPTANCE-V1.1`。动作按钮随服务端状态动态变化，不得固定显示。

任何动作失败或错误提示关闭后，必须保留：

- 当前数据；
- 当前选择；
- 当前排序；
- 冻结列；
- 横向滚动位置。

错误恢复不得依赖刷新页面。

## 6. 风险分级与迁移顺序

- Level 1：`payment_request_prepare`、`payment_request`、`payment_instruction_prepare`、`payment_order_prepare`、`payment_order_draft`、`payable_confirm`
- Level 2：`ap_draft`、`purchase_invoice_prepare`、`purchase_reconciliation`
- Level 3：其余付款链模块

单个版本只能将实际完成状态机、Registry 和四表面事实门禁的模块标记为 `migrated`。其余模块保持原风险等级，不得一次性伪迁移。

## 7. 数据与归档保护

治理前后必须记录开发数据库和金丝雀数据库 SHA-256，并证明：

- `productionUserDataWritten=false`
- 未自动执行影响生产数据的 Migration；
- 未重放业务动作；
- 未隐式创建下游对象。

只有状态机事实、Action Registry、四表面事实和数据库保护全部通过，且检查点 `immutable=true`，才允许归档。

## 8. V57 采购付款上游治理

`payable_confirm`、`purchase_invoice_prepare`、`purchase_accounts_payable_draft`
和 `purchase_reconciliation` 适用同一契约，不得建立上游模块私有例外。

1. 对账对象必须从 `draft` 统一初始化，并通过“完成采购对账”动作写入带权威审计引用的状态转换；测试夹具、管理命令和金丝雀初始化也不得直接初始化为 `matched`。
2. 发票准备只有服务端校验成功可以执行 `draft -> prepared`；发票资料保存不得自行改变正式业务状态。
3. AP 草稿和应付确认准备虽然当前只有初始状态，也必须通过统一初始化服务创建，并输出零条但一致的持久化转换事实。
4. 生成采购发票准备、保存/校验发票资料、生成 AP 草稿及跨模块导航都必须注册；目标模块生成动作的权限复核必须读取服务端来源对象事实。
5. 页面初始化不得用固定 `0` 或空数组伪装未读取的转换事实；读取完成前使用 `null`，读取后原样透传服务端 `strictFacts`。
6. 遗留数据库只允许在文件名和设置开关双重隔离的验收副本中，依据既有已提交审计补录转换事实；不得对开发库、金丝雀库或生产库运行该补录。
