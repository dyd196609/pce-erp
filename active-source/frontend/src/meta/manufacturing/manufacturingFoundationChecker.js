import {
  getEnabledCustomers,
  getEnabledMaterials,
  getEnabledSuppliers,
  getEnabledWarehouses,
  getEnabledWorkCenters,
  getDefaultPrice,
  getEmployeeOptions,
  getLocationOptions,
  getReferenceState,
  getRecommendedSuppliers,
} from './manufacturingReferenceService.js'
import {
  getInventoryBalances,
  getInventoryTransactions,
  getReceivableScmPurchaseOrders,
  getWarehouseTasks,
} from '../wms/wmsStore.js'
import { listPurchaseReceives } from '../wms/purchaseReceiveStore.js'
import { listIncomingInspections } from '../qms/qmsStore.js'

function result(id, category, name, status, message, suggestion, route) {
  return { id, category, name, status, message, suggestion, route }
}

function hasItems(items) {
  return Array.isArray(items) && items.length > 0
}

function hasEnabled(items) {
  return hasItems(items)
}

function missing(id, category, name, message, suggestion, route) {
  return result(id, category, name, 'missing', message, suggestion, route)
}

function warning(id, category, name, message, suggestion, route) {
  return result(id, category, name, 'warning', message, suggestion, route)
}

function passed(id, category, name, message, route) {
  return result(id, category, name, 'passed', message, '无需处理', route)
}

export function checkMaterials() {
  const materials = getEnabledMaterials()
  const missingSafetyStock = materials.filter((item) => Number(item.raw.safetyStock || 0) <= 0)
  const missingDefaultWarehouse = materials.filter((item) => !item.raw.defaultWarehouseId && !item.raw.defaultWarehouse)

  return [
    hasEnabled(materials)
      ? passed('materials-enabled', 'ERP主数据', '启用物料', `已找到 ${materials.length} 个启用物料。`, '/foundation/erp/materials')
      : missing('materials-enabled', 'ERP主数据', '启用物料', '未找到启用物料，后续 SCM/WMS/MRP/MES 无法引用物料。', '请先维护并启用物料主数据。', '/foundation/erp/materials'),
    missingDefaultWarehouse.length
      ? warning('materials-default-warehouse', 'ERP主数据', '物料默认仓库', `${missingDefaultWarehouse.length} 个物料未配置默认仓库。`, '建议为关键物料配置默认仓库，便于 WMS/MRP 默认引用。', '/foundation/erp/materials')
      : passed('materials-default-warehouse', 'ERP主数据', '物料默认仓库', '物料默认仓库配置检查通过。', '/foundation/erp/materials'),
    missingSafetyStock.length
      ? warning('materials-safety-stock', 'ERP主数据', '物料安全库存', `${missingSafetyStock.length} 个物料未配置安全库存或安全库存为 0。`, '建议为关键物料配置安全库存，用于库存预警和 MRP 计算。', '/foundation/erp/materials')
      : passed('materials-safety-stock', 'ERP主数据', '物料安全库存', '物料安全库存配置检查通过。', '/foundation/erp/materials'),
  ]
}

export function checkCustomers() {
  const customers = getEnabledCustomers()
  const missingCredit = customers.filter((item) => !item.raw.creditLimit && !item.raw.creditLevel)
  return [
    hasEnabled(customers)
      ? passed('customers-enabled', 'ERP主数据', '启用客户', `已找到 ${customers.length} 个启用客户。`, '/foundation/erp/customers')
      : missing('customers-enabled', 'ERP主数据', '启用客户', '未找到启用客户，后续 CRM/MPS 无法引用客户。', '请先维护并启用客户主数据。', '/foundation/erp/customers'),
    missingCredit.length
      ? warning('customers-credit', 'ERP主数据', '客户信用信息', `${missingCredit.length} 个客户未配置信用额度或信用等级。`, '建议维护客户信用等级或信用额度，便于 CRM 信用控制。', '/foundation/erp/customers')
      : passed('customers-credit', 'ERP主数据', '客户信用信息', '客户信用信息检查通过。', '/foundation/erp/customers'),
  ]
}

