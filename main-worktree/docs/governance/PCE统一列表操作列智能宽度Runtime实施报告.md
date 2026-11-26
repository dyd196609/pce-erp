# PCE统一列表操作列智能宽度Runtime实施报告

- 版本：`V1.14.2.8.4.27.2.39`
- 实施边界：仅统一列表 Runtime、Schema Action Contract 接入、布局治理与验收资产
- 数据库结构：未修改
- Business Write Count：`0`

## ListRuntimeCapabilityInventory

| 能力名称 | 文件位置 | 当前作用 | 是否复用 | 是否扩展 |
|---|---|---|---|---|
| 企业列表契约 | `frontend/src/meta/runtime/pceEnterpriseListContract.js` | 列表、分页、筛选与固定列契约 | 是 | 否 |
| 企业列表组件 | `frontend/src/meta/components/PceEnterpriseListTable.vue` | 单一表格与横向滚动所有者 | 是 | 接入宽度诊断属性 |
| 列表 Action Runtime | `frontend/src/meta/runtime/listActionColumnRuntime.js` | 按状态解析行级 Action Contract | 是 | 增加 Schema 动作目录解析 |
| 操作列宽度引擎 | `frontend/src/meta/runtime/tableActionColumnEngine.js` | 根据动作标签与数量计算宽度 | 是 | 升级为 `ActionColumnWidthRuntime` |
| 主数据 Metadata Registry | `frontend/src/meta/master-data/masterDataRegistry.js` | 列、筛选、动作策略唯一配置源 | 是 | 增加只读主数据动作策略 |
| Metadata 列表适配器 | `frontend/src/meta/components/FoundationMetadataList.vue` | 将 Registry 投影到企业列表 | 是 | 移除 300px 和 template 动作硬编码 |

## 复用结论

未创建新的 Metadata、Registry、Schema、表格组件或平行列表框架。现有 `tableActionColumnEngine` 是宽度算法正式所有者；本版本仅将其升级为具名、可诊断、可验收的公共 Runtime。

## 目标页面接入

| 页面 | Metadata动作策略 | 预期动作数 | 预期宽度 |
|---|---|---:|---:|
| 供应商资料 | `readonlyMaster` | 1 | 96px |
| 物料资料 | `master` | 2 | 152px |
| 供应商物料价格 | `config` | 3 | 208px及以上，按标签扩展 |
| 物料供应商关系 | `fact` | 1 | 96px |
| 供应商价格分析 | `fact` | 1 | 96px |
| 供应商核价智能辅助 | `fact` | 1 | 96px |

## 实施边界确认

- SupplierMaster、MaterialMaster、MaterialSupplierRelation、SupplierPriceFact 数据：未修改。
- PurchaseOrder、Gate、采购流程：未修改。
- 数据库结构：未修改。
- 业务交易写入：`0`。

真实浏览器逐页记录与截图索引见 `PCE统一列表操作列智能宽度真实运行验收报告.md`。
