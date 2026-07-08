import { getFoundationState } from './manufacturingFoundationStore.js'

function clone(value) {
  return JSON.parse(JSON.stringify(value))
}

function state() {
  return getFoundationState()
}

function enabled(item) {
  const status = String(item?.status || 'enabled').toLowerCase()
  return status !== 'disabled' && status !== '停用' && !status.includes('停用')
}

function statusName(item, name) {
  return enabled(item) ? name : `${name}（已停用）`
}

function option(item, type, extra = {}) {
  const rawName = item.name || item.userName || item.role || item.key || item.processName || item.routingName || item.equipmentName || item.categoryName || item.id
  return {
    id: item.id,
    code: item.code || item.employeeNo || item.key || item.prefix || item.processCode || item.routingCode || item.equipmentCode || item.categoryCode || item.supplierMaterialCode || item.relationCode || item.id,
    name: statusName(item, rawName),
    type,
    status: item.status || 'enabled',
    sourceModule: extra.sourceModule || 'V1.11.6制造业基础资料',
    raw: clone(item),
    ...extra,
  }
}

function byCode(collection, code, codeKeys = ['code']) {
  const value = String(code || '')
  return clone((collection || []).find((item) => codeKeys.some((key) => String(item[key] || '') === value)) || null)
}

function exists(collection, id) {
  return Boolean((collection || []).find((item) => String(item.id) === String(id)))
}

export function getReferenceState() {
  return state()
}

export function getEmployeeOptions() {
  return state().employees.map((item) => option(item, '员工', { code: item.employeeNo || item.id, sourceModule: 'PFM人员档案' }))
}

export function getDepartmentOptions() {
  return state().departments.map((item) => option(item, '部门', { sourceModule: 'PFM组织资料' }))
}

export function getRoleOptions() {
  return state().roles.map((item) => option(item, '岗位/角色', { sourceModule: 'PFM组织资料' }))
}

export function getSkillOptions() {
  return state().skills.filter(enabled).map((item) => option(item, '技能', { sourceModule: 'PFM人员档案' }))
}

export function getShiftOptions() {
  return state().shifts.filter(enabled).map((item) => option(item, '班次', { sourceModule: 'PFM人员档案' }))
}

export function getWorkCenterOptions() {
  return state().workCenters.map((item) => option(item, '工作中心', { sourceModule: 'ERP主数据' }))
}

export function getMaterialOptions() {
  return state().materials.map((item) => option(item, '物料', { sourceModule: 'ERP主数据' }))
}

export function getCustomerOptions() {
  return state().customers.map((item) => option(item, '客户', { sourceModule: 'ERP主数据' }))
}

export function getSupplierOptions() {
  return state().suppliers.map((item) => option(item, '供应商', { sourceModule: 'ERP主数据' }))
}

export function getWarehouseOptions() {
  return state().warehouses.map((item) => option(item, '仓库', { sourceModule: 'ERP主数据' }))
}

export function getLocationOptions(warehouseId) {
  const warehouses = state().warehouses.filter((warehouse) => enabled(warehouse))
  const selectedWarehouses = warehouseId ? warehouses.filter((warehouse) => String(warehouse.id) === String(warehouseId)) : warehouses
  return selectedWarehouses.flatMap((warehouse) => (warehouse.locations || []).map((location) => option(location, '库位', {
    warehouseId: warehouse.id,
    warehouseName: warehouse.name,
    sourceModule: 'ERP主数据',
  }))).filter((item) => enabled(item.raw))
}

export function getDataDictionaryOptions(dictionaryCode) {
  const dictionaries = state().dataDictionaries.filter(enabled)
  const selected = dictionaryCode
    ? dictionaries.filter((item) => [item.id, item.code, item.name].map(String).includes(String(dictionaryCode)))
    : dictionaries
  return selected.map((item) => option(item, '数据字典', {
    sourceModule: 'ERP主数据',
    values: String(item.values || '').split(',').map((value) => value.trim()).filter(Boolean),
  }))
}

export function getCodingRuleOptions() {
  return state().codingRules.filter(enabled).map((item) => option(item, '编码规则', { sourceModule: 'ERP主数据' }))
}

export function getSystemParameterValue(key) {
  return state().systemParameters.find((item) => String(item.key) === String(key) && enabled(item))?.value ?? null
}

export function getPermissionPointOptions() {
  return state().permissionPoints.filter(enabled).map((item) => option(item, '权限点', { sourceModule: '权限与日志' }))
}

export function getWarningRuleOptions(moduleId) {
  const rules = state().warningRules.filter(enabled)
  const selected = moduleId ? rules.filter((item) => [item.moduleId, item.module, item.target].filter(Boolean).map(String).includes(String(moduleId))) : rules
  return selected.map((item) => option(item, '预警规则', { sourceModule: '预警引擎基础' }))
}

export function getWarningSubscriberOptions(ruleId) {
  const subscribers = state().warningSubscribers.filter(enabled)
  const selected = ruleId ? subscribers.filter((item) => [item.ruleId, item.scope].filter(Boolean).map(String).includes(String(ruleId))) : subscribers
  return selected.map((item) => option(item, '预警订阅人', { sourceModule: '预警引擎基础' }))
}

