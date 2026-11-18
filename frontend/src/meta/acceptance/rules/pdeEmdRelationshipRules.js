export const PDE_EMD_RELATIONSHIP_RULESET_VERSION = 'PCE-PDE-EMD-RELATIONSHIP-V410'

export const pdeEmdRelationshipRules = Object.freeze([
  Object.freeze({ ruleId: 'PDE-EMD-001', title: 'BOM必须引用EMD物料' }),
  Object.freeze({ ruleId: 'PDE-EMD-002', title: '工艺路线必须引用EMD工作中心' }),
  Object.freeze({ ruleId: 'PDE-EMD-003', title: '禁止PDE创建重复物料' }),
  Object.freeze({ ruleId: 'PDE-EMD-004', title: '工程资料必须关联产品' }),
  Object.freeze({ ruleId: 'PDE-EMD-005', title: 'PDE数据不得修改SCM冻结对象' }),
])

function result(ruleId, passed, evidence) {
  return {
    ruleId,
    title: pdeEmdRelationshipRules.find(rule => rule.ruleId === ruleId)?.title || '',
    status: passed ? 'PASS' : 'FAIL',
    evidence,
  }
}

export function evaluatePdeEmdRelationshipRules({
  relationships,
  pdeModelSource,
  canary,
  frozenBaselinesUnchanged,
}) {
  const codes = new Set(relationships.map(item => item.relationshipCode))
  return [
    result(
      'PDE-EMD-001',
      codes.has('PDE_BOM_MATERIAL')
        && /class ProductBOM[\s\S]*emd_material_code/.test(pdeModelSource)
        && canary.boms.every(bom => bom.materialReferences.every(reference => reference.emdMaterialCode)),
      {
        relationshipCode: 'PDE_BOM_MATERIAL',
        bomCount: canary.boms.length,
        materialReferenceCount: canary.materialReferences.length,
      },
    ),
    result(
      'PDE-EMD-002',
      codes.has('PDE_ROUTING_WORK_CENTER')
        && /class Routing[\s\S]*emd_work_center_code/.test(pdeModelSource)
        && canary.routings.every(routing => routing.emdWorkCenterCode),
      {
        relationshipCode: 'PDE_ROUTING_WORK_CENTER',
        routingCount: canary.routings.length,
        workCenterCount: canary.workCenters.length,
      },
    ),
    result(
      'PDE-EMD-003',
      !/class\s+Material\s*\(/.test(pdeModelSource)
        && canary.materialReferences.every(reference => reference.ownerModule === 'EMD'),
      {
        pdeMaterialModelPresent: /class\s+Material\s*\(/.test(pdeModelSource),
        materialOwnerModules: [...new Set(canary.materialReferences.map(item => item.ownerModule))],
      },
    ),
    result(
      'PDE-EMD-004',
      [
        'PDE_ENGINEERING_DOCUMENT_PRODUCT',
        'PDE_ENGINEERING_DOCUMENT_BOM',
        'PDE_ENGINEERING_DOCUMENT_ROUTING',
      ].every(code => codes.has(code))
        && /class EngineeringDocument[\s\S]*product\s*=\s*models\.ForeignKey/.test(pdeModelSource)
        && /class EngineeringDocument[\s\S]*product_bom\s*=\s*models\.ForeignKey/.test(pdeModelSource)
        && /class EngineeringDocument[\s\S]*routing\s*=\s*models\.ForeignKey/.test(pdeModelSource)
        && canary.engineeringDocuments.every(document => (
          document.productCode && document.bomCode && document.routingCode
        )),
      {
        engineeringDocumentCount: canary.engineeringDocuments.length,
        requiredAssociations: ['ProductDefinition', 'ProductBOM', 'Routing'],
      },
    ),
    result(
      'PDE-EMD-005',
      frozenBaselinesUnchanged
        && relationships.every(item => !item.relationshipCode.startsWith('SCM_'))
        && relationships.every(item => item.sourceModule === 'PDE'),
      {
        frozenBaselinesUnchanged,
        relationshipSourceModules: [...new Set(relationships.map(item => item.sourceModule))],
      },
    ),
  ]
}

