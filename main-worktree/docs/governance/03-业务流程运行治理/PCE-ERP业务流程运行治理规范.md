# PCE-ERP业务流程运行治理规范

# 文档信息

- 版本：V1.14.2.8.18.20
- 用途：统一ERP业务节点、生命周期、交接、黄金路径和回归治理
- 适用范围：PCE-ERP全部端到端业务流程
- 优先级：高
- 关联规范：04页面与交互、05自动验收、06模块专项、07案例库
- 维护方式：持续更新

## 1. 节点九要素

每一个业务节点必须定义并验证：

1. `Input`：进入节点的必要数据；
2. `Source`：权威来源对象、编号和版本；
3. `Business Object`：当前节点唯一业务对象；
4. `State`：状态、标签、允许迁移和终态；
5. `Action`：用户可申请的动作；
6. `Guard`：状态、数据、权限、完整性和边界阻断；
7. `Output`：动作产生的当前节点结果；
8. `Handoff`：下一节点可恢复的交接；
9. `Acceptance`：自动与人工可重放证据。

缺少任一适用要素不得输出READY。

## 2. PROCESS规则统一定义

| 编号 | 权威定义 | 最低证据 |
|---|---|---|
| PROCESS-006 | 端到端业务Walkthrough：节点内部、节点交接、多入口一致、人工真实路径 | 对象编号、动作、前后状态、页面/接口证据 |
| PROCESS-008 | 业务不可破坏回归：黄金路径、状态、映射、禁止边界持续冻结 | 基线、升级前后、失败阻断 |
| PROCESS-009 | 一页一验收：每个可访问业务页面独立验收 | 页面身份、区域、字段、动作、异常、刷新、人工结果 |
| PROCESS-010 | 治理资产调用与问题闭环 | 读取清单、案例编号、规则更新、回归绑定 |
| PROCESS-011 | 流程节点真实运行验收 | Object、Page、Data Handoff、Human Loop、Entry Consistency、Action Executability、Route Identity、Context Separation及适用扩展项 |

## 3. PROCESS-011运行层

READY必须同时满足：

- `Object Exists`：Domain字段、状态、关系存在；
- `Page Exists`：唯一PageCode、Route、身份和区域存在；
- `Data Handoff`：来源编号、对象、数量和当前上下文一致且非Demo；
- `Human Action Loop`：用户选择、填写、确认、状态变化和下一节点交接闭环；
- `Entry Consistency`：菜单、上游按钮、批量入口和流程中心恢复同一业务实例；
- `Action Executability`：按钮可见、状态允许、数据完整、权限满足、执行结果正确；
- `Route Identity`：Route稳定并只表达页面身份；
- `Context Separation`：业务上下文由内部Resolver恢复；
- `Batch Completeness`：存在批量动作时全部子项完成；否则明确N/A；
- 模块扩展：Decision Revision、Inspection History等按专项规范执行。

静态“文件存在”不能代替真实Handoff和人工动作。

## 4. 生命周期冻结

- 生命周期必须由业务对象和State Contract定义，记录状态变化而不删除历史对象。
- 状态变化只由受控Action推动，禁止跨级、自动补齐或通过路由跳转冒充推进。
- 业务流程状态、审批状态、业务结论和外部执行状态必须分离。
- 完成、拒绝、退回、重开和重新确认必须保留Revision、Actor、Reason、At和证据。
- 下游对象只有在当前节点满足Guard后由独立动作创建；入口资格不等于对象已创建。

## 5. Golden Path与回归

每条关键流程建立Golden Path，冻结：输入对象、关键编号、动作序列、状态序列、Handoff、输出对象、禁止副作用和恢复入口。PROCESS-008回归至少包含正常、边界、异常三类样本，并验证旧能力、旧数据、旧入口和公共页面未被破坏。

失败用例必须证明Guard真实阻断；只跑成功路径不得判定完整。

## 6. 数据连续性与链路追踪

每个节点必须显示并验证`Upstream Object -> Current Object -> Downstream Entry State`。Production与Canary隔离；升级前、升级后、刷新和重入的数量与业务键一致。拆分、合并和批量场景必须保留`SOURCE_FROM/SPLIT_FROM/MERGED_FROM/GENERATED_FROM/REFERENCED_BY/DECISION_BASED_ON`关系。

