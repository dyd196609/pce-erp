# MaterialMaster唯一运行入口规范

- 规则编号：`MATERIAL-MASTER-SINGLE-RUNTIME-001`
- 生效版本：`V1.14.2.8.4.27.2.23`
- 适用范围：企业物料页面、采购、库存、BOM、MRP、MES及所有物料引用
- 状态：长期有效、持续更新

## 1. 唯一来源

企业物料唯一事实来源为 `masterdata.Material`（数据库表 `material`）。正式运行链固定为：

```text
MaterialMaster
-> MaterialMasterRuntimeAdapter
-> MaterialRuntimeModel
-> Provider/API
-> Page/Business Selector
```

前端的制造参考、SCM兼容页与WMS等同步选项消费者，必须经过
`MaterialMasterRuntimeProvider` 读取同一服务端 Runtime facts。
`manufacturingFoundationStore.materials` 只能作为隔离的历史样例集合，不得被任何正式物料选择器、存在性校验或页面列表消费。

`MaterialMasterRuntimeAdapter` 是唯一字段转换入口；页面和业务模块不得直接从静态 rows、Demo Store、临时 Context 或模块私有物料集合构造正式物料。

## 2. 运行字段

`MaterialRuntimeModel` 必须提供 `materialCode`、`materialName`、`specification`、`unit`、`category`、`type/materialType`、`status/businessStatus`、`updatedAt` 与 `materialSourceTrace`。

`MaterialSourceTrace` 固定输出：物料编码、来源 `MaterialMaster`、数据库表 `material`、维护入口“企业基础数据 → 物料数据”。

## 3. 模块边界

1. 所有业务模块禁止独立维护物料。
2. 采购申请只保存 MaterialMaster 身份和业务时点快照。
3. 采购订单通过 PurchaseRequestItem 回查 MaterialMaster，不得使用 Gate 临时字段。
4. 验收 Fixture 必须隔离，禁止进入生产页面、Provider、业务选择器或正式对象链。
5. 物料编码不可在 Runtime、页面或迁移中改写。

## 4. 验收门禁

- `MATERIAL-MASTER-SINGLE-RUNTIME-001`：正式物料 Runtime 入口数量必须为1。
- `MATERIAL-DATA-SOURCE-001`：企业物料页和业务选择器必须读取 `masterdata.Material/material`。
- `MATERIAL-FIXTURE-CLEANUP-001`：旧静态物料 Fixture 不得残留于生产代码或测试断言。
- `MATERIAL-BUSINESS-CHAIN-001`：`MaterialMaster → PurchaseRequestItem → PurchaseOrderItem` 来源链完整，规格和单位有效。

以上转换与检查均为只读，`Business Write Count = 0`；本规范不授权修改数据库结构、物料编码、采购流程、Gate或采购订单编号。
