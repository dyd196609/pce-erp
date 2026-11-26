# PCE-STATE-MACHINE-CONTRACT-V1.1

## 1. 服务端状态机

正式业务状态由服务端显式转换函数控制。客户端不得直接提交最终状态；任意非法跨级转换必须阻断、记录 expected/actual，并保持事务零部分写入。

所有业务状态必须通过状态转换服务产生。每次状态变化必须在同一事务写入唯一 `BusinessStateTransition`，至少记录业务类型、业务对象、前后状态、动作编码、工作流实例、操作人、转换版本和时间。禁止页面、脚本、初始化数据、管理后台或模块服务直接修改最终状态。

历史状态只能依据已提交的工作流、审批决策、业务审计和冻结快照受控补录转换记录；不得通过补录重新执行原业务动作。

## 2. 执行冻结

进入不可逆执行边界前，服务端保存版本化冻结快照和 `freezeHash`。快照至少覆盖金额、币种、付款账户、收款账户、银行路线、执行日期、来源风险版本和审批版本。

冻结后受保护字段禁止修改。确需变化时必须通过显式解除冻结、重新审批和重新冻结流程；不得原地覆盖快照或哈希。

## 3. 资格不等于执行

服务端 eligibility 只表达下游动作资格。资格为真不得自动创建下游任务、报文、执行、凭证、核销、总账或过账对象。

## 4. 单一事实模型

状态、审批、冻结、资格、阻断原因和下游数量统一由服务端事实模型派生并驱动 API、页面、诊断、`strictFacts` 与验收报告。

最终状态必须同时匹配完整转换历史。`submitted` 必须有工作流实例，`approved` 必须有审批决策，`frozen_for_execution` 必须有审批通过事实、不可变冻结快照、`freezeHash` 和对应转换记录。任一条件缺失时服务端资格必须为阻断。

## 5. 转换事实完整性

1. 所有业务状态必须通过统一状态转换服务。
2. 初始状态必须通过统一对象初始化服务产生，不得由页面、Provider、夹具或 ORM 直接写入。
3. 每次转换必须在同一事务中持久化 `sourceState`、`targetState`、`objectType`、`objectId`、`operator`、`timestamp`、`reason`、`version` 和 `auditReference`。
4. `auditReference` 必须绑定真实权威审计；对象、动作和操作人任一不一致时，转换事实无效。
5. `statusTransitionHistory` 和 `statusTransitionCount` 只能由服务端持久化转换表派生；Provider、页面内存、路由参数和诊断快照不得生成或补齐历史。
6. 遗留直接状态写入必须在覆盖扫描中如实标记模块、文件和风险等级，未迁移模块不得标记为符合。
7. `statusTransitionCount` 必须由服务端公共事实构造器按持久化历史长度派生；API、页面、复制诊断和 `strictFacts` 只能原样传递，不得固定值、不得默认 0、不得由客户端或 `localStorage` 重新计算。
8. 公共运行时契约必须强制 `statusTransitionCount === statusTransitionHistory.length`；不一致时立即失败，不得以默认值继续渲染或放行资格。

## 6. 付款链统一治理

1. 所有业务状态必须经过统一状态转换服务。
2. 五表面事实必须一致：API、页面、复制诊断、`strictFacts`、验收报告。
3. 付款链业务对象的初始状态和后续状态转换必须分别调用统一初始化服务与统一转换服务；模块服务不得直接赋值 `status`，不得通过 `QuerySet.update(status=...)` 或 `bulk_update(..., ["status"])` 绕过转换事实。
4. `statusTransitionHistory`、`statusTransitionCount` 和 `stateMachineConsistent` 只能由服务端持久化事实派生，客户端只负责校验并原样展示。
5. 状态机覆盖率报告必须区分业务对象、共享工作流内部对象和未迁移遗留对象；共享审批任务状态不得冒充业务对象转换历史，遗留模块不得标记为已符合。

## 7. V56 遗留扫描与默认值禁令

1. 付款链遗留治理必须同时扫描 `backend` 与 `frontend/src`，并逐模块输出 `migrationStatus`、风险等级和文件证据。
2. 状态字段的 `save`、`QuerySet.update`、`bulk_update`、页面赋值和 `localStorage` 持久化均属于独立扫描类别；基础设施事务状态必须与正式业务对象状态分开分类。
3. `statusTransitionCount` 不得使用 `Number(value || 0)`、`|| 0`、固定值或历史数组长度作为客户端默认或重算结果。
4. V56 详细规则继承 [PCE-PAYMENT-CHAIN-LEGACY-GOVERNANCE-V1.0](./PCE-PAYMENT-CHAIN-LEGACY-GOVERNANCE-V1.0.md)。

## 8. V57 上游模块状态事实

1. `PurchaseReconciliation` 的合法初始状态是 `draft`；`matched`、`difference_found` 和 `source_missing` 必须由统一核对转换产生。
2. `PurchaseInvoicePrepare` 的合法转换为服务端校验动作产生的 `draft -> prepared`，并且 `auditReference` 必须绑定本次已提交校验审计。
3. `PurchaseAccountsPayableDraft` 的初始状态为 `draft`，`PayableConfirmationPrepare` 的初始状态为 `prepared`；当前无后续转换时，空历史只有在对象仍处于合法初始状态时才一致。
4. 历史数据补录只能在隔离副本执行，必须复用既有已提交审计，不得修改对象状态、版本或重新执行业务动作。

## 9. 状态呈现与诊断生命周期

技术状态码必须保留，中文业务标签必须由服务端映射。页面路由切换不得让上一页面诊断覆盖当前状态事实；诊断注册生命周期修复不得创建第二套状态字段或状态机。
