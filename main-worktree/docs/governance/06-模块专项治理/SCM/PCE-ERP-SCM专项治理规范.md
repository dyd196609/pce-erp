# PCE-ERP SCM专项治理规范

# 文档信息

- 版本：V1.14.2.8.4.27.2.4.3
- 用途：在五大核心治理规范之下固化SCM采购生命周期、人工决策和数据连续性专项约束
- 适用范围：SCM采购申请、询价、报价、报价比较、核价、供应商推荐、订单准入和采购订单
- 优先级：高
- 关联规范：PCE-ERP开发治理总纲、PCE-ERP架构与运行边界规范、PCE-ERP业务流程运行治理规范、PCE-ERP页面与交互开发规范、PCE-ERP自动验收与证据治理规范
- 维护方式：持续更新

## 1. 规范层级

本规范是SCM模块专项约束，不重新定义五大核心规范。发生冲突时，依次执行开发治理总纲、核心规范和本专项规范；案例库只提供问题证据，不覆盖规则。

## 2. SCM标准采购链

```text
PurchaseRequest
  ↓
PurchaseInquiry
  ↓
SupplierQuotation
  ↓
QuoteComparisonFact
  ↓
PriceApprovalPreparation
  ↓
SupplierRecommendationDecision
  ↓
PurchaseOrderGate
  ↓
PurchaseOrder
```

每个节点必须保持来源编号、业务对象、状态、Action、Guard、输出和Handoff可追溯。任何页面不得通过前端重算或Demo事实补齐服务端事实。

## 3. 人工决策边界

系统只提供报价、历史价格、资格、来源和比较证据。禁止自动选择最低报价、自动核价、自动推荐供应商、自动审批或自动生成采购订单。人工选择、意见、理由、确认人、确认时间和版本必须形成可审计事实。

## 4. 运行模式与事实隔离

- `production`只读取正式Provider和受控服务端事实。
- `canary_acceptance`只读取带批次和场景身份的金丝雀事实。
- Legacy事实必须标识来源和可信等级，未经人工确认不得伪装为正式事实。
- Production、Canary、Demo、Acceptance和浏览器Runtime互不覆盖。
- 页面、复制诊断、`strictFacts`和验收报告必须复用同一服务端事实。

## 5. 报价比较与核价

QuoteComparisonFact必须保留全部SupplierQuoteEvidence，不得只保存最低价供应商。PriceApprovalPreparation编号必须来自稳定QuoteComparison编号，禁止使用数组位置或`index + 1`。核价状态与业务结论分离；只有完成且结论通过、报价已接收时，才可进入供应商推荐。

## 6. 供应商推荐批次

一个DecisionBatch可包含多个DecisionItem，一个物料对应一个DecisionItem，同物料多个供应商作为SupplierCandidate集合。批量确认前必须执行Batch Completeness：总项数、已完成项数、待完成项数和动作可用性均有证据；存在待完成项时禁止确认。

## 7. 采购订单准入Gate

Gate只读取当前SupplierRecommendationDecisionBatchResult，不得用历史PurchaseOrder影响当前判断。Gate支持物料级阻断原因、返回修改、重新检查和检查记录；检查记录包括检查人、时间、结果、项目和阻断原因。Gate通过只表示`ready_for_purchase_order`，不等于已创建PurchaseOrder。

## 8. 数据连续性与Legacy保护

已经产生下游业务影响的PR、PI、SQ、QC、PAP、DecisionBatch和Gate事实不得因页面或Provider重构而不可见。缺失历史来源不得补造；使用Alias和MissingBusinessEvidence记录双轨身份、缺口和人工确认。历史编号不得被Canonical编号覆盖。

## 9. 页面与列表

SCM页面继承页面与交互规范，使用唯一Page Identity、服务端`statusLabel`、企业列表契约、页面操作指引和一页一验收。状态变化不得导致任务从生命周期列表消失。公共列表基座、页面壳和流程中心不得因单一SCM增强而修改。

## 10. SCM验收证据

每个SCM节点除核心验收项外，还必须证明：上游编号一致、下游对象边界正确、多供应商证据完整、人工动作可执行、Production/Canary隔离、刷新保持、无越权自动动作。PurchaseOrder创建必须由其独立版本和准入动作证明。

