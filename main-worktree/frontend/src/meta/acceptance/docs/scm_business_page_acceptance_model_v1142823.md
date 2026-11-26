# V1.14.2.8.4.23 SCM Business Page Acceptance Model

## 定位

本版本是 PCE-ERP 质量治理基础设施，仅建立 SCM 业务对象的只读验收模型，不开发或修改采购申请、询价、采购订单业务能力。

## 模型范围

- 对象：`PurchaseRequest`、`PurchaseInquiry`、`PurchaseOrder`。
- Trace：`PurchaseRequest → PurchaseInquiry → PriceApproval → PurchaseOrder → WarehouseReceipt → QualityInspection → APPrepare`。
- 状态：仅接受模型声明的相邻正向迁移；逆转、停滞和跨级迁移均失败。
- Action：逐对象、逐状态显式白名单，未登记动作默认拒绝。
- Finance：允许读取 `priceReference`、`costEstimate`、`purchaseAmount`；禁止付款、银行发送、总账过账及对账动作。
- Canary：只读 `canary_acceptance` 模式，生产 API 调用数、业务写入数均必须为 0。

缺失验收事实或未建模对象/状态返回 `UNKNOWN`，不得由页面缓存或前端推算补齐。

## 业务隔离

验收代码只能读取和判断，不创建业务对象、不修改状态、不调用写入 API、不触发审批、不生成下游对象。固定保护结果：

```text
businessLogicChanged=false
scmLogicChanged=false
businessWriteCount=0
productionUserDataWritten=false
```

## 自动验证与归档

在 `frontend` 目录执行：

```text
node scripts/verifyScmAcceptanceModelV1142823.mjs
node --test tests/acceptance/enterpriseScmAcceptanceModelV1142823.test.mjs
```

验证脚本必须得到 `PASS=10`、`FAIL=0`、`UNKNOWN=0`，并将七个模型/报告文件写入：

`test-results/page-acceptance/V1.14.2.8.4.23/SCM/acceptance-model/`

最终状态仅在全部门禁通过时为 `SCM_ACCEPTANCE_MODEL_READY`。