已产生下游影响的Legacy事实保持原编号，以Alias映射Canonical身份；来源缺失记录MissingBusinessEvidence，禁止补造。

## 7. 节点与页面唯一映射

`NODE-PAGE-001`要求一个独立业务节点对应唯一主页面、唯一Page Contract和唯一主Route。页面族可包含列表、详情、编辑，但共享业务对象且职责清晰。流程中心、Registry和Router必须引用同一映射。

## 8. 人工决策边界

系统提供资格、价格、质量、交期、历史和风险证据；除强制合规Guard外，不得自动判断合理性、自动选择供应商、自动审批或自动生成交易对象。人工动作必须记录选择、理由、确认人、确认时间和决策版本。

## 9. 批量业务语义

Batch只负责集合管理；子项保持独立业务粒度。批量确认前必须验证`Total=Completed+Pending`，且`Total>0`、`Pending=0`。存在待完成项时按钮和服务端入口均阻断，保持原状态并提示未完成项。

## 10. PROCESS-ITEM-SOURCE-001 交易明细来源承接

由上游业务对象生成交易明细时，每条明细必须独立保存来源对象编号、物料、申请数量、已处理数量、剩余数量、建议值、人工确认值及分配依据。建议值只作为人工决策证据，不得直接成为交易事实；只有明确 Action 保存的确认数量、确认价格、确认对象和确认日期可以进入下游交易对象。

一个聚合只允许一个交易对手时，上游多交易对手结果必须先形成可见的拆分计划，并由人工逐组确认。任务明确授权批量创建时，显式创建Action可以读取已保存且已确认的拆分计划，按交易对手形成多个单一交易对手聚合；禁止页面加载或草稿保存自动创建、静默绑定第一个对象、自动分量，或把多交易对手写入单一聚合头。来源缺失、数量无依据或拆分未完成时，Guard 必须阻断全部写入。

## 11. PROCESS-QUANTITY-001 ERP数量核算与人工确认

数量驱动的交易明细必须分别展示需求数量、可用量、已处理未完成量、净需求、系统建议和人工确认量，并显示业务公式、来源和完整性状态。缺失事实必须显示`UNKNOWN/未接入`，禁止默认为零后宣称完整核算。

系统建议只提供决策证据。人工确认量低于或等于建议量时允许保存且不强制填写原因；高于建议量时必须由显式Action保存原建议、修改后数量、原因、操作者和时间，无原因增加必须由Guard阻断。系统不得自动改回建议量；模块另有法定或业务上限时仍须独立Guard阻断。

草稿明细必须区分`included/excluded`：确认量大于0时纳入正式对象，确认量等于0时作为未选择明细保留在草稿中且不得生成正式明细。全部明细均为`excluded`时允许保存草稿，但禁止进入正式对象创建。确认量超过建议量10倍属于严重异常，必须阻断并要求重新确认。

## 12. PROCESS-DRAFT-001 正式交易对象前人工草稿

正式交易对象创建前需要人工复核供应商、数量、价格、交期或意见时，必须使用唯一受治理草稿承接，不得把页面临时状态直接写为正式对象。草稿至少经历`editing -> confirmed -> ready_for_creation`，只能由显式保存与确认Action推进，并记录人工版本、Actor、At及调整历史。

创建Action必须同时复核草稿已持久保存、人工确认完整、当前版本一致、业务Guard通过和上游准入仍有效。Provider重载、刷新和页面重入必须恢复同一草稿版本；系统建议、默认初始化或新一轮计算不得覆盖已保存人工值。

## 13. PROCESS-SUPPLIER-DRAFT-SPLIT-001 多供应商采购草稿拆分

一个`PurchaseOrderDraft`可以包含多个`SupplierPurchaseDraft`，但每个供应商草稿只承载一个供应商及其物料、交货日期、供应商备注和审批意见。每条纳入明细必须明确且只能归属一个供应商；同一物料同时归属多个供应商时必须阻断，不得由Runtime重新分配。

显式创建Action必须在全部供应商草稿完成并保存后一次读取完整拆分计划，按供应商生成多个单供应商`PurchaseOrder`。幂等范围为`Gate + Supplier`；任何分组校验失败必须在写入前整体阻断。供应商级交期、备注和审批意见执行人工数据不可变保护，禁止继续使用草稿头共享值覆盖分组人工值。

