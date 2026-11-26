# SupplierMaterialPrice Source Scan Report

- 版本：`V1.14.2.8.4.27.2.42`
- 扫描页面：`#/foundation/erp/supplier-material-prices`
- 扫描结论：早期浏览器维护源已从正式页面退出；页面现由既有`SupplierMaterialPriceRuntime`统一提供事实。

## 扫描清单

| 项目 | 扫描前 | V42治理结果 |
|---|---|---|
| 数据来源 | `manufacturing-foundation-state-v1`浏览器Store | `SupplierMaterialPriceRuntime`服务端事实 |
| Schema | `masterDataRegistry`早期字段 | `SupplierMaterialPriceSchema`完整字段契约 |
| Provider | 无正式Provider | `SupplierMaterialPriceRuntimeProvider`，仅适配既有服务端Runtime |
| Runtime | 既有Runtime把报价明细弱投影为价格 | 原位扩展既有`SupplierMaterialPriceRuntime`，只投影完整受治理价格 |
| 正式主数据 | 否 | 企业有效价格维护对象；当前正式记录0条 |
| 旧源引用 | 正式列表直接读取 | 仅在样例数据管理保留，正式价格页不再读取 |

## ListRuntimeCapabilityInventory

| 能力名称 | 文件位置 | 当前作用 | 是否复用 | 是否扩展 |
|---|---|---|---|---|
| Metadata Registry | `frontend/src/meta/master-data/masterDataRegistry.js` | 字段、列、筛选和Action契约 | 是 | 原位补齐字段 |
| List Runtime | `frontend/src/meta/components/FoundationMetadataList.vue` | 统一列表、筛选、统计和操作列 | 是 | 否 |
| SupplierMaterialPrice Runtime | `backend/masterdata/master_data_statistics_runtime.py` | 企业有效价格只读投影与迁移评估 | 是 | 是，原位扩展 |
| Provider | `frontend/src/meta/providers/supplierMaterialPriceRuntimeProvider.js` | 调用同一服务端Runtime | 是 | 新增客户端适配器，不构成第二套Runtime |
| Action Runtime | `frontend/src/meta/runtime/listActionColumnRuntime.js` | 查看/编辑动作契约 | 是 | 否 |

## 运行边界

- 正式页面不再从`manufacturing-foundation-state-v1`读取价格行。
- `SupplierPriceFact`历史事实未修改。
- `PurchaseOrder`、Gate、采购流程均未修改。
- 数据库结构未修改；业务写入为0。
