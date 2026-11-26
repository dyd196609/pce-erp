# PCE Existing Intelligence Capability Inventory

- 版本：`V1.14.2.8.4.27.2.32`
- 扫描范围：`frontend/src/meta/schema|runtime|registry|core|components`
- 扫描结论：已有能力优先复用，禁止建立第二套 Metadata、Registry、Runtime 或 Config 框架

## 1. 目录扫描

| 目录 | 文件数 | 能力命中文件数 | 结论 |
|---|---:|---:|---|
| `meta/schema` | 14 | 2 | 已有业务 Schema；基础资料列表继续复用既有 Registry，不另建 Schema 根目录 |
| `meta/runtime` | 127 | 31 | 已有列表、列、筛选、下拉与契约 Runtime |
| `meta/registry` | 3 | 1 | 已有 Meta/Module/GlobalModule Registry |
| `meta/core` | 83 | 10 | 已有 Schema Contract、Normalizer、Registry、Resolver 与 Page Renderer |
| `meta/components` | 41 | 26 | 已有企业列表、高级筛选、筛选字段和业务状态组件 |

## 2. 能力映射

| 能力 | 正式复用路径 | 状态 |
|---|---|---|
| 列 Metadata | `meta/master-data/masterDataRegistry.js` | 已存在，扩充同一 Registry 定义 |
| 筛选 Metadata | `masterDataRegistry.filterSchema` | 已存在，页面直接消费 |
| 字段 Schema | `meta/core/schemaContract.js`、`schemaNormalizer.js` | 已存在 |
| 页面 Schema/注册 | `meta/core/schemaRegistry.js`、`meta/registry/metaRegistry.js` | 已存在 |
| 列 Runtime | `meta/runtime/pceTableColumnRuntime.js` | 已存在，不新建 |
| 筛选 Runtime | `meta/runtime/listFilterRuntime.js`、`pceEnterpriseListContract.js` | 已存在，直接复用 |
| 下拉 Runtime | `meta/runtime/remoteSelectOptionsProvider.js`、`listFilterRuntime.js` | 已存在，使用当前 Runtime 结果去重或受治理 Provider |
| 企业列表 | `PceEnterpriseListTable.vue`、`PceEnterpriseAdvancedFilter.vue` | 已存在，直接复用 |
| CRUD Engine | `meta/crud/crudEngine.js`、`CRUDRenderer.vue` | 已存在，本版本不重建 |

## 3. 企业自主维护能力审计

| 能力 | 当前状态 | 本版本处理 |
|---|---|---|
| 修改列名称 | 未发现持久化配置闭环 | 不重复开发；建议未来在现有 `masterDataRegistry` 上叠加受权限控制的配置投影 |
| 隐藏列 | 未发现用户级持久化闭环 | 同上 |
| 调整列顺序 | `uiEvolutionEngine` 存在运行时重排，但不是企业用户持久配置 | 不冒充已支持；保留为扩展候选 |
| 配置筛选 | Registry 已支持开发期 Schema 配置，未发现用户持久化管理页 | 接入现有 Schema；管理能力提出扩展方案 |
| 配置下拉来源 | `optionsSource/optionsProvider` 已存在，未发现用户持久化管理页 | 接入现有 Runtime 来源；管理能力提出扩展方案 |

建议扩展仅允许在后续独立授权版本中，为现有 `masterDataRegistry` 增加租户/角色配置投影、权限、版本、审计、回滚与服务端持久化；不得新增平行 Registry 或前端 localStorage 配置事实。

## 4. 边界

- 本版本只调整元数据定义、页面消费与验收资产。
- 不修改 MaterialMaster、SupplierMaster、MaterialSupplierRelation、SupplierMaterialPrice 或采购订单事实。
- Database Changed：`NO`。
- Business Write Count：`0`。
