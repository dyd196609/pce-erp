# SCM采购申请物料选择器数据源诊断报告

## 1. 任务信息

- Version：`V1.14.2.8.4.27.2.22`
- 目标页面：`#/scm/purchase-request`
- 对照页面：`#/master-data/materials`
- 执行方式：源码链路追踪、SQLite 只读查询、浏览器只读渲染核对
- 业务写入：`0`

## 2. Purchase Request Material Selector Trace

|层级|实际来源|
|---|---|
|Route|`frontend/src/router/index.js` → `ScmPurchaseRequestPage.vue`|
|Page Component|`frontend/src/meta/pages/ScmPurchaseRequestPage.vue`|
|Business Region|`frontend/src/meta/components/ScmPurchaseRequestOriginalBusinessRegion.vue`|
|Select|`configs.request.detailFields[key=materialId]`，Provider=`materialProvider`|
|Options Provider|`purchaseRequestProviderRuntimeRegistry.js` → `loadMaterialProvider()`|
|Store|N/A；Provider 使用 Vue reactive 只读运行缓存，不是独立物料事实库|
|Frontend API|`purchaseRequestApi.searchReference('materials', '', 200)`|
|HTTP API|`GET /api/procurement/purchase-request-references/materials/?q=&limit=200`|
|Backend Query|`Material.objects.select_related('category').filter(is_active=True, is_purchased=True)`|
|Domain/Database|`masterdata.models.Material` → SQLite `backend/db.sqlite3` → table `material`|
|Record Count|数据库总数 80；启用 80；启用且可采购 80；浏览器选择器渲染 80 个物料选项|

结论：80 个物料属于 **A. MaterialMaster**，不是页面临时数据、采购申请专用库或制造 Demo Store。维护入口应当是正式 `Material` 管理能力/API；当前 `#/master-data/materials` 页面没有消费该数据库事实，因此用户看不到这 80 条。

## 3. “4条”来源追踪

`#/master-data/materials` 使用 `EnterpriseMasterDataPage.vue`，调用：

```text
GET /api/masterdata/enterprise/materials/facts/
-> backend/masterdata/enterprise_master_data.py
-> definition["materials"].rows
-> 4 条静态服务端验收事实
```

该页面虽然诊断标签为 `factSource=server`，但其数据是 Python 文件中的静态 rows，不是 `masterdata.models.Material` / `material` 表。它与采购申请选择器是两个事实集合。

## 4. Material Source Matrix

|来源|页面|对象|数量|维护位置|
|---|---|---|---:|---|
|企业物料展示事实|`#/master-data/materials`|`enterprise_master_data.py[materials].rows`|4|源码静态验收事实；不是正式物料维护库|
|采购申请选择器|`#/scm/purchase-request`|`masterdata.models.Material`|80|SQLite `backend/db.sqlite3` 的 `material` 表；API 为采购申请引用接口|

`MATERIAL-SOURCE-UNIQUE-001` 当前结果：**FAIL**。失败对象是维护页与业务引用接口的事实所有者不一致，不是 80 条数据库物料本身无效。

## 5. 80条物料字段完整性

|字段|完整数量|结论|
|---|---:|---|
|物料编码|80/80|完整|
|物料名称|80/80|完整|
|规格|80/80|完整|
|单位（采购单位优先，否则基础单位）|80/80|完整|
|分类|80/80|完整|
|类型|80/80|完整|
|状态|80/80|完整，均启用且可采购|
|供应商关联|0/80|MaterialMaster 未建立正式 Material-Supplier 关系；采购申请仅有建议供应商字段|
|维护时间|80/80|完整|

`MATERIAL-MASTER-FIELD-COMPLETE-001` 对核心物料字段为 PASS；供应商关联属于缺失的独立关系能力，不允许用建议供应商冒充。

## 6. Material Consolidation Proposal（仅设计，不执行）

1. 当前来源：正式数据库 Material 80 条；企业物料页面静态验收 rows 4 条。
2. 目标来源：`masterdata.models.Material` / `material` 表成为唯一 MaterialMaster；企业物料页面、采购申请引用接口及后续业务 Provider 均读取该事实。
3. 字段映射：`materialCode→code`、`materialName→name`、`specification→specification`、`unit→unit/purchase_unit`、`category→category.name`、`materialType→material_type`、`businessStatus→is_active`。
4. 重复风险：4 条 `MAT-*` 编码与现有 80 条 `MT*` 编码当前不直接重复，但名称、规格和业务含义仍需人工去重；静态 ID 不能直接作为数据库 ID。
5. 迁移步骤：冻结快照 → 按编码/名称/规格生成重复报告 → 人工决定4条是验收数据隔离还是正式导入 → 受控迁移 → 企业物料页面切换正式 Provider → 对齐筛选条件和计数 → 全链回归。

本版本不执行导入、删除、合并或页面切换。

## 7. Impact Analysis

|模块|当前影响|
|---|---|
|采购申请|实际选择 80 条数据库 Material；与企业物料页面所见不一致，维护人员无法从当前页面核对选择器数据|
|询价|继承 PurchaseRequestItem 快照；来源仍可追到数据库 Material ID|
|供应商报价|继承询价物料；名称/规格依赖上游快照，主数据页面不一致会增加人工核对成本|
|核价|价格证据按物料编码聚合；双源可能造成编码口径分裂|
|供应商推荐|物料与供应商证据可能被误认为来自企业物料页的4条集合|
|采购订单|V1.14.2.8.4.27.2.21 已要求回查 PurchaseRequestItem + MaterialMaster；数据库80条是当前可解析来源|
|库存|若库存模块读取另一 Store/Provider，会继续扩大同名物料多源风险，需后续专项扫描|
|MRP|制造基础 Store 曾存在独立样例物料能力；正式 MRP 必须改为只引用统一 MaterialMaster，不能把样例 Store 作为生产事实|

## 8. 验收结论

- `MATERIAL-SELECTOR-SOURCE-TRACE-001`：PASS
- `MATERIAL-SOURCE-UNIQUE-001`：FAIL（已准确识别双源；本诊断版本未获授权合并）
- `MATERIAL-MASTER-FIELD-COMPLETE-001`：PASS（核心字段 80/80）
- Duplicate Source Detection：PASS
- PurchaseOrder Changed：NO
- PurchaseRequest Changed：NO
- Database Changed：NO
- Business Write Count：0

诊断完成状态：`MATERIAL_SOURCE_TRACE_COMPLETED`。

## 9. V1.14.2.8.4.27.2.23 统一治理结果

经全项目引用扫描，4条 `enterprise_master_data.py` 静态物料仅用于旧验收展示，没有进入采购申请、采购订单、库存、BOM/MRP/MES业务链。V1.14.2.8.4.27.2.23 已删除该静态集合，并将企业物料页面和采购申请引用接口统一到 `MaterialMasterRuntimeAdapter → MaterialRuntimeModel → masterdata.Material/material`。

自该版本起，`MATERIAL-SOURCE-UNIQUE-001` 由诊断期 FAIL 转为 PASS；本节是后续整改记录，不改写第8节的历史诊断结论。