export function getEnabledMaterials() { return getMaterialOptions().filter((item) => enabled(item.raw)) }
export function getEnabledCustomers() { return getCustomerOptions().filter((item) => enabled(item.raw)) }
export function getEnabledSuppliers() { return getSupplierOptions().filter((item) => enabled(item.raw)) }
export function getEnabledWarehouses() { return getWarehouseOptions().filter((item) => enabled(item.raw)) }
export function getEnabledWorkCenters() { return getWorkCenterOptions().filter((item) => enabled(item.raw)) }

export function findMaterialByCode(code) { return byCode(state().materials, code) }
export function findCustomerByCode(code) { return byCode(state().customers, code) }
export function findSupplierByCode(code) { return byCode(state().suppliers, code) }
export function findWarehouseByCode(code) { return byCode(state().warehouses, code) }
export function findEmployeeByCode(code) { return byCode(state().employees, code, ['employeeNo', 'code']) }

export function validateMaterialExists(materialId) { return exists(state().materials, materialId) }
export function validateCustomerExists(customerId) { return exists(state().customers, customerId) }
export function validateSupplierExists(supplierId) { return exists(state().suppliers, supplierId) }
export function validateWarehouseExists(warehouseId) { return exists(state().warehouses, warehouseId) }
export function validateLocationExists(locationId) { return getLocationOptions().some((location) => String(location.id) === String(locationId)) }
export function validateEmployeeExists(employeeId) { return exists(state().employees, employeeId) }
export function validateWorkCenterExists(workCenterId) { return exists(state().workCenters, workCenterId) }

export function getSupplierMaterialPriceOptions() {
  return (state().supplierMaterialPrices || []).map((item) => option(item, '供应商物料价格', {
    code: item.supplierMaterialCode || item.id,
    name: statusName(item, `${item.supplierMaterialCode || item.id} / ${item.price || 0} ${item.currency || 'CNY'}`),
    sourceModule: 'ERP供应商物料价格',
  }))
}

export function getPricesByMaterial(materialId) {
  return clone((state().supplierMaterialPrices || []).filter((item) => String(item.materialId) === String(materialId) && enabled(item)))
}

export function getPricesBySupplier(supplierId) {
  return clone((state().supplierMaterialPrices || []).filter((item) => String(item.supplierId) === String(supplierId) && enabled(item)))
}

export function getDefaultPrice(materialId, supplierId) {
  const prices = (state().supplierMaterialPrices || []).filter((item) => (
    String(item.materialId) === String(materialId)
    && (!supplierId || String(item.supplierId) === String(supplierId))
    && enabled(item)
  ))
  return clone(prices.find((item) => item.isDefault) || prices[0] || null)
}

export function getRecommendedSuppliers(materialId) {
  const suppliers = getEnabledSuppliers()
  return (state().materialSupplierRelations || [])
    .filter((item) => String(item.materialId) === String(materialId) && enabled(item))
    .sort((a, b) => Number(a.priority || 99) - Number(b.priority || 99))
    .map((relation) => ({
      ...relation,
      supplier: suppliers.find((supplier) => String(supplier.id) === String(relation.supplierId)) || null,
    }))
    .filter((relation) => relation.supplier)
}

export function getPrimarySupplierByMaterial(materialId) {
  const suppliers = getRecommendedSuppliers(materialId)
  return clone(suppliers.find((item) => item.isPrimary) || suppliers[0] || null)
}

export function getProcessOptions() {
  return (state().processes || []).filter(enabled).map((item) => option(item, '工序', {
    code: item.processCode || item.id,
    name: item.processName || item.name || item.id,
    sourceModule: 'MES工序基础资料',
  }))
}

export function getProcessesByIndustry(industryType) {
  return clone((state().processes || []).filter((item) => enabled(item) && (!industryType || item.industryType === industryType)))
}

export function getRoutingOptions() {
  return (state().routings || []).filter(enabled).map((item) => option(item, '工艺路线', {
    code: item.routingCode || item.id,
    name: item.routingName || item.name || item.id,
    sourceModule: 'MES工艺路线',
  }))
}

export function getRoutingSteps(routingId) {
  return clone((state().routingSteps || []).filter((item) => String(item.routingId) === String(routingId)).sort((a, b) => Number(a.stepNo || 0) - Number(b.stepNo || 0)))
}

export function getRoutingsByIndustry(industryType) {
  return clone((state().routings || []).filter((item) => enabled(item) && (!industryType || item.industryType === industryType)))
}

export function getEquipmentOptions() {
  return (state().equipment || []).filter(enabled).map((item) => option(item, '设备', {
    code: item.equipmentCode || item.id,
    name: item.equipmentName || item.name || item.id,
    sourceModule: 'MES设备基础资料',
  }))
}

export function getEquipmentByWorkCenter(workCenterId) {
  return clone((state().equipment || []).filter((item) => enabled(item) && String(item.workCenterId) === String(workCenterId)))
}

export function getProductCategoryOptions() {
  return (state().productCategories || []).filter(enabled).map((item) => option(item, '产品类别', {
    code: item.categoryCode || item.id,
    name: item.categoryName || item.name || item.id,
    sourceModule: 'ERP产品类别',
  }))
}

export function getProductCategoriesByIndustry(industryType) {
  return clone((state().productCategories || []).filter((item) => enabled(item) && (!industryType || item.industryType === industryType)))
}

