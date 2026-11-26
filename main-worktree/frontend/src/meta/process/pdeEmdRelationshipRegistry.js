export const PDE_EMD_RELATIONSHIP_REGISTRY_VERSION = 'V1.14.2.8.4.10'

const relationship = (
  relationshipCode,
  sourceObject,
  targetModule,
  targetObject,
  relationshipType = 'reference',
) => Object.freeze({
  relationshipCode,
  sourceModule: 'PDE',
  sourceObject,
  targetModule,
  targetObject,
  relationshipType,
  status: 'active',
})

export const pdeEmdRelationshipRegistry = Object.freeze([
  relationship('PDE_PRODUCT_DEFINITION_MATERIAL', 'ProductDefinition', 'EMD', 'MaterialMaster'),
  relationship('PDE_BOM_MATERIAL', 'ProductBOM', 'EMD', 'MaterialMaster'),
  relationship('PDE_ROUTING_WORK_CENTER', 'Routing', 'EMD', 'WorkCenterMaster'),
  relationship('PDE_ENGINEERING_DOCUMENT_PRODUCT', 'EngineeringDocument', 'PDE', 'ProductDefinition', 'association'),
  relationship('PDE_ENGINEERING_DOCUMENT_BOM', 'EngineeringDocument', 'PDE', 'ProductBOM', 'association'),
  relationship('PDE_ENGINEERING_DOCUMENT_ROUTING', 'EngineeringDocument', 'PDE', 'Routing', 'association'),
  relationship('PDE_MASS_PRODUCTION_PRODUCT', 'MassProductionIntroduction', 'PDE', 'ProductDefinition', 'association'),
  relationship('PDE_MASS_PRODUCTION_BOM', 'MassProductionIntroduction', 'PDE', 'ProductBOM', 'association'),
  relationship('PDE_MASS_PRODUCTION_ROUTING', 'MassProductionIntroduction', 'PDE', 'Routing', 'association'),
  relationship('PDE_MASS_PRODUCTION_RESOURCE', 'MassProductionIntroduction', 'EMD', 'ProductionResourceMaster'),
])

export function listPdeEmdRelationships() {
  return pdeEmdRelationshipRegistry.map(item => ({ ...item }))
}

export function findPdeEmdRelationship(relationshipCode = '') {
  return pdeEmdRelationshipRegistry.find(
    item => item.relationshipCode === String(relationshipCode),
  ) || null
}