export function checkSuppliers() {
  const suppliers = getEnabledSuppliers()
  const missingLeadTime = suppliers.filter((item) => !item.raw.leadTime && !item.raw.deliveryCycle)
  return [
    hasEnabled(suppliers)
      ? passed('suppliers-enabled', 'ERP主数据', '启用供应商', `已找到 ${suppliers.length} 个启用供应商。`, '/foundation/erp/suppliers')
      : missing('suppliers-enabled', 'ERP主数据', '启用供应商', '未找到启用供应商，后续 SCM/QMS 无法引用供应商。', '请先维护并启用供应商主数据。', '/foundation/erp/suppliers'),
    missingLeadTime.length
      ? warning('suppliers-lead-time', 'ERP主数据', '供应商交货周期', `${missingLeadTime.length} 个供应商未配置交货周期。`, '建议维护交货周期，便于 SCM 交期预警和 MRP 采购建议。', '/foundation/erp/suppliers')
      : passed('suppliers-lead-time', 'ERP主数据', '供应商交货周期', '供应商交货周期检查通过。', '/foundation/erp/suppliers'),
  ]
}

export function checkWarehouses() {
  const warehouses = getEnabledWarehouses()
  return [
    hasEnabled(warehouses)
      ? passed('warehouses-enabled', 'ERP主数据', '启用仓库', `已找到 ${warehouses.length} 个启用仓库。`, '/foundation/erp/warehouses')
      : missing('warehouses-enabled', 'ERP主数据', '启用仓库', '未找到启用仓库，后续 WMS/MRP/MES 无法引用仓库。', '请先维护并启用仓库。', '/foundation/erp/warehouses'),
  ]
}

export function checkLocations() {
  const locations = getLocationOptions()
  const warehouses = getEnabledWarehouses()
  const warehousesWithoutLocations = warehouses.filter((warehouse) => !(warehouse.raw.locations || []).length)

  return [
    hasItems(locations)
      ? passed('locations-exist', 'ERP主数据', '仓库库位', `已找到 ${locations.length} 个库位。`, '/foundation/erp/warehouses')
      : missing('locations-exist', 'ERP主数据', '仓库库位', '未找到库位，后续 WMS 无法进行库位级引用。', '请在仓库资料中维护库位。', '/foundation/erp/warehouses'),
    warehousesWithoutLocations.length
      ? warning('warehouse-location-link', 'ERP主数据', '仓库关联库位', `${warehousesWithoutLocations.length} 个启用仓库没有关联库位。`, '建议每个启用仓库至少维护一个库位。', '/foundation/erp/warehouses')
      : passed('warehouse-location-link', 'ERP主数据', '仓库关联库位', '启用仓库均有关联库位。', '/foundation/erp/warehouses'),
  ]
}

export function checkWorkCenters() {
  const workCenters = getEnabledWorkCenters()
  return [
    hasEnabled(workCenters)
      ? passed('work-centers-enabled', 'ERP主数据', '工作中心', `已找到 ${workCenters.length} 个启用工作中心。`, '/foundation/erp/work-centers')
      : missing('work-centers-enabled', 'ERP主数据', '工作中心', '未找到工作中心，后续 MRP/APS/MES 无法引用产能资源。', '请先维护工作中心。', '/foundation/erp/work-centers'),
  ]
}