## 11. 采购订单创建入口唯一性

`SCM-PO-ENTRY-001`：所有采购订单创建入口必须先读取当前 `PurchaseOrderGate`、人工确认事实和 `PurchaseOrderAdmissionGuard` 结果，并由 `PurchaseOrderCreationGuard` 在路由入口与创建 Action 两处重复检查。只有 Gate 状态为 `READY_FOR_PURCHASE_ORDER`、人工确认完整、准入检查全部 PASS 且创建入口与当前准入结果一致时，才允许进入人工创建草稿。

旧 `/scm/purchase-order/create` 入口必须由上述 Guard 接管；无 Gate、Gate 未就绪、人工确认缺失、准入失败或上下文不一致时必须显示阻断原因。`PriceApproval -> PurchaseOrder` 直接创建、页面按钮直接调用创建函数以及 Store 内部无准入上下文写入均属于禁止绕过。Gate 通过仅开放人工入口，不得自动创建、提交或审批 PurchaseOrder。

采购订单创建草稿中的人工供应商、数量、价格、交期和备注执行 `DATA-PROTECTION-001`：人工值优先于系统计算值与默认值，只能由显式 Action 修改；刷新、Provider 重载、流程跳转和页面重入不得覆盖人工版本。

## 12. 采购订单来源隔离与生命周期冻结

`SCM-PO-LIFECYCLE-001`：PurchaseOrder 必须按可审计来源分类为 `LEGACY`、`GATE_CREATED`、`MANUAL` 或 `UNKNOWN`。`GATE_CREATED` 必须同时存在 SupplierRecommendationGate、PurchaseOrderAdmissionGuard、PurchaseOrderCreationEntry 以及与订单一致的来源证据；仅有 `sourceType=priceApproval`、页面创建标记或历史编号不得视为 Gate 治理订单。已经存在但无法追溯 Gate 的订单归为 `LEGACY`；明确由人工 Action 创建且来源证据完整但不属于 Gate 链的订单归为 `MANUAL`；证据不足时归为 `UNKNOWN`。分类只形成只读治理标签，不得回写 PurchaseOrder、补写 Gate、迁移、删除或改变历史状态。

正式采购订单生命周期以代码中已冻结的 `PurchaseOrderLifecycleStateDefinition` 为准：`draft -> pending_approval -> approved -> issued -> partially_received -> completed`，并保留 `cancelled` 终止状态。该定义当前仍为 definition-only，自动迁移、自动状态推进和交易执行均关闭。旧 Store、旧 Schema 与 Domain 中存在的其他状态集合只作为 Legacy 兼容证据，不得静默合并、改名或反向覆盖历史记录；任何启用状态迁移的版本必须另行授权并提供映射、Guard、审计与回滚证据。

历史 PurchaseOrder 不得参与当前 PurchaseOrderGate 或 PurchaseOrderAdmissionGuard 的准入判断。供应商、数量、价格、交期、备注和审批意见继续执行 `DATA-PROTECTION-001` 与 `DATA-PROTECTION-RUNTIME-001`；分类、刷新、Provider 重载、流程跳转和生命周期映射均不得覆盖人工值或人工版本。

## 13. 正式采购订单显式创建

`SCM-PO-CREATE-001`：正式 `PurchaseOrder` 只能由人工在受保护的 `PurchaseOrderCreationEntry` 执行一次显式 `CREATE_PURCHASE_ORDER` 动作创建。Action 必须依次复核 `SupplierRecommendationGate`、`PurchaseOrderAdmissionGuard`、人工确认事实、当前准入结果和创建入口一致性；任一检查失败均不得写入。

创建必须复用唯一 `PurchaseOrder` 领域对象，初始状态只能为 `draft`，并完整保存 `sourceGateId`、`sourceRecommendationId`、`sourceInquiryId`、`sourcePriceApprovalId`、供应商、确认人、确认时间、确认来源及报价、核价、资质证据。Action 不得重新计算供应商或价格，不得覆盖人工数量、价格、交期、备注和审批意见；刷新、Provider 重载和页面重入必须恢复同一人工版本。

