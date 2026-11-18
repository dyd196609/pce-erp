export const PDE_MANUFACTURING_OUTPUT_REGISTRY_VERSION = 'V1.14.2.8.4.10.2'

const relationship = ({
  relationshipCode,
  sourceObject,
  targetModule,
  targetObject,
  relationshipType,
  fields,
  protection,
}) => Object.freeze({
  relationshipCode,
  sourceModule: 'PDE',
  sourceObject,
  targetModule,
  targetObject,
  relationshipType,
  fields: Object.freeze(fields),
  protection,
  status: 'active',
})

export const pdeManufacturingOutputRegistry = Object.freeze([
  relationship({
    relationshipCode: 'PDE_MFG_OUTPUT_PRODUCT_VERSION',
    sourceObject: 'ProductManufacturingOutput', targetModule: 'PDE', targetObject: 'ProductVersion',
    relationshipType: 'version_reference', fields: ['product', 'productVersion', 'effectiveDate'],
    protection: '失效版本禁止输出',
  }),
  relationship({
    relationshipCode: 'PDE_MFG_OUTPUT_BOM_VERSION',
    sourceObject: 'ProductManufacturingOutput', targetModule: 'PDE', targetObject: 'BOMVersion',
    relationshipType: 'version_reference', fields: ['bomVersion', 'effectiveDate'],
    protection: 'BOM必须存在且已发布',
  }),
  relationship({
    relationshipCode: 'PDE_BOM_EMD_MATERIAL',
    sourceObject: 'BOMVersion', targetModule: 'EMD', targetObject: 'MaterialMaster',
    relationshipType: 'read_only_reference', fields: ['materialCode', 'specification', 'quantity', 'unit'],
    protection: '物料所有权属于EMD',
  }),
  relationship({
    relationshipCode: 'PDE_ROUTING_EMD_WORK_CENTER',
    sourceObject: 'RoutingVersion', targetModule: 'EMD', targetObject: 'WorkCenterMaster',
    relationshipType: 'read_only_reference', fields: ['operation', 'workCenter', 'standardHours', 'routingVersion'],
    protection: '工作中心所有权属于EMD',
  }),
  relationship({
    relationshipCode: 'PDE_BOM_MRP_MATERIAL_REQUIREMENT_INPUT',
    sourceObject: 'BOMVersion', targetModule: 'MRP', targetObject: 'MaterialRequirementInput',
    relationshipType: 'manufacturing_input', fields: ['materialCode', 'quantity', 'unit', 'bomVersion', 'effectiveDate'],
    protection: '只提供输入，不执行MRP计算',
  }),
  relationship({
    relationshipCode: 'PDE_BOM_SHORTAGE_SCM_PURCHASE_REQUIREMENT_BASIS',
    sourceObject: 'BOMVersion', targetModule: 'SCM', targetObject: 'PurchaseRequirementBasis',
    relationshipType: 'read_only_basis', fields: ['materialCode', 'specification', 'quantity', 'version', 'requiredDate'],
    protection: 'PDE不得创建采购申请或采购订单',
  }),
  relationship({
    relationshipCode: 'PDE_ROUTING_MES_MANUFACTURING_PREPARATION',
    sourceObject: 'RoutingVersion', targetModule: 'MES', targetObject: 'ManufacturingPreparationInput',
    relationshipType: 'manufacturing_input', fields: ['operation', 'workCenter', 'standardHours', 'routingVersion'],
    protection: '只提供制造准备输入，不执行生产',
  }),
])

export const manufacturingInputReferences = Object.freeze([
  Object.freeze({ sourceModule: 'PDE', targetModule: 'MRP', sourceObject: 'BOMVersion', targetObject: 'MaterialRequirementInput', referenceStatus: 'active' }),
  Object.freeze({ sourceModule: 'PDE', targetModule: 'SCM', sourceObject: 'BOMVersion', targetObject: 'PurchaseRequirementBasis', referenceStatus: 'active' }),
])

export function listPdeManufacturingOutputRelationships() {
  return pdeManufacturingOutputRegistry.map(item => ({ ...item, fields: [...item.fields] }))
}
