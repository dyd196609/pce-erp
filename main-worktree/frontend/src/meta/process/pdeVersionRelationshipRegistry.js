export const PDE_VERSION_RELATIONSHIP_REGISTRY_VERSION = 'V1.14.2.8.4.10.1'

const edge = (relationshipCode, sourceObject, targetObject, relationshipType) => Object.freeze({
  relationshipCode,
  moduleCode: 'PDE',
  sourceObject,
  targetObject,
  relationshipType,
  status: 'active',
})

export const pdeVersionRelationshipRegistry = Object.freeze([
  edge('PDE_PRODUCT_PRODUCT_VERSION', 'ProductDefinition', 'ProductVersion', '1:N'),
  edge('PDE_PRODUCT_VERSION_BOM_VERSION', 'ProductVersion', 'BOMVersion', '1:N'),
  edge('PDE_PRODUCT_VERSION_ROUTING_VERSION', 'ProductVersion', 'RoutingVersion', '1:N'),
  edge('PDE_PRODUCT_VERSION_DOCUMENT_VERSION', 'ProductVersion', 'EngineeringDocumentVersion', '1:N'),
  edge('PDE_EFFECTIVE_PRODUCT_VERSION', 'EffectiveDateControl', 'ProductVersion', 'effective_reference'),
  edge('PDE_EFFECTIVE_BOM_VERSION', 'EffectiveDateControl', 'BOMVersion', 'effective_reference'),
  edge('PDE_EFFECTIVE_ROUTING_VERSION', 'EffectiveDateControl', 'RoutingVersion', 'effective_reference'),
  edge('PDE_ECN_BEFORE_VERSION', 'EngineeringChangeNotice', 'ProductVersion', 'before_reference'),
  edge('PDE_ECN_AFTER_VERSION', 'EngineeringChangeNotice', 'ProductVersion', 'after_reference'),
])

export function listPdeVersionRelationships() {
  return pdeVersionRelationshipRegistry.map(item => ({ ...item }))
}