export function checkEmployees() {
  const foundation = getReferenceState()
  return [
    hasItems(foundation.employees)
      ? passed('employees-exist', 'PFM人员档案', '员工', `已找到 ${foundation.employees.length} 名员工。`, '/foundation/pfm/employees')
      : missing('employees-exist', 'PFM人员档案', '员工', '未找到员工，后续 APS/MES/KPI 无法引用人员。', '请先维护员工档案。', '/foundation/pfm/employees'),
    hasItems(foundation.departments)
      ? passed('departments-exist', 'PFM人员档案', '部门', `已找到 ${foundation.departments.length} 个部门。`, '/foundation/pfm/employees')
      : missing('departments-exist', 'PFM人员档案', '部门', '未找到部门，组织和绩效引用不完整。', '请先维护部门资料。', '/foundation/pfm/employees'),
    hasItems(foundation.roles)
      ? passed('roles-exist', 'PFM人员档案', '岗位/角色', `已找到 ${foundation.roles.length} 个岗位/角色。`, '/foundation/pfm/employees')
      : missing('roles-exist', 'PFM人员档案', '岗位/角色', '未找到岗位/角色，权限与流程责任人引用不完整。', '请先维护岗位/角色。', '/foundation/pfm/employees'),
    hasItems(foundation.shifts)
      ? passed('shifts-exist', 'PFM人员档案', '班次', `已找到 ${foundation.shifts.length} 个班次。`, '/foundation/pfm/shifts')
      : missing('shifts-exist', 'PFM人员档案', '班次', '未找到班次，后续 APS/MES 无法引用排班资料。', '请先维护班次。', '/foundation/pfm/shifts'),
  ]
}

export function checkPermissions() {
  const permissions = getReferenceState().permissionPoints
  return [
    hasItems(permissions)
      ? passed('permissions-exist', '权限与日志', '权限点', `已找到 ${permissions.length} 个权限点。`, '/foundation/security/permissions')
      : missing('permissions-exist', '权限与日志', '权限点', '未找到权限点，后续模块无法建立统一权限引用。', '请先维护权限点。', '/foundation/security/permissions'),
  ]
}

export function checkWarningRules() {
  const rules = getReferenceState().warningRules
  return [
    hasItems(rules)
      ? passed('warning-rules-exist', '预警引擎基础', '预警规则', `已找到 ${rules.length} 条预警规则。`, '/foundation/warnings/rules')
      : missing('warning-rules-exist', '预警引擎基础', '预警规则', '未找到预警规则，后续模块无法引用统一预警基础。', '请先维护预警规则。', '/foundation/warnings/rules'),
  ]
}

export function checkSystemParameters() {
  const parameters = getReferenceState().systemParameters
  return [
    hasItems(parameters)
      ? passed('system-parameters-exist', 'ERP主数据', '系统参数', `已找到 ${parameters.length} 个系统参数。`, '/foundation/erp/system-parameters')
      : missing('system-parameters-exist', 'ERP主数据', '系统参数', '未找到系统参数，后续模块缺少统一参数引用。', '请先维护系统参数。', '/foundation/erp/system-parameters'),
  ]
}

