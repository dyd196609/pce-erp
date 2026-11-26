# PCE Intelligence Capability Inventory

- 版本：`V1.14.2.8.4.27.2.32`
- 扫描日期：`2026-08-11`
- 扫描方式：指定目录全量文件盘点、关键字与所有者文件复核
- 结论：已有智能开发底座覆盖Metadata、Schema、Registry、Runtime、组件、CRUD、权限、流程与智能分析；本版本不新建同类框架

## 1. 指定目录扫描结果

| 指定目录 | 状态/文件数 | 归属结论 |
|---|---:|---|
| `frontend/src/meta` | 存在 / 1294 | 前端智能化能力总目录 |
| `frontend/src/runtime` | 不存在 / 0 | 能力已归属`frontend/src/meta/runtime`，禁止机械补建 |
| `frontend/src/schema` | 不存在 / 0 | 能力已归属`frontend/src/meta/schema`与`meta/core` |
| `frontend/src/components` | 不存在 / 0 | 智能公共组件归属`frontend/src/meta/components` |
| `backend/runtime` | 不存在 / 0 | 通用流程归属`backend/workflow_runtime`，领域Runtime归属模块目录 |
| `backend/services` | 不存在 / 0 | 服务按`backend/<module>/*service*.py/services.py`归属 |
| `docs/governance` | 存在 / 90 | 现有治理、专项规范、案例与验收资产 |

目录不存在不等于能力缺失。未经所有权和引用审计，不得新建同名目录复制现有实现。

## 2. PCE Intelligence Capability Inventory

| 能力名称 | 所在文件（代表性正式所有者） | 当前用途 | 可复用范围 |
|---|---|---|---|
| Schema契约与解析 | `frontend/src/meta/core/schemaContract.js`、`schemaNormalizer.js`、`schemaRegistry.js`、`schemaResolver.js` | 字段契约、标准化、注册和解析 | 字段/页面自动生成、Schema校验 |
| Meta与模块注册 | `frontend/src/meta/registry/metaRegistry.js`、`moduleRegistry.js`、`globalModuleRegistry.js` | Meta和模块统一发现 | 新模块注册、Schema/页面接管 |
| 基础资料Registry | `frontend/src/meta/master-data/masterDataRegistry.js` | 基础资料列、筛选、选项与页面定义 | 员工、物料、供应商、关系、价格、工序、工艺、设备 |
| 企业列表契约 | `frontend/src/meta/runtime/pceEnterpriseListContract.js`、`pceTableColumnRuntime.js` | 表格列、固定列、滚动与企业列表契约 | 全部企业级列表 |
| 筛选Runtime | `frontend/src/meta/runtime/listFilterRuntime.js`、`unifiedFilterSchema.js`、`pceAdvancedFilterContract.js` | 筛选Schema解析和执行 | 高级筛选自动生成与统一校验 |
| 下拉选项Runtime | `frontend/src/meta/runtime/remoteSelectOptionsProvider.js` | 受治理远程选项加载 | 主数据与业务枚举下拉 |
| 企业列表/筛选组件 | `frontend/src/meta/components/PceEnterpriseListTable.vue`、`PceEnterpriseAdvancedFilter.vue`、`PceAdvancedFilterField.vue`、`PceBusinessStatus.vue` | 通用表格、筛选和中文业务状态 | 所有企业列表页面，禁止页面重建 |
| CRUD与页面生成 | `frontend/src/meta/crud/crudEngine.js`、`CRUDRenderer.vue`、`formGenerator.js`、`frontend/src/meta/core/pageRenderer.js` | Schema驱动CRUD、表单和页面渲染 | 适用的基础资料与配置页面 |
| 权限与Action治理 | `frontend/src/meta/runtime/permissionEngine.js`、`pceBusinessActionRegistry.js`、`backend/workflow_runtime/action_permissions.py` | 页面动作、权限与服务端授权 | 列、筛选、按钮和业务Action权限 |
| 流程Runtime | `backend/workflow_runtime/state_transitions.py`、`providers.py`、`facts.py`、`write_intents.py` | 状态迁移、事实、Provider和写意图 | 跨模块流程治理，不复制到`backend/runtime` |
| 主数据Runtime | `backend/masterdata/material_master_runtime.py`、`backend/masterdata/supplier_master_runtime.py`、`backend/masterdata/material_supplier_relation_runtime.py`、`backend/masterdata/master_data_statistics_runtime.py` | 物料、供应商、关系、价格和统计的服务端事实 | 基础资料列表、引用、统计和完整性检查 |
| SCM事实服务 | `backend/procurement/scm_runtime_services.py`、`supplier_quotation_service.py`、`purchase_order_supplier_fact_runtime.py` | 询价、报价、订单供应商事实 | 采购链只读事实、来源追踪与Guard输入 |
| 领域智能能力 | `frontend/src/meta/intelligence`、`meta/ai`、`meta/decision`、`meta/prediction`、`meta/optimization`、`meta/autonomy` | 分析、决策支持、预测、优化与自治实验能力 | 只读分析与建议；落地前必须验证事实、权限和人工边界 |
| 验收与治理 | `frontend/src/meta/acceptance`、`docs/governance/05-自动验收治理` | 自动验收、反向用例、证据和门禁 | 每版本能力复用与禁止重复框架检查 |

## 3. 并行能力审计

`frontend/src/platform/runtime/metaRuntimeV7.js`、`metaRuntimeV10.js`、`metaNormalizer.js`、`metaFormEngine.js`和`metaControlCenter.js`构成历史Platform Meta Runtime族。它们是待收敛候选，不是新框架建设依据。在完成进口引用、事实所有者、消费者和兼容性审计前，禁止扩建、删除或用其替代`frontend/src/meta`正式所有者。

## 4. 企业自主维护能力

| 能力 | 当前事实 | 决策 |
|---|---|---|
| 修改列名称 | 未发现租户/角色级服务端持久化闭环 | 暂缓；未来扩展现有Registry |
| 隐藏列 | 未发现完整权限、版本和审计闭环 | 暂缓 |
| 调整排序 | `uiEvolutionEngine`有运行时重排，不等于企业配置持久化 | 只作为候选能力 |
| 配置筛选 | Registry支持开发期Schema配置 | 直接复用；用户维护能力暂缓 |
| 配置下拉来源 | 已有`optionsSource/optionsProvider` | 直接复用；用户维护须服务端授权 |

未来扩展必须在现有Registry之上增加租户、角色、权限、版本、审计、回滚和服务端持久化投影，禁止以`localStorage`或第二套Config事实替代。
