# DO4 原功能保护关联（非冻结声明）

任务：PCE-ORDER-DELIVERY-PLANNING-DO4-OPERABLE-CLOSURE-20260913。

`currentFrozenVerifiedModuleIds=[]` 来自完整原 Registry，原 31 个模块实际有登记，状态为待当前复验、已漂移或仅计划。没有证据表明登记损坏；也没有完整用户验收＋当前非回归证明可将其升级为 FROZEN。DO4 追加 3 个受保护能力关联，原 31 项逐字保留。`completedModuleFreezeContractV1.js` 的 12 项契约仍为 `ACCEPTANCE_PENDING`。

## 阅读与修改前置回执

COMPLETED MODULE GOVERNANCE READING RECEIPT：Preservation Standard=V1.0 READ；Registry=全文 READ；Affected Frozen Modules=没有已验证冻结模块命中，不等于无保护；Freeze Contracts=Registry 无已签署合同，12 候选合同保持 ACCEPTANCE_PENDING；Unfreeze Authorization=NONE。上位及 Source AGENTS、开发规范 V1.2、保护 Preflight、正式 PCM V1.6、适用基础资料模板已读。修改前已在对话输出回执及 SAFE TO MODIFY。源码仅原销售页面、来源服务与其测试的保留式扩展；不改共享身份、列表、Workflow、库存或计算核心。

## 关联与回归

| 能力 | 原页面/API/权威 | 保护与本轮回归 |
|---|---|---|
| 销售订单与来源 | /sales/orders；/api/sales/*；SalesOrder/Item、ExternalIdentity、MasterDataWriteRequest、OrganizationOperatingAuditRecord | DO3 基线完整保留；DO4 只增加来源映射和确认动作；sales tests、原页面 Node 合同、最终 Vite |
| 订单计划语义 | /planning/requirements；/api/planning/facts/；planning.Demand/Requirement、只读 InventoryBalance | DO3 原件与实现不变；planning tests；6/2/4/4/0，订单库存覆盖仍未确认 |
| 六项线条核算 | /pde/engineering-calculations；/api/pde/a1-engineering/calculations/batch-reuse/；calculation_batch_reuse.py、EngineeringCalculationBatchPanel.vue | 原 71 行独立于37行；340/335/5＋48/48/0=388/383/5。继承 resume/closeout 证据，专项 7 Python＋4 Node 回归；无算法和数据修改 |
| 供应商/采购物料 | EnterpriseMasterDataPage；/api/procurement/suppliers/、/api/masterdata/materials/ | 原 Supplier/Material、编码、权限不变。读取候选不创建主数据 |
| 采购申请/采购订单 | ScmPurchaseRequestPage、ScmPage；scm-page-facts/purchase-request、purchase_orders | 原菜单、原采购链、Workflow与业务编号保留；verifyCompletedModuleContracts 的确定性合同回归 |
| 收货/检验/库存 | PurchaseReceivePage、QmsPage、FormalExecutionPage；formal-purchase-receipt-facts、formal-quality-facts、formal-inventory-facts | 不修改、不以快照伪装分配；同一既有合同回归。历史人工冲突不被本轮静态 PASS 覆盖 |
| 对账/结算 | PayableCheckPage、SupplierSettlementPage、PurchaseReconciliationPage；既有 reconciliation authority | 不修改其状态/权限/数据/菜单；同一既有合同回归。禁止资金或银行发送写入 |

共享依赖：PceListPageShell、PceEnterpriseListTable、PceEnterpriseAdvancedFilter、PceBusinessStatus、StandardListToolbar、原路由/流程注册、AuthorizationService、正式员工岗位职责及状态迁移服务均保持原实现。本轮代码只调用它们，不重建公共能力。

历史依据：DO2、DO3 FINAL_CONSOLIDATED 与 fingerprints；pce-pde-calculation-do1-resume-20260913 和 closeout 的报告及专项测试。当前真实运行事实高于自动化和登记。本轮没有把未登录的原浏览器、真实订单验收、CSV历史未验证状态或未复验模块改为 PASS。

精确回退：使用 DO4 baseline 与逐文件 diffs，只逆向本轮差异；新建来源模块与自有测试脚本可按清单移除。不得覆盖同时存在的用户修改、历史证据、任何持久化数据库或共享实现；不使用 Git reset/checkout/clean。