同一 Gate 可以依据已保存且已人工确认的供应商采购草稿对应多张 `GATE_CREATED` 采购订单，但同一`Gate + Supplier`只能对应一张订单。首次成功创建按实际供应商订单聚合数记录 `Business Write Count`；重复请求必须按`Gate + Supplier`幂等返回原订单并记新增写入为0。创建动作只产生 `draft`，不得自动提交、审批、下达、发布、发送供应商或推进后续状态。`LEGACY`、`MANUAL` 与 `UNKNOWN` 订单不得被创建动作回写或重分类。

## 14. 采购订单明细来源与供应商分配

`SCM-PO-ITEM-SOURCE-001`：复用唯一 `PurchaseOrderItem`，不得另建第二明细模型。每条 Gate 治理明细必须保存 `sourcePurchaseRequestId`、`sourceInquiryId`、`sourceQuoteComparisonId`、`sourcePriceApprovalId`、`sourceGateId`，以及物料、申请数量、确认数量、行供应商、供应商分配来源、报价、核准价、确认价、需求日期、供应商交期和确认交期。

正式 `PurchaseOrder` 聚合维持单一供应商。一个 Gate 中不同物料指向多个供应商时，必须先在唯一`PurchaseOrderDraft`内形成按供应商拆分的`SupplierPurchaseDraft`并完成供应商级人工确认；显式创建Action可以一次读取该确认结果，并为每个供应商生成一张单供应商订单。禁止把第一个推荐供应商绑定全部物料，禁止页面加载或保存草稿自动创建订单。一个物料不得同时属于多个供应商；需要分量时本版本以`PURCHASE_ORDER_ITEM_MULTI_SUPPLIER_ALLOCATION`阻断。

数量证据按 `requestedQuantity -> availableQuantity（如有） -> orderedQuantity（如有） -> remainingQuantity -> confirmedQuantity` 展示。系统只能给出建议数量，`confirmedQuantity`、行供应商、`confirmedPrice`、`confirmedDeliveryDate` 和备注必须由显式保存 Action 固化，并执行 `DATA-PROTECTION-001`；来源不完整或人工确认未完成时禁止生成采购订单明细。

## 15. 采购订单数量核算模型

`SCM-PO-QUANTITY-001`：采购订单创建页统一使用ERP业务语言展示`需求数量 -> 可用库存 -> 已采购未入库数量 -> 净需求数量 -> 建议采购数量 -> 确认采购数量`。建议公式为`max(需求数量 - 可用库存 - 已采购未入库数量, 0)`；仅已下达且尚未完成入库的Gate治理订单可以作为在途采购证据，草稿订单不得计入。

本规则不授权接入WMS或MRP。可用库存不存在权威事实时必须保持`null`并显示“未接入”，核算状态为`PARTIAL`；禁止用零冒充已读取库存。人工确认数量低于或等于建议量时允许保存且不强制原因；高于建议量时必须保存原因、修改人、修改时间和历史，无原因增加由Guard阻断。不得自动调整或自动创建订单。

## 16. 采购订单人工草稿承接

`SCM-PO-DRAFT-001`：复用唯一采购订单创建草稿Store，并以`PurchaseOrderDraft`作为正式业务身份；历史`PurchaseOrderCreationDraft`仅作为兼容名称，不得另建第二套模型。草稿承接Gate、采购申请、人工供应商、确认数量、确认价格、确认交期、备注及数量调整审计，状态只允许`editing -> confirmed -> ready_for_creation`。

`SAVE_PURCHASE_ORDER_CREATION_DRAFT`只保存人工草稿，不创建PurchaseOrder。`CREATE_PURCHASE_ORDER`执行前必须复核草稿已保存、人工确认完整、数量规则通过、草稿版本一致且Gate仍有效；无草稿、未确认或增加数量无原因时必须零写入阻断。刷新、Provider重载和页面重入不得用建议值覆盖草稿人工值。

## 17. 采购订单草稿物料纳入规则