export function checkScmReferences() {
  const materials = getEnabledMaterials()
  const suppliers = getEnabledSuppliers()
  const warehouses = getEnabledWarehouses()
  const locations = getLocationOptions()
  const employees = getEmployeeOptions().filter((item) => !String(item.status || item.raw?.status || '').toLowerCase().includes('disabled'))
  const materialsWithSupplier = materials.filter((item) => getRecommendedSuppliers(item.id).length)
  const materialsWithPrice = materials.filter((item) => {
    const supplierId = getRecommendedSuppliers(item.id)[0]?.supplierId
    return supplierId && getDefaultPrice(item.id, supplierId)
  })
  const materialsWithWarehouse = materials.filter((item) => item.raw?.defaultWarehouseId || item.raw?.defaultWarehouse)

  return [
    materials.length
      ? passed('scm-material-reference', 'SCM引用检查', '启用物料下拉源', `SCM 可读取 ${materials.length} 个启用物料。`, '/scm/purchase-requests')
      : missing('scm-material-reference', 'SCM引用检查', '启用物料下拉源', 'SCM 没有可用物料下拉数据。', '请维护并启用物料基础资料。', '/foundation/erp/materials'),
    suppliers.length
      ? passed('scm-supplier-reference', 'SCM引用检查', '启用供应商下拉源', `SCM 可读取 ${suppliers.length} 个启用供应商。`, '/scm/purchase-inquiries')
      : missing('scm-supplier-reference', 'SCM引用检查', '启用供应商下拉源', 'SCM 没有可用供应商下拉数据。', '请维护并启用供应商基础资料。', '/foundation/erp/suppliers'),
    materialsWithSupplier.length
      ? passed('scm-recommended-supplier', 'SCM引用检查', '物料推荐供应商', `${materialsWithSupplier.length} 个物料已配置推荐供应商。`, '/foundation/erp/supplier-prices')
      : warning('scm-recommended-supplier', 'SCM引用检查', '物料推荐供应商', '尚未发现物料供应商关系，SCM 无法自动推荐供应商。', '请维护物料供应商关系，并设置主供应商或优先级。', '/foundation/erp/supplier-prices'),
    materialsWithPrice.length
      ? passed('scm-default-price', 'SCM引用检查', '默认采购价格', `${materialsWithPrice.length} 个物料可通过推荐供应商带出默认价格。`, '/foundation/erp/supplier-prices')
      : warning('scm-default-price', 'SCM引用检查', '默认采购价格', '尚未发现可自动带出的供应商物料价格。', '请维护供应商物料价格，避免询价/订单明细无价格。', '/foundation/erp/supplier-prices'),
    warehouses.length && locations.length
      ? passed('scm-warehouse-location', 'SCM引用检查', '仓库库位引用', `SCM 可读取 ${warehouses.length} 个仓库和 ${locations.length} 个库位。`, '/foundation/erp/warehouses')
      : warning('scm-warehouse-location', 'SCM引用检查', '仓库库位引用', '仓库或库位引用不完整，采购订单无法自动带出入库位置。', '请维护仓库与库位基础资料。', '/foundation/erp/warehouses'),
    materialsWithWarehouse.length
      ? passed('scm-material-default-warehouse', 'SCM引用检查', '物料默认仓库', `${materialsWithWarehouse.length} 个物料配置了默认仓库。`, '/foundation/erp/materials')
      : warning('scm-material-default-warehouse', 'SCM引用检查', '物料默认仓库', '物料未配置默认仓库，采购订单只能使用首个启用仓库。', '建议为常用物料维护默认仓库和库位。', '/foundation/erp/materials'),
    employees.length
      ? passed('scm-employee-reference', 'SCM引用检查', '请购人与采购员', `SCM 可读取 ${employees.length} 个员工用于请购人/采购员字段。`, '/foundation/pfm/employees')
      : missing('scm-employee-reference', 'SCM引用检查', '请购人与采购员', 'SCM 没有可用员工选项。', '请维护人员档案。', '/foundation/pfm/employees'),
  ]
}

