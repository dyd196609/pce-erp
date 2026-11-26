# PCE已有智能化元数据能力复用验收报告

- Version：`V1.14.2.8.4.27.2.32`
- 主题：PCE已有智能化元数据能力扫描与基础资料列表智能化接入治理
- 执行日期：`2026-08-11`

## 治理与能力扫描

- Governance Files Loaded：`PASS`
- Existing Capability Scan：`PASS`
- Metadata Reuse：`PASS`
- Duplicate Framework：`PASS`
- 企业自主维护能力：当前仅有开发期 Metadata 和运行时自动重排；未发现企业用户持久化配置闭环，按任务要求只提出扩展方案。

正式复用链：

```text
masterDataRegistry / MaterialSupplierRelationRuntime fields
  -> PceEnterpriseListContract + listFilterRuntime
  -> PceEnterpriseAdvancedFilter + PceEnterpriseListTable
  -> 基础资料真实 Route
```

## 自动验收

| 检查 | 结果 |
|---|---|
| `EXISTING-METADATA-SCAN-001` | PASS |
| `DUPLICATE-RUNTIME-CHECK-001` | PASS |
| `HARDCODE-FIELD-SCAN-001` | PASS |
| V31筛选布局回归 | PASS |
| V30物料供应商关系回归 | PASS |
| Database SHA256 | `634DE03199C0BD5E3140437A7CAC3E2DA1BE327B857C62553E4D4005EE19C847`（未变化） |
| Business Write Count | 0 |

## 真实浏览器验收

| 入口 | Metadata来源 | 声明列数 | 筛选数 | 企业列表契约 | 结果 |
|---|---|---:|---:|---|---|
| `/master-data/materials` | masterDataRegistry | 7 | 5 | V1.1 | PASS |
| `/master-data/suppliers` | masterDataRegistry | 11 | 5 | V1.1 | PASS |
| `/foundation/pfm/employees` | masterDataRegistry | 13 | 13 | V1.1 | PASS |
| `/foundation/erp/supplier-material-prices` | masterDataRegistry | 10 | 10 | V1.1 | PASS |
| `/foundation/erp/material-suppliers` | MaterialSupplierRelationRuntime | 9 | 9 | V1.1 | PASS |
| `/foundation/manufacturing/processes` | masterDataRegistry | 8 | 8 | V1.1 | PASS |
| `/foundation/manufacturing/routings` → `/master-data/routings` | masterDataRegistry | 6 | 5 | V1.1 | PASS |
| `/foundation/manufacturing/equipment` | masterDataRegistry | 7 | 7 | V1.1 | PASS |

供应商页展开高级筛选后，三行布局为`query/range/actions`；分类、状态和等级的`optionsSource`均为`currentResultDistinctValues`。

## Build

- 直接 Vite 生产构建：`PASS`。
- 标准 `npm run build`：`FAIL`，在构建前置的全项目 `verify:web-acceptance-contract` 被13项既有范围外阻断项拦截；首项为采购询价 `quick_search_fields` 缺失。本版本目标代码已成功编译，且阻断项不属于本版本八个基础资料入口。
- 按总纲“存在任何适用 FAIL 不得签发 READY”，本报告不把直接 Vite 构建替代标准 Build。

## 最终结果

```text
Version: V1.14.2.8.4.27.2.32
Existing Capability Scan: PASS
Metadata Reuse: PASS
Duplicate Framework: PASS
List Runtime: PASS
Filter Runtime: PASS
Dropdown Runtime: PASS
Hardcode Scan: PASS
Database Changed: NO
Business Write Count: 0
Build: FAIL (pre-existing full-project web acceptance blockers)
Final Status: PCE_EXISTING_INTELLIGENCE_REUSE_BUILD_BLOCKED
```
