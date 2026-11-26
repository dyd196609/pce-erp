# V1.14.2.8.5.1 Purchase Inquiry Domain Model

## 定位

本版本建立采购询价领域定义，不实现页面、流程执行、业务 API 或数据库持久化。模型遵循“对象 → 关系 → 状态 → Action → Finance → Acceptance Registry”的建设顺序。

## 领域对象

- `SCM_PURCHASE_INQUIRY`：询价主对象，承接采购申请并聚合明细、供应商报价和比较结果。
- `SCM_PURCHASE_INQUIRY_LINE`：询价物料明细，引用采购申请明细。
- `SCM_SUPPLIER_QUOTE`：供应商报价头。
- `SCM_SUPPLIER_QUOTE_LINE`：逐物料报价、税率与交期事实。
- `SCM_QUOTE_COMPARISON`：报价比较和推荐事实，不是采购订单或付款依据。

全部对象为 `definition_only`，`automaticCreation=false`。

## Trace

```text
PurchaseRequest
  → PurchaseInquiry
  → SupplierQuote
  → QuoteComparison
  → PriceApproval
  → PurchaseOrder
```

主链关系类型统一为 `business_reference`。仅允许 `forward`，禁止反向生成；询价不能自动创建采购申请，比较结果不能自动创建采购订单。

## 状态与 Action

状态仅允许相邻正向迁移：

```text
draft → issued → quoted → evaluating → approved → closed
```

Action 使用逐状态显式白名单，未登记动作默认拒绝。询价阶段始终禁止 `createPurchaseOrder`、付款、银行、总账和核销动作。

## Finance 边界

允许价格事实：`quoteAmount`、`estimatedCost`、`priceReference`。

禁止：`payment`、`createPayment`、`bankTransfer`、`ledgerPost`、`reconcile`。

## Acceptance Registry

`SCM_PURCHASE_INQUIRY_ACCEPTANCE_PROFILE` 注册五个领域对象、SCM V2 模板、Status/Trace/Action/Finance 四类规则、五条主链 Trace 关系和只读 Runner。SCM 模块激活后会自动返回该对象 Profile。

## 数据保护

```text
Business Logic Changed=NO
SCM Logic Changed=NO
Business Write Count=0
Production Data Written=NO
productionUserDataWritten=false
```

验证命令：

```text
node scripts/verifyPurchaseInquiryDomainModelV1142851.mjs
node --test tests/acceptance/enterprisePurchaseInquiryDomainModelV1142851.test.mjs
```
