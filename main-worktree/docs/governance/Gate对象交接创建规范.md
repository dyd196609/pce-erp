# Gate对象交接创建规范

## GATE-HANDOFF-001：Gate目标对象正式创建门禁

Gate完成仅代表目标业务对象具备创建资格，不等于目标对象已经创建。Gate页面不得用页面跳转、前端诊断对象、状态修改或临时缓存替代正式业务对象创建。

正式创建链必须保持唯一且可追踪：

`Gate Action -> CreationRequest -> Provider -> Domain -> Canonical Number -> Target Object List`

强制要求：

1. Gate状态与准入结果必须明确允许创建。
2. 页面动作必须先生成带唯一编号的 `CreationRequest`，记录Gate、准入结果、来源链和待确认业务事实。
3. 目标对象只能在用户显式确认后，由服务端Provider调用Domain事务创建。
4. 目标对象编号只能由目标对象自己的Canonical编号服务生成；禁止复用或拼接Gate、申请、询价、报价及核价编号。
5. 创建请求必须幂等；相同请求重复提交不得重复创建目标对象。
6. 创建结果必须可从目标对象正式Provider查询，并在列表事实源中可见。
7. 来源供应商、物料、数量和价格必须通过服务端校验；主数据不一致时必须阻断并要求人工确认，禁止静默替换。
8. Gate模型、目标对象生命周期与数据库结构不得因为页面交接而被绕过或修改。

## 验收门禁

`PURCHASE-ORDER-GATE-HANDOFF-001` 至少检查：

- Gate Action Count = 1
- CreationRequest Count = 1
- PurchaseOrder Create Count = 1
- List Visible Count = 1
- DOM采购订单编号 = `PurchaseOrder.objectNo`
- Business Write Count = 1（目标业务对象；明细属于同一事务聚合）

任何一项失败均不得输出READY。

## GATE-HANDOFF-002：供应商拆单与明细同事务创建

采购订单准入 Gate 向采购订单交接时，必须以 Gate 已确认的供应商—物料关系为唯一拆单事实：

1. 一个正式供应商生成一个 `PurchaseOrder`，不同供应商不得合并到同一订单；
2. 同一供应商的物料行归入该供应商唯一订单；
3. 每个订单头与所属 `PurchaseOrderItem` 必须在同一数据库事务内创建；
4. `PurchaseOrderItem.purchaseOrderId` 必须指向本次创建的订单，禁止只创建 Header；
5. 供应商、采购日期、交期、紧急程度与 Gate 来源关系必须进入正式运行事实，页面不得以空值或前端推算补齐；
6. 供应商数量必须等于创建订单数量；任一供应商主数据、交期或物料关系不完整时，整批阻断且写入数为 0；
7. 重复提交同一 CreationRequest 必须幂等，不得重复创建订单或明细。

验收门禁：

- `PURCHASE-ORDER-SUPPLIER-SPLIT-001`：Supplier Count = PurchaseOrder Count；
- `PURCHASE-ORDER-DETAIL-CREATE-001`：每个 Header 至少存在一条所属 Detail；
- `PURCHASE-ORDER-FIELD-INHERIT-001`：supplier、purchaseDate、deliveryDate、urgency、sourceGate 均完整。

## GATE-HANDOFF-003：采购订单物料来源隔离

Gate 只传递供应商决策、价格决策、物料编码和来源申请身份。采购订单创建服务必须按来源申请编号与物料编码重新读取 `PurchaseRequestItem` 和 MaterialMaster，再生成 `PurchaseOrderItem`。

禁止把 Gate 临时物料名称、规格、单位或数量直接作为采购订单明细权威事实。来源申请明细或物料主数据无法唯一解析时，整批创建必须回滚。
