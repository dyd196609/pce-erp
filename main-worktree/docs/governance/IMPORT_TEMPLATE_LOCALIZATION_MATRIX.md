# Import Template Localization Matrix

Instruction: `WAVE1-FORMAL-IMPORT-XLSX-CONTRACT-CORRECTIVE-20260911-001`

The former localization PASS is `SUPERSEDED BY USER REALITY FAILURE`. It inspected an internal generator while the user-facing server was a stale process returning legacy CSV/key headers. The corrected gate invokes the actual Template Download view and parses its exact response bytes.

| Entity | Worksheet | Actual visible headers from corrected authority | Result |
|---|---|---|---|
| Customer | 客户／经销商 | 编码；名称；启用状态 | automated PASS; manual pending |
| Supplier | 供应商 | 供应商编码；供应商名称；交付地址；分类；信用等级；提前期；启用 | automated PASS |
| Material | 物料档案 | 编码；名称；规格型号；计量单位；单位状态；物料类型；采购属性；产品属性；启用状态 | automated PASS; manual pending |
| Product Definition | 产品定义 | 产品编码；产品名称；EMD物料编码；规格；型号；制造定义模式；状态；启用 | automated PASS |
| Workshop | 车间／生产区域 | 编码；名称；所属部门；启用状态 | automated PASS; manual pending |
| Operation | 工序 | 工序编码；工序名称；车间编码；工作中心编码；工序类型；核算维度；核算单位编码；默认转序方式；启用 | automated PASS |
| WorkCenter | 工作中心 | 工作中心编码；工作中心名称；部门编码；车间编码；标准人工产能；机器工时；单位人工成本；制造费用；启用 | automated PASS |
| Equipment | 设备资料 | 设备编码；设备名称；设备类型；工作中心编码；小时产能；接口标识；启用 | automated PASS |
| Standard Capacity | 标准产能 | 产能编码；产能名称；资源范围；资源编码；计量单位编码；测量状态；标准产能数量；时间基准；时间基准数量；标准工时；启用 | automated PASS |

`／` is used because Excel forbids `/` in worksheet names. Actual-response gate result: 9/9 XLSX parsed, ZIP magic 9/9, header/schema round-trip 9/9, unapproved technical English 0.

`REPORT VS USER REALITY CONFLICT = YES`
