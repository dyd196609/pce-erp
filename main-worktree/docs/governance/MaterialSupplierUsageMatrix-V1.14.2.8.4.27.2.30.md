# MaterialSupplierUsageMatrix V1.14.2.8.4.27.2.30

## 运行结论

- 事实来源：`MaterialSupplierUsageMatrix` 服务端运行时扫描。
- 扫描组合数：95。
- 可建立正式关系：87。
- 待人工确认：8。
- 编码无法严格匹配：0。
- 重复正式关系：0。
- 业务交易写入：0。

## 来源汇总

| 来源模块 | 事实数 |
| --- | ---: |
| PurchaseRequest | 50 |
| PurchaseInquiry | 4 |
| SupplierQuotation | 1 |
| QuoteComparison | 0 |
| PriceApproval | 0 |
| SupplierRecommendation | 0 |
| PurchaseOrderGate | 0 |
| PurchaseOrder | 475 |

正式关系的来源优先级为供应商推荐、核价、报价/报价比较、采购订单历史。采购申请和询价只参与使用追踪，不能单独触发正式关系。

## 待人工确认矩阵

以下组合只有采购申请中的供应商建议，没有符合治理要求的关系事实，因此不创建 `MaterialSupplierRelation`：

| 物料编码 | 供应商编码 | 状态 | 原因 |
| --- | --- | --- | --- |
| MT010 | SUP001 | 待人工确认 | 仅有 PurchaseRequest 建议 |
| MT011 | SUP001 | 待人工确认 | 仅有 PurchaseRequest 建议 |
| MT012 | SUP001 | 待人工确认 | 仅有 PurchaseRequest 建议 |
| MT022 | SUP001 | 待人工确认 | 仅有 PurchaseRequest 建议 |
| MT026 | SUP001 | 待人工确认 | 仅有 PurchaseRequest 建议 |
| MT030 | SUP001 | 待人工确认 | 仅有 PurchaseRequest 建议 |
| MT031 | SUP001 | 待人工确认 | 仅有 PurchaseRequest 建议 |
| MT068 | SUP001 | 待人工确认 | 仅有 PurchaseRequest 建议 |

## 完整矩阵入口

完整95行矩阵由以下唯一运行入口输出，不在文档中复制形成第二事实源：

- API：`/api/masterdata/relations/material-suppliers/runtime/facts/` 的 `usageMatrix`。
- 命令：`python manage.py verify_material_supplier_relation_v11428427230`。

每行输出 `materialCode`、`materialName`、`supplierCode`、`supplierName`、`sourceModules`、`businessUsageCount`、`quoteCount`、`recommendationCount`、`purchaseOrderReferenceCount`、`mappingStatus` 和 `relationEligible`。
