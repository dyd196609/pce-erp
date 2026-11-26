# PCE 采购三模式治理规范

版本：V1.14.2.8.4.27.2.46（第一批：评估与设计）

## 1. 模式定义

- `STANDARD`（标准采购）：采购申请 → 询价 → 供应商报价 → 报价比较 → 核价 → 供应商确认 → SupplierMaterialPrice（供应商物料有效价格）→ PurchaseOrder（采购订单）。
- `AGREED_PRICE`（既定价格采购）：SupplierMaster（供应商主数据）、MaterialMaster（物料主数据）及当前有效 SupplierMaterialPrice 均存在时，可跳过询价、报价比较和核价。
- `DIRECT`（直接采购）：可跳过采购申请、询价、报价比较和核价，但不能跳过主数据与价格治理。没有有效价格时必须先人工确认价格并形成 SupplierMaterialPrice，再创建 PurchaseOrder。

三种模式是三种前置流程，不是三套订单或三套价格体系。

## 2. 强制规则

### PURCHASE-MODE-SINGLE-ORDER-001

三种模式最终只能进入 `procurement.PurchaseOrder`。禁止新增 StandardPurchaseOrder、AgreedPricePurchaseOrder、DirectPurchaseOrder、SimplePurchaseOrder 或 SmallBusinessPurchaseOrder。仓库现存 `purchase.PurchaseOrder` 必须按 LEGACY（历史兼容）治理，V46 不得继续扩展或作为三模式目标对象。

### PURCHASE-ORDER-MASTER-DATA-BOUNDARY-001

正式订单的供应商必须引用启用的 SupplierMaster；物料必须引用存在、启用且 `is_purchased=true` 的 MaterialMaster；适用时必须验证 MaterialSupplierRelation（物料供应商关系）。联系人、联系方式、供应商地址、送货地址来自 SupplierMaster；规格、单位来自 MaterialMaster；币种和税率来自 SupplierMaterialPrice 或企业采购配置。页面不得现场创造供应商、物料或正式采购价。

### PURCHASE-PRICE-CLOSED-LOOP-001

每个正式 `PurchaseOrderItem.unitPrice`（采购订单明细单价）必须引用同一供应商、物料及有效期内的 SupplierMaterialPrice，并保存 `supplierMaterialPriceId`（供应商物料有效价格标识）。SupplierQuotation（供应商报价）、PriceApprovalResult（核价结果）、SupplierPriceFact（供应商价格事实）、Gate 价格、页面输入、MaterialMaster 价格、历史价格及默认值均不得直接成为执行价格。

### PURCHASE-DIRECT-PRICE-CONFIRM-001

DIRECT 模式没有当前有效价格时，页面必须明确提示“当前供应商-物料没有有效价格。确认该价格后，系统将先建立供应商物料有效价格，再生成采购订单。”人工确认必须记录确认人、确认时间、原因、税率、币种、生效日期及来源；事务顺序必须是 Price Confirmation（价格确认）→ SupplierMaterialPrice → PurchaseOrder。禁止先保存订单再补价。

### PURCHASE-AGREED-PRICE-VALIDITY-001

AGREED_PRICE 仅在 SupplierMaster 启用、MaterialMaster 启用且允许采购、SupplierMaterialPrice 状态为 ACTIVE、生效日期不晚于当前日期、失效日期为空或不早于当前日期，并满足物料供应商关系治理时可用。订单必须记录 `purchaseMode=AGREED_PRICE`、`priceSource=SupplierMaterialPrice`、`priceSourceId` 及 `bypassReason=已有有效供应商物料价格`。

### PURCHASE-ORDER-SNAPSHOT-001

订单创建时必须同时保存正式引用和不可随主数据变化的历史快照：

- 订单：`supplierId`、`supplierCodeSnapshot`、`supplierNameSnapshot`、`supplierContactSnapshot`、`supplierPhoneSnapshot`、`supplierAddressSnapshot`、`deliveryAddressSnapshot`。
- 明细：`materialId`、`materialCodeSnapshot`、`materialNameSnapshot`、`specificationSnapshot`、`unitSnapshot`、`supplierMaterialPriceId`、`unitPriceSnapshot`、`taxRateSnapshot`、`currencySnapshot`。

### PURCHASE-PROCESS-BYPASS-TRACE-001

流程跳过必须成为服务端持久业务事实，至少记录 `purchaseMode`（采购模式）、`sourceType`（来源类型）、`sourceReference`（来源引用）、`bypassReason`（跳过原因）和节点状态。AGREED_PRICE 必须把 Inquiry（询价）和 PriceApproval（核价）记为 SKIPPED（已跳过）并关联 SupplierMaterialPrice；DIRECT 必须把 PurchaseRequest（采购申请）、Inquiry 和 PriceApproval 记为 SKIPPED，并把 PriceConfirmation 记为 COMPLETED（已完成）。页面 if/else、路由参数或本地缓存不能充当跳过事实。

## 3. SupplierPriceFact 边界

SupplierPriceFact 继续负责历史报价、历史采购价、趋势、分析和异常提示。它可以辅助 DIRECT 人工确认，但不得作为 PurchaseOrderItem 的直接执行价格，也不得替代 SupplierMaterialPrice。

## 4. 后续统一流程

三种模式创建同一 PurchaseOrder 后，共用收货、检验、入库、对账、应付、结算和关闭流程。禁止分模式复制下游链。

## 5. 配置与权限

允许模式必须扩展现有 Metadata Registry（元数据注册）、Schema Registry（模式注册）、Workflow Runtime（工作流运行层）、Permission Runtime（权限运行层）和 Enterprise Config（企业配置）能力。企业可配置 STANDARD only、STANDARD + AGREED_PRICE 或三模式全开；禁止新建第二套企业配置中心或工作流引擎。

## 6. 第一批冻结边界

本批次只做扫描、评估、规则冻结和零写入诊断。不得修改 PurchaseOrder 数据库结构，不得创建订单、价格或测试业务数据。后续批次必须先由用户人工确认本规范。

## 7. Batch2 STANDARD 正式落地

V1.14.2.8.4.27.2.46-Batch2 仅落地 `STANDARD`（标准采购）。唯一正式订单域为
`procurement.PurchaseOrder`；`purchase.PurchaseOrder` 保持 `LEGACY_READ_ONLY`（历史只读兼容），不得接收
三模式新增写入。

新建标准订单必须在同一服务端事务中，以本次 `PriceApprovalResult`（核价结果）精确定位其一对一
`SupplierMaterialPrice`（供应商物料有效价格），完成状态、有效期、供应商、物料和来源身份复核后，
保存正式外键与历史快照。Gate（准入门）只传身份，不传执行价格。任何关键校验失败必须整单回滚。

`AGREED_PRICE`（既定价格采购）与 `DIRECT`（直接采购）仍未实施；本节不授权入口、按钮、接口或写入。