`SCM-PO-DRAFT-ITEM-001`：每条`PurchaseOrderItem`草稿必须具有`included/excluded`状态。确认采购数量大于0时为`included（纳入采购订单）`；确认采购数量等于0时为`excluded（不纳入采购订单）`，允许保存并继续保留来源与人工证据，但正式PurchaseOrder不得生成该明细。

正式创建前至少存在一个有效`included`物料；全部排除时只允许保持草稿。确认数量高于建议量时必须有调整原因，超过建议量10倍时即使有原因也由数量Guard阻断并要求重新确认。页面对业务用户显示中文状态标签，技术状态码仅用于内部契约与自动验收。

## 18. 采购订单草稿供应商拆分

`SCM-PO-SUPPLIER-DRAFT-001`：唯一`PurchaseOrderDraft`允许包含多个`SupplierPurchaseDraft`。每个供应商草稿必须具有`supplierId/supplierName/deliveryDate/supplierRemark/approvalRemark/items`，且只承载一个供应商；每条`PurchaseOrderItem`必须明确`materialCode/supplierId/confirmedQuantity/confirmedPrice`。草稿头共享交期和备注仅作为Legacy兼容证据，不得覆盖供应商级人工值。

显式`CREATE_PURCHASE_ORDER`必须先整体校验所有供应商分组，再按供应商生成多张单供应商`draft`订单；幂等键为`Gate + Supplier`。任一分组不完整或同一物料跨供应商重复分配时必须在写入前整体阻断。人工供应商、数量、价格、供应商级交期、备注和审批意见在刷新、Provider重载和页面重入后必须保持；不得改变Gate、采购订单生命周期或Legacy订单。

## 19. 采购订单草稿供应商分配页面

采购订单创建页以“供应商采购草稿信息”列表集中维护供应商编码、名称、交货日期、审批意见和备注；该列表不得展示正式订单才具有的物料数量或金额汇总。物料明细使用企业列表契约，明确显示物料、需求数量、确认采购数量、供应商编码、供应商名称和分配来源。

物料供应商选择的唯一选项源是当前`SupplierPurchaseDraft`集合；选择编号后由模型解析名称并记录人工分配来源，禁止自由输入或Runtime自动重新分配。筛选、排序和刷新不得覆盖人工分配。正式创建继续只读取已保存拆分计划，并按供应商形成单一供应商PurchaseOrder。

## 20. 采购订单草稿可见内容与创建入口

供应商采购草稿信息使用企业列表契约，一个`SupplierPurchaseDraft`一行；供应商名称不得拼接，列表不得展示正式订单的物料数量或金额汇总。采购订单创建页的物料明细只显示`included && confirmedQuantity > 0`的实际采购行；零数量或`excluded`行继续保存在唯一草稿中，但不显示且不得生成正式订单明细。

数量列表保留中文数量状态，详细异常统一汇总到采购数量核算说明区域。`/scm/purchase-order`的新增入口只允许导航到`/scm/purchase-order/create`并由`PurchaseOrderCreationGuard`判断；禁止在采购订单列表、创建申请或Route跳转中直接创建、提交、审批或发布PurchaseOrder。

## 21. 采购订单供应商真实拆分与需求一致性

`SupplierPurchaseDraft`必须按物料行明确的供应商编号分组，一个分组只对应一个供应商；Gate或草稿头的多供应商汇总名称只用于摘要展示，禁止作为PurchaseOrderItem的供应商身份。每个有效物料必须具有唯一供应商编号和名称，并与所属供应商草稿一致。供应商数量只等于`SupplierPurchaseDraft.length`。

进入供应商草稿、页面物料明细和正式订单准备的物料必须同时满足需求数量大于0、确认数量大于0。需求为0但确认数量大于0必须在草稿保存和正式创建前阻断；确认数量为0的有需求物料允许保留为待确认证据但不进入订单。Provider和Runtime不得重新合并供应商、用头部默认供应商覆盖物料人工分配或删除人工版本。

## 22. 采购订单草稿真实数据源

SCM采购订单创建页固定使用`SupplierPurchaseDraftProvider -> PurchaseOrderDraft -> SupplierPurchaseDraft[]/PurchaseOrderItem`。推荐决策及Gate聚合供应商字段只保留为证据；不得生成供应商列表、统计供应商数量或覆盖物料供应商。显式零需求与正确认数量组合必须在草稿入口阻断，人工分配和人工调整继续执行`DATA-PROTECTION-001`。