## 14. PROCESS-DRAFT-VISIBLE-PROJECTION-001 草稿实际采购内容投影

采购订单人工草稿必须区分“完整草稿证据”和“当前实际采购内容”。`excluded`或确认采购数量等于0的物料继续保留在`PurchaseOrderDraft`中用于审计、恢复和后续人工调整，但采购订单创建页的物料明细列表只投影`included && confirmedQuantity > 0`的行。过滤是只读页面投影，不得删除、改写或覆盖排除行证据。

供应商采购草稿信息必须以一个供应商一行展示，供应商名称不得拼接多个供应商。采购订单列表的新增入口只能导航到受`PurchaseOrderCreationGuard`保护的创建页；列表、创建申请或导航动作不得直接调用正式采购订单创建Action。

## 15. PROCESS-SUPPLIER-ITEM-CONSISTENCY-001 供应商与物料需求一致性

`SupplierPurchaseDraft`只能由明确且有效的`PurchaseOrderItem`供应商归属生成。每个分组具有唯一`supplierId/supplierName`，禁止读取草稿头部的供应商汇总字符串作为物料兜底，禁止把“供应商A、供应商B”作为单一供应商名称。每条有效物料只能归属一个供应商，物料供应商与所属供应商草稿必须一致。

实际采购行必须同时满足`requestedQuantity > 0 && confirmedQuantity > 0`。需求为0但确认数量大于0属于业务错误，保存草稿和创建Action均须以“采购需求不存在”阻断；需求大于0但确认数量为0允许保存为待确认/排除证据。确认数量大于0时必须存在明确供应商。供应商数量只能取`SupplierPurchaseDraft.length`，不得拆分或解析名称字符串统计。

## 16. PROCESS-DRAFT-RUNTIME-SOURCE-001 采购订单草稿运行数据源隔离

采购订单创建页面的供应商数量、供应商列表和物料供应商归属必须依次读取`SupplierPurchaseDraftProvider -> PurchaseOrderDraft -> SupplierPurchaseDraft[]/PurchaseOrderItem`。`SupplierRecommendationDecision`及`SupplierRecommendationGate.supplierName`只作为推荐证据和来源链摘要，禁止直接作为采购草稿数据源，禁止用聚合名称回填物料供应商。

供应商数量只允许等于`SupplierPurchaseDraft.length`；物料供应商只允许读取行级`supplierId/supplierName`。显式`requestedQuantity=0`不得被Provider视为缺失并重新补水；当确认数量大于0时必须在进入采购订单草稿前FAIL。Provider重载、页面刷新和Runtime恢复不得覆盖人工供应商分配、数量、价格、交期或备注。

## 17. PROCESS-PO-MATERIAL-ELIGIBILITY-001 采购物料准入

供应商推荐物料不等于采购订单物料。`SupplierRecommendationDecision`只提供只读推荐证据；必须由`PurchaseOrderMaterialEligibilityGuard`逐行判断。仅`requestedQuantity > 0 && confirmedQuantity > 0 && supplierId存在`的行可以进入`PurchaseOrderDraft.purchaseMaterialItems`并生成`SupplierPurchaseDraft`。

需求为0但确认量大于0、或正确认量但无供应商的行必须FAIL；确认量为0的推荐项为`NOT_SELECTED`。所有非PASS项只保存在`recommendationEvidenceItems`供追溯，禁止混入采购订单创建区域。过滤不得删除源证据或覆盖人工供应商、数量、价格、交期和备注；创建Action必须复用同一Guard并只接收PASS投影。

## 18. PROCESS-MULTI-SOURCE-CONTEXT-001 多来源交易创建上下文

一个Gate或Handoff关联多个来源业务对象时，下游创建上下文必须使用来源编号数组完整承接，禁止只读取第一项或把数组静默降为单值。下游Provider必须逐个读取来源对象、展开来源明细并形成唯一创建上下文；同物料合并时必须保留`sourceObjectIds[]`和逐来源数量证据，关系标记为`MERGED_FROM`。

系统来源合并只更新需求证据，不得覆盖人工供应商、确认数量、价格、交期和备注。正式创建投影必须继续保留完整来源数组，同时兼容单值主来源字段；上下文建立、刷新和验收不得自动创建交易对象，业务写入计数为0。
