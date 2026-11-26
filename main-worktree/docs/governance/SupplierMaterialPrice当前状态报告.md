# SupplierMaterialPrice Current State Report

- 版本：`V1.14.2.8.4.27.2.43`
- 页面：`#/foundation/erp/supplier-material-prices`
- 扫描时间：2026-08-11

## 当前状态

| 检查项 | 结果 |
|---|---|
| 当前数据来源 | `SupplierMaterialPriceRuntime`服务端只读事实 |
| 当前Runtime | `backend/masterdata/master_data_statistics_runtime.py::SupplierMaterialPriceRuntime` |
| 当前Schema | `SupplierMaterialPriceSchema` / `masterDataRegistry` |
| 当前Provider | `SupplierMaterialPriceRuntimeProvider` |
| 正式价格数量 | 0 |
| 隔离测试数据数量 | 3 |
| 审批候选数量 | 12 |
| 不完整候选数量 | 12 |
| 维护模式 | `APPROVAL_WORKFLOW_MANAGED` |

## 能力复用与实施边界

- 智能化影响评估：把完整且人工审批的价格归档为企业认可有效价格，并供价格事实和核价辅助只读引用。
- 已有能力扫描：复用现有Runtime、Metadata Registry、Schema、Provider、企业列表与Action Runtime。
- 复用方案：只扩展既有`SupplierMaterialPriceRuntime.list_runtime_models()`，不新建价格模型或Runtime体系。
- 实施边界：不修改数据库、采购订单、Gate或推荐流程；不补造缺失字段；业务写入0。

当前0条正式价格是完整性门禁的真实输出。Runtime已具备对未来完整审批记录的只读归档能力，但本版本没有可安全转换的数据。