export function checkWmsReferences() {
  const materials = getEnabledMaterials()
  const warehouses = getEnabledWarehouses()
  const locations = getLocationOptions()
  const balances = getInventoryBalances()
  const transactions = getInventoryTransactions()
  const tasks = getWarehouseTasks()
  const receivableOrders = getReceivableScmPurchaseOrders()
  const balancesWithRefs = balances.filter((item) => item.materialId && item.warehouseId && item.locationId)
  const balancesWithStatus = balances.filter((item) => {
    if (Number(item.maxStock || 0) > 0 && Number(item.quantity || 0) > Number(item.maxStock || 0)) return item.status === 'overStock'
    if (Number(item.safetyStock || 0) > 0 && Number(item.quantity || 0) < Number(item.safetyStock || 0)) return item.status === 'lowStock'
    return ['normal', 'locked'].includes(item.status)
  })
  const transactionWithBeforeAfter = transactions.filter((item) => item.beforeQuantity !== undefined && item.afterQuantity !== undefined)
  const receiveTasks = tasks.filter((item) => item.sourceType === 'scmPurchaseOrder')

  return [
    materials.length
      ? passed('wms-material-reference', 'WMS引用检查', '读取启用物料', `WMS 可读取 ${materials.length} 个启用物料。`, '/wms/inventory-balances')
      : missing('wms-material-reference', 'WMS引用检查', '读取启用物料', 'WMS 没有可用物料引用源。', '请先维护并启用物料。', '/foundation/erp/materials'),
    warehouses.length
      ? passed('wms-warehouse-reference', 'WMS引用检查', '读取启用仓库', `WMS 可读取 ${warehouses.length} 个启用仓库。`, '/wms/inventory-balances')
      : missing('wms-warehouse-reference', 'WMS引用检查', '读取启用仓库', 'WMS 没有可用仓库引用源。', '请先维护并启用仓库。', '/foundation/erp/warehouses'),
    locations.length
      ? passed('wms-location-reference', 'WMS引用检查', '读取启用库位', `WMS 可读取 ${locations.length} 个库位。`, '/wms/inventory-balances')
      : missing('wms-location-reference', 'WMS引用检查', '读取启用库位', 'WMS 没有可用库位引用源。', '请先维护仓库库位。', '/foundation/erp/warehouses'),
    balancesWithRefs.length === balances.length && balances.length
      ? passed('wms-balance-reference-integrity', 'WMS引用检查', '库存余额引用完整', `库存余额 ${balances.length} 行均包含物料、仓库、库位。`, '/wms/inventory-balances')
      : warning('wms-balance-reference-integrity', 'WMS引用检查', '库存余额引用完整', '部分库存余额缺少物料、仓库或库位引用。', '请检查库存余额演示数据或基础资料引用。', '/wms/inventory-balances'),
    balancesWithStatus.length === balances.length && balances.length
      ? passed('wms-balance-status-rule', 'WMS引用检查', '库存状态自动判断', '库存状态已根据安全库存和最高库存判断。', '/wms/inventory-balances')
      : warning('wms-balance-status-rule', 'WMS引用检查', '库存状态自动判断', '部分库存状态与安全库存/最高库存不一致。', '请重新生成或更新库存余额状态。', '/wms/inventory-balances'),
    transactionWithBeforeAfter.length === transactions.length && transactions.length
      ? passed('wms-transaction-before-after', 'WMS引用检查', '库存流水前后数量', `库存流水 ${transactions.length} 条均记录变动前后数量。`, '/wms/inventory-transactions')
      : warning('wms-transaction-before-after', 'WMS引用检查', '库存流水前后数量', '部分库存流水缺少变动前后数量。', '请通过 applyInventoryTransaction 写入库存流水。', '/wms/inventory-transactions'),
    receivableOrders.length || receiveTasks.length
      ? passed('wms-scm-receive-preview', 'WMS引用检查', 'SCM到货预备', `已识别 ${receivableOrders.length} 张待收货采购订单，已有 ${receiveTasks.length} 条收货任务。`, '/wms/purchase-receive-preview')
      : warning('wms-scm-receive-preview', 'WMS引用检查', 'SCM到货预备', '当前没有可预备收货的已审批采购订单。', '请先在 SCM 形成已审批采购订单。', '/scm/purchase-orders'),
    receiveTasks.every((task) => !transactions.some((txn) => txn.sourceType === 'scmPurchaseOrder' && String(txn.sourceId) === String(task.sourceId)))
      ? passed('wms-receive-task-no-stock-change', 'WMS引用检查', '收货任务不直接改库存', 'SCM到货预备只生成仓库任务，没有直接增加库存流水。', '/wms/purchase-receive-preview')
      : warning('wms-receive-task-no-stock-change', 'WMS引用检查', '收货任务不直接改库存', '发现收货任务直接关联库存流水。', '本阶段应只生成收货任务，不直接增加库存。', '/wms/purchase-receive-preview'),
    warehouses.length && locations.length
      ? passed('wms-disabled-reference-filter', 'WMS引用检查', '停用仓库库位过滤', 'WMS 新增选择只读取启用仓库和启用库位。', '/wms/inventory-balances')
      : warning('wms-disabled-reference-filter', 'WMS引用检查', '停用仓库库位过滤', '仓库或库位引用源为空，无法验证停用过滤。', '请维护仓库和库位。', '/foundation/erp/warehouses'),
  ]
}

