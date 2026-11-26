# PCE统一高级筛选区域布局验收报告

## 版本与边界

- 版本：`V1.14.2.8.4.27.2.31`
- 布局契约：`PCE-ADVANCED-FILTER-LAYOUT-V1.0`
- 修改范围：统一高级筛选组件、布局Runtime、布局CSS及基础资料页面的统一布局接入。
- 未修改：MaterialMaster、SupplierMaster、MaterialSupplierRelation、SupplierMaterialPrice、PurchaseOrder、Provider、业务Runtime数据来源、采购流程和Gate。
- Business Write Count：0。

## 治理加载

- `PCE-ERP开发治理总规范.md`：PASS。
- `页面开发模板.md`：PASS；兼容入口指向当前页面与交互开发规范。
- `统一列表规范.md`：PASS；兼容入口指向当前企业列表契约。
- `页面字段来源唯一规范.md`：PASS。
- `高级筛选布局规范.md`：已新增并在实现前生效。

## 自动验收

| 门禁 | 结果 | 证据 |
| --- | --- | --- |
| FILTER-LAYOUT-HEIGHT-001 | PASS | 标准高度36px，四页真实计算高度唯一值均为36 |
| FILTER-LAYOUT-WIDTH-001 | PASS | 1440px下同一行前四列宽度一致，控件宽度100%且无容器溢出 |
| FILTER-LAYOUT-RESPONSIVE-001 | PASS | 1440/1024/768/375px分别为4/3/2/1列 |
| FILTER-LAYOUT-ROWS-001 | PASS | 查询条件、范围条件、操作按钮顺序一致 |
| FILTER-RUNTIME-SOURCE-ISOLATION-001 | PASS | 未修改筛选字段来源、Provider或业务Runtime |

专项命令：`npm run verify:pce-filter-layout:v11428427231`，全部通过。Vite生产编译通过，2516个模块完成转换。

## 真实浏览器验收

| 页面 | 布局 | 控件高度 | 数据回归 | 横向溢出 |
| --- | --- | ---: | --- | --- |
| `#/foundation/erp/material-suppliers` | 4列、三行顺序正确 | 36px | 87条 | 无 |
| `#/master-data/suppliers` | 4列、三行顺序正确 | 36px | 100条 | 无 |
| `#/master-data/materials` | 4列、三行顺序正确 | 36px | 80条 | 无 |
| `#/foundation/erp/supplier-material-prices` | 4列、三行顺序正确 | 36px | 1条 | 无 |

关系页补充验证：输入`MT080`后结果正确收敛，点击“清空条件”恢复87条；1024/768/375px下根容器与页面均无横向溢出。

## 数据保护与治理检查

- Material Regression：PASS。
- Supplier Regression：PASS。
- Relation Regression：PASS。
- Frozen Asset Check：PASS；表格、分页、操作、字段Schema和数据加载未改变。
- Identity Check：N/A；本版本不修改业务对象身份。
- Data Extract Check：PASS；Provider/Runtime未改动。
- Array Completeness：PASS；80/100/87/1数据数量保持一致。
- Regression Check：PASS。
- 数据库启动前后SHA256均为 `634DE03199C0BD5E3140437A7CAC3E2DA1BE327B857C62553E4D4005EE19C847`。

## 构建结论

- 专项验收：PASS。
- Vite生产编译：PASS。
- 标准 `npm run build`：BLOCKED。
- 阻断原因：全局 `PCE-WEB-ACCEPTANCE-V1.1` 仍有13个既有blocker，涉及采购询价、采购订单创建和绩效页面的快速搜索/筛选字段完整性；这些是内容能力问题，不是本版本授权的布局问题。

## 最终报告

Version: `V1.14.2.8.4.27.2.31`

Governance Files Loaded: PASS

Filter Runtime: PASS

Layout: PASS

Material Regression: PASS

Supplier Regression: PASS

Relation Regression: PASS

Database Changed: NO

Business Write Count: 0

Build: BLOCKED（13个范围外全局Web Acceptance blocker）

Final Status: `PCE_FILTER_LAYOUT_STANDARD_BUILD_BLOCKED`