## 23. 采购物料准入与推荐证据隔离

`PurchaseOrderMaterialEligibilityGuard`是推荐物料进入采购草稿的唯一准入规则。只有正需求、正确认采购数量且具有供应商的行进入`purchaseMaterialItems`；无需求、无供应商和未选择项保留为只读`recommendationEvidenceItems`。供应商草稿、供应商数量和创建Action只读取有效采购物料投影，过滤不得修改SupplierRecommendationDecision或人工数据。

## 24. 采购订单创建上下文多采购申请承接

`PurchaseOrderCreationContext`是`PurchaseOrderGate -> PurchaseOrderDraft`的唯一多来源承接对象，必须保存`gateId`、`purchaseRequestIds[]`、`purchaseInquiryIds[]`、`quoteComparisonIds[]`、`priceApprovalIds[]`、`supplierPurchaseDrafts[]`和`materialItems[]`。Gate允许多个采购申请，Provider必须逐个读取并展开全部申请，禁止只使用`purchaseRequestId`第一项。

同一物料允许按物料编码合并需求数量，但必须保留`sourcePurchaseRequestIds[]`及逐来源数量明细。人工供应商、确认数量、价格、交期和备注优先于合并计算并不得被覆盖。创建页必须显示全部采购申请编号和来源数量；正式订单投影保留完整来源数组，本规则不授权自动创建、审批或修改采购订单生命周期。

## 25. DELIVERY-URGENCY-001 交期紧急程度自动计算规则

采购交期紧急程度是系统风险计算事实，不是采购人员录入字段或主观判断。计算必须读取权威的需求日期、计划到货日期、采购提前期、供应商交期和安全周期，记录输入来源、完整性、规则版本、计算时间和结果；任何必需输入未接入或读取失败时输出“未知/待确认”，不得按正常处理。

系统统一输出四级中文业务标签：

| 等级 | 业务条件 | 颜色语义 |
|---|---|---|
| 正常 | 剩余周期充足，满足采购提前期和安全周期 | 正常色 |
| 一般 | 接近标准采购周期，存在一定交期风险 | 提示色 |
| 紧急 | 剩余周期小于标准采购周期，可能影响生产 | 警示色 |
| 特急 | 小于最低采购周期，或已经超过需求日期 | 严重警示色 |

标准采购周期、最低采购周期和安全周期的数值阈值必须由受治理业务规则或主数据版本提供，禁止页面硬编码或开发人员自行解释。同一输入与规则版本必须得到同一等级；列表、详情、筛选、排序和导出说明使用同一结果及`COLOR-RULE-001`映射。

采购人员禁止直接修改紧急程度。认为计算错误时，只允许提交风险反馈，记录目标业务对象、原等级、原因、人员、时间和证据；反馈不改变等级。只有权威输入或规则版本经独立授权变更后，系统才可重新计算，并保留重新计算前后等级及来源审计。

## 26. SCM采购列表业务能力与字段基线

SCM采购列表必须按`LIST-BUSINESS-CAPABILITY-001`逐项评估导入模板、导入、导出、高级筛选、排序、分页、批量操作、权限和操作日志。导入、导出和批量动作是否适用由具体采购对象、状态和权限决定；只读证据列表不得为满足清单而获得写能力，`N/A`必须记录原因。

采购业务列表的业务字段基线包括：采购编号、供应商、物料、数量、金额、交期、交期风险等级、状态和操作。聚合列表无法在一行完整展示多物料时，必须显示物料摘要/数量并提供详情入口，禁止只取第一条物料；技术标识和完整来源关系继续按`LIST-DISPLAY-001`隔离。

高级筛选至少评估供应商、物料、状态、交期和紧急程度；适用字段必须使用受治理主数据选项、日期或风险等级选项，并与服务端事实及权限范围一致。紧急程度筛选、排序、颜色和导出必须复用`DELIVERY-URGENCY-001`结果，不得页面重新计算或允许人工修改。