export function checkScmWmsQmsBoundary() {
  const materials = getEnabledMaterials()
  const warehouses = getEnabledWarehouses()
  const locations = getLocationOptions()
  const employees = getEmployeeOptions()
  const purchaseReceives = listPurchaseReceives()
  const incomingInspections = listIncomingInspections()
  const transactions = getInventoryTransactions()
  const receiveTasks = getWarehouseTasks().filter((task) => task.taskType === 'purchaseReceive')
  const receiveNos = new Set(purchaseReceives.map((item) => item.receiveNo))
  const inspectionSourceNos = new Set(incomingInspections.map((item) => item.sourceReceiveNo))
  const receiveStockTransactions = transactions.filter((txn) => ['purchaseReceivePreview', 'purchaseReceive', 'incomingInspection'].includes(txn.sourceType))

  return [
    passed('wms-purchase-receive-preview-available', 'SCM-WMS-QMS边界检查', 'WMS采购收货预备可用', `采购收货预备能力已接入，当前 ${purchaseReceives.length} 张预备单。`, '/wms/purchase-receives'),
    passed('qms-incoming-inspection-preview-available', 'SCM-WMS-QMS边界检查', 'QMS来料检验预备可用', `来料检验预备能力已接入，当前 ${incomingInspections.length} 张预备单。`, '/qms/incoming-inspections'),
    receiveTasks.length || purchaseReceives.length || incomingInspections.length
      ? passed('scm-wms-qms-traceable', 'SCM-WMS-QMS边界检查', 'SCM到WMS到QMS可追踪', `已识别 ${receiveTasks.length} 条收货任务、${purchaseReceives.length} 张收货预备、${incomingInspections.length} 张检验预备。`, '/wms/purchase-receives')
      : warning('scm-wms-qms-traceable', 'SCM-WMS-QMS边界检查', 'SCM到WMS到QMS可追踪', '当前还没有形成仓库任务、收货预备或检验预备。', '请从 SCM 已审批采购订单生成收货任务或收货预备单。', '/wms/purchase-receive-preview'),
    incomingInspections.every((item) => !item.sourceReceiveNo || receiveNos.has(item.sourceReceiveNo) || inspectionSourceNos.has(item.sourceReceiveNo))
      ? passed('qms-source-receive-linked', 'SCM-WMS-QMS边界检查', 'QMS来源收货预备可追踪', '来料检验预备单保留来源收货单号。', '/qms/incoming-inspections')
      : warning('qms-source-receive-linked', 'SCM-WMS-QMS边界检查', 'QMS来源收货预备可追踪', '部分检验预备单缺少可追踪来源收货单。', '请从采购收货预备单生成来料检验预备。', '/wms/purchase-receives'),
    receiveStockTransactions.length === 0
      ? passed('scm-wms-qms-no-direct-stock', 'SCM-WMS-QMS边界检查', '预备链路不直接入库', '采购收货预备与来料检验预备没有生成库存入库流水。', '/wms/inventory-transactions')
      : warning('scm-wms-qms-no-direct-stock', 'SCM-WMS-QMS边界检查', '预备链路不直接入库', '发现预备链路相关库存流水。', '本阶段应只做预备，不直接增加库存。', '/wms/inventory-transactions'),
    materials.length && warehouses.length && locations.length && employees.length
      ? passed('reference-service-still-source', 'SCM-WMS-QMS边界检查', '引用源仍来自manufacturingReferenceService', '物料、仓库、库位、员工均通过制造业基础资料引用服务读取。', '/reference/check')
      : warning('reference-service-still-source', 'SCM-WMS-QMS边界检查', '引用源仍来自manufacturingReferenceService', '物料、仓库、库位或员工引用源为空。', '请维护制造业基础资料后再验证。', '/reference/check'),
  ]
}

export function runFoundationCheck() {
  return [
    ...checkMaterials(),
    ...checkCustomers(),
    ...checkSuppliers(),
    ...checkWarehouses(),
    ...checkLocations(),
    ...checkWorkCenters(),
    ...checkEmployees(),
    ...checkPermissions(),
    ...checkWarningRules(),
    ...checkSystemParameters(),
    ...checkScmReferences(),
    ...checkWmsReferences(),
    ...checkScmWmsQmsBoundary(),
  ]
}
