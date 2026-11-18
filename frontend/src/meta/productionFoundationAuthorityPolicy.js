export const PRODUCTION_FOUNDATION_AUTHORITY_VERSION = 'PCE-PRODUCTION-A1-V1.0'
export const FORMAL_FACT_STORAGE = 'server'
export const LOCAL_STORAGE_FORMAL_FACT_COUNT = 0

export const LEGACY_LOCAL_COLLECTIONS = Object.freeze([
  'materials', 'skills', 'shifts', 'workCenters', 'processes',
  'routings', 'routingSteps', 'equipment', 'productCategories',
])

export const PRODUCTION_OBJECT_AUTHORITIES = Object.freeze({
  Material: { currentOwner: 'masterdata.Material', futureOwner: 'masterdata.Material', compatibility: 'MaterialMasterRuntimeAdapter', legacyWriteAllowed: false },
  Product: { currentOwner: 'pde.ProductDefinition → masterdata.Material', futureOwner: 'pde.ProductDefinition', compatibility: 'emd_material_code只作兼容快照', legacyWriteAllowed: false },
  ProductCategory: { currentOwner: 'pde.ProductCategory', futureOwner: 'pde.ProductCategory', compatibility: 'localStorage只保留遗留演示快照', legacyWriteAllowed: false },
  BOM: { currentOwner: 'pde.ProductBOM/BOMVersion/BOMItem', futureOwner: 'pde.ProductBOM/BOMVersion/BOMItem', compatibility: '旧JSON/行模型已退出正式事实', legacyWriteAllowed: false },
  Routing: { currentOwner: 'pde.Routing/RoutingVersion/RoutingStep', futureOwner: 'pde.Routing/RoutingVersion/RoutingStep', compatibility: 'localStorage路线只保留遗留演示快照', legacyWriteAllowed: false },
  Operation: { currentOwner: 'system.Process', futureOwner: 'system.Process', compatibility: '复用现有工序对象并增加正式工作中心引用', legacyWriteAllowed: false },
  WorkCenter: { currentOwner: 'pde.WorkCenter', futureOwner: 'pde.WorkCenter', compatibility: 'localStorage工作中心只保留遗留演示快照', legacyWriteAllowed: false },
  Equipment: { currentOwner: 'pde.Equipment', futureOwner: 'pde.Equipment', compatibility: 'localStorage设备只保留遗留演示快照', legacyWriteAllowed: false },
  ProductionPlan: { currentOwner: 'planning.ProductionPlan', futureOwner: 'planning.ProductionPlan', compatibility: '保持销售/需求/采购计划链兼容', legacyWriteAllowed: false },
  ManufacturingOrder: { currentOwner: 'NOT_IMPLEMENTED', futureOwner: 'A3正式服务端对象', compatibility: '禁止以页面或localStorage对象代替', legacyWriteAllowed: false },
  WorkOrder: { currentOwner: 'NOT_IMPLEMENTED', futureOwner: 'A3正式服务端对象', compatibility: '禁止以页面或localStorage对象代替', legacyWriteAllowed: false },
  Inventory: { currentOwner: 'procurement.InventoryBalance/InventoryTransaction', futureOwner: '现有库存正式服务端对象', compatibility: 'A0-A4零库存业务写入', legacyWriteAllowed: false },
})

export function isLegacyLocalCollection(collection) {
  return LEGACY_LOCAL_COLLECTIONS.includes(String(collection || ''))
}

export function assertFormalProductionWriteAllowed(collection) {
  if (!isLegacyLocalCollection(collection)) return true
  throw new Error(`${collection} 已退出 localStorage 正式事实；请通过正式服务端业务入口维护。`)
}