## 27. PURCHASE-ORDER-VIEW-PERMISSION-001 采购订单角色视图与导出权限

采购订单详情必须从同一服务端采购订单、明细、来源关系、生命周期和审批事实构建只读`PurchaseOrderViewModel`，并按采购人员、仓库、供应商和管理角色形成字段投影。角色切换只改变可见字段，不得重新计算业务事实、修改采购订单、推进生命周期、补造来源或写入物料档案。

- 采购人员视图可以查看供应商、物料、数量、采购执行价格、交期、状态和内部备注；
- 仓库视图只查看收货执行所需的物料、数量、计划到货日期和收货状态，不得查看采购执行价格、内部审批和供应商评价；
- 供应商视图只查看该供应商订单履约所需的信息，不得查看内部审批、内部成本、历史价格、推荐依据和其他供应商信息；
- 管理视图可以查看完整业务证据，但技术字段仍按`TECH-FIELD-SEPARATION-001`进入授权诊断区域。

采购订单详情只展示采购执行价格；`QualifiedMaterialPrice`及其历史归属物料档案价格历史，禁止在采购订单详情形成可编辑区域或自动更新物料档案。采购订单导出模板固定为采购人员版、仓库版、供应商版和管理版，导出字段必须复用当前角色视图权限投影；页面无权查看的字段不得通过导出获得。导出记录必须包含人员、时间、订单、模板、角色、范围、数量和结果。

## 28. PURCHASE-ORDER-DOCUMENT-VIEW-001 采购订单标准单据视图

采购订单详情Provider必须只使用当前`PurchaseOrder`头、其`PurchaseOrderItem[]`、结构化`SourceRelations`、生命周期事实和审批事实构建只读单据视图。采购物料明细唯一来源为与当前订单身份关联的`PurchaseOrderItem[]`；禁止回退Gate推荐物料、供应商推荐物料、报价比较物料或采购申请全部物料。Provider必须输出`PurchaseOrderItem Count`、`Detail Display Count`和一致性结果，任何缺失、额外或跨订单明细均为FAIL。

采购订单自身业务编号使用`purchaseOrderNo/poNo`独立字段，Gate业务编号使用`gateNo`，采购申请来源使用`sourcePurchaseRequestIds[]`；三者禁止互相替代、拼接或解析。详情按采购订单基础信息、来源追踪、采购物料明细、审批信息、制单信息组织；来源追踪以业务流程链和关联数量摘要展示，完整数组证据通过受控Tooltip或诊断查看，不得用长编号数组撑开单据页面。

详情必须遵守`DETAIL-NAVIGATION-001`。历史订单来源缺失时保持原编号、明细和人工字段并显示“历史数据不可追溯”，不得补造来源或重写历史数据；开发测试订单编号只允许通过`TEST-DATA-001`标记的生成或清理脚本重建，不得由展示层伪造。

## 29. PURCHASE-ORDER-PRINT-001 采购订单标准打印模型

采购订单打印必须建立`PurchaseOrderPrintViewModel`并复用`BusinessPrintViewModel`四段式契约。公司信息读取当前受治理企业上下文；单据名称固定为“采购订单”；订单编号只读取`PurchaseOrder.purchaseOrderNo/poNo`，且必须与详情、列表、导出一致，禁止读取Gate编号或拼接采购申请来源。

采购物料明细唯一来源为当前订单的`PurchaseOrderItem[]`，标题固定为“采购物料明细”，打印行数必须等于订单明细数。禁止读取PurchaseOrderGate、SupplierRecommendation、QuoteComparison或其他候选/未采购物料。基本信息默认六列紧凑布局；底部按权限提供审批、审核、复核、制表及各自日期，空白签字栏不构成审批事实。

`PurchaseOrderPrintPermission`固定支持采购人员版、仓库版、供应商版和管理版。采购人员版显示供应商、物料、数量、价格和交期；仓库版显示物料、数量、交货日期和收货状态并隐藏价格；供应商版只显示供应商履约信息并隐藏内部审批、成本、历史价格和推荐依据；管理版显示完整业务字段。打印预览和临时编辑均为零业务写入，不得修改采购订单、Gate、生命周期、数据库或历史订单。
