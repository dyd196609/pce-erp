# PCE-BUSINESS-ACTION-CONTRACT-V1.0

> 权限硬约束：所有动作同时继承
> `PCE-BUSINESS-ACTION-PERMISSION-V1.0`。前端展示不是权限，服务端验证才是权限。

版本：V1.14.2.8.4.7.55.1

## 目标

PCE 页面不得自行决定业务动作名称、当前动作、批量动作、下一模块或禁止动作。公共 `BusinessActionRegistry` 是页面业务操作动作的唯一契约来源。

## 输入

- `currentModule`：当前业务模块编码。
- `currentStatus`：服务端当前业务状态；遗留页面迁移期间仅允许使用注册页面状态。
- `selectedRows`：用户当前选择对象，不得由隐藏记录或筛选外记录补齐。
- `permissions`：当前用户业务动作权限。
- `eligibility`：服务端下一步资格；客户端不得自行改写。
- `routeQuery`：只读导航上下文。

## 输出

- `availableActions`：当前允许的单对象业务动作。
- `batchActions`：根据全部所选对象状态、选择数量、权限和资格派生的批量动作。
- `nextModule`：唯一下一模块。
- `nextRoute`：唯一下一模块路由。
- `forbiddenActions`：未满足状态、权限或资格以及当前版本禁止的动作。

每个动作至少包含：

- `actionId`
- `actionName`
- `actionType`
- `scope`
- `permission`
- `allowedStatuses`
- `handlerType`
- `targetRoute`
- `enabled`
- `disabledReason`

## 强制规则

1. 所有业务操作必须由 Action Registry 驱动。
2. 页面不得硬编码生命周期、跨模块或批量动作名称。
3. 批量动作必须对全部所选对象执行同一状态校验；混合状态不得误放行。
4. `eligible=false` 时，需要下一步资格的动作必须进入 `forbiddenActions`。
5. 状态改变后必须重新解析注册表；例如采购应付核对由 `draft` 变为 `checked` 后，批量动作必须从“批量完成应付核对”切换为“批量进入供应商结算”。
6. 付款申请 `approved` 且服务端资格通过时，必须提供“进入付款指令准备”。
7. 动作错误不得清空表格、选择、排序或滚动上下文。
8. 银行发送、付款执行、付款凭证、核销、总账和过账未被当前版本显式注册时一律禁止。
9. 业务动作页面必须具备真实服务端数据，并同时证明数据存在、动作存在、动作可执行和结果可验证；空表或内存路由模拟不能替代真实用户路径。
10. 单条动作要求恰好选择一条记录；批量动作要求至少选择两条记录。选择数量不足时必须禁用并提供稳定的 `disabledReason`。
11. 需要服务端资格的跨模块动作必须在每次导航前逐条重新调用 eligibility API；页面、URL、Store、`localStorage` 和注册表中的旧资格只用于展示，不可作为最终放行依据。
12. 进入下一模块仅形成带来源标识的导航上下文，不得隐式创建目标对象；验收必须比较动作前后目标对象数量。

## 机器实现

- 注册表：`frontend/src/meta/runtime/pceBusinessActionRegistry.js`
- 渲染器：`frontend/src/meta/components/PceBusinessActionBar.vue`
- 静态守卫：`frontend/scripts/verifyPceBusinessActionContractV551.mjs`
- V55.1 用户路径：`frontend/scripts/verifyPceBusinessActionUserPathV551.mjs`
- V55.1.1 真实数据验收：`frontend/scripts/verifyPceBusinessActionRealDataV5511.mjs`

## V56 遗留动作治理

1. Registry 动作必须显式提供 `actionCode`、`displayName`、`allowedRoles`、`allowedStatus`、`singleOrBatch` 和 `serverEligibilityCheck`。
2. 静态扫描必须同时检查注册缺失和页面硬编码；页面已有 `data-action-id` 不代表已接入 Registry。
3. 未迁移模块必须标记为 `partially_migrated` 或 `legacy_observability_gap`，不得因相邻模块已注册而宣称完成。
4. V56 扫描器：`frontend/scripts/verifyPaymentChainLegacyGovernanceV56.mjs`。

## V57 采购付款上游动作治理

1. 注册动作除既有字段外，必须显式暴露 `displayName`、`allowedRoles`、`allowedStatus`、`singleOrBatch` 和 `serverEligibilityCheck=true`。
2. 创建目标对象的动作必须以来源对象作为权限事实；例如“生成采购应付账款草稿”由 AP 草稿模块注册，但统一权限校验器必须读取采购发票准备的服务端状态与法人范围。
3. 页面可使用 `includeActionIds` 将公共动作栏限定为当前区域的注册动作，但不得因此跳过统一权限 API、服务端资格或状态矩阵。
4. V57 静态门禁：`frontend/scripts/verifyPurchaseUpstreamGovernanceV57.mjs`。

## 诊断生命周期不得改变动作治理

共享壳的诊断提供者必须按页面实例注册和注销。修复跨页诊断时，不得新增页面硬编码业务按钮，不得绕过 Registry、权限 API 或服务端资格复核；复制诊断始终是只读动作。
