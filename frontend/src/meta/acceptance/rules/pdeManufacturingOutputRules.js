export const PDE_MANUFACTURING_OUTPUT_RULESET_VERSION = 'PCE-PDE-MANUFACTURING-OUTPUT-V102'

export const pdeManufacturingOutputRules = Object.freeze([
  Object.freeze({ ruleId: 'PDE-MFG-001', title: 'BOM必须存在' }),
  Object.freeze({ ruleId: 'PDE-MFG-002', title: 'BOM物料必须来自EMD' }),
  Object.freeze({ ruleId: 'PDE-MFG-003', title: '工艺路线必须引用EMD工作中心' }),
  Object.freeze({ ruleId: 'PDE-MFG-004', title: '失效版本禁止输出' }),
  Object.freeze({ ruleId: 'PDE-MFG-005', title: 'PDE不得直接生成采购订单' }),
  Object.freeze({ ruleId: 'PDE-MFG-006', title: 'SCM冻结流程Hash不得变化' }),
])

function result(ruleId, passed, evidence) {
  return {
    ruleId,
    title: pdeManufacturingOutputRules.find(rule => rule.ruleId === ruleId)?.title || '',
    status: passed ? 'PASS' : 'FAIL',
    evidence,
  }
}

export function evaluatePdeManufacturingOutputRules({ canary, relationships, modelSource, scmBaseline }) {
  const relationshipByCode = new Map((relationships || []).map(item => [item.relationshipCode, item]))
  const productVersion = new Map(canary.productVersions.map(item => [item.versionId, item]))
  const bomVersion = new Map(canary.boms.map(item => [item.bomId, item]))
  const routingVersion = new Map(canary.routings.map(item => [item.routingId, item]))
  return [
    result(
      'PDE-MFG-001',
      canary.manufacturingOutputs.every(output => bomVersion.has(output.bomId)),
      { outputCount: canary.manufacturingOutputs.length, bomCount: canary.boms.length },
    ),
    result(
      'PDE-MFG-002',
      canary.materials.length === 100
        && canary.materials.every(material => material.ownerModule === 'EMD')
        && relationshipByCode.get('PDE_BOM_EMD_MATERIAL')?.targetModule === 'EMD',
      { materialCount: canary.materials.length, ownerModule: 'EMD' },
    ),
    result(
      'PDE-MFG-003',
      canary.routings.every(routing => routing.workCenterSource === 'EMD')
        && relationshipByCode.get('PDE_ROUTING_EMD_WORK_CENTER')?.targetObject === 'WorkCenterMaster',
      { routingCount: canary.routings.length, workCenterSource: 'EMD' },
    ),
    result(
      'PDE-MFG-004',
      canary.manufacturingOutputs.every(output => (
        productVersion.get(output.productVersionId)?.status === 'released'
          && bomVersion.get(output.bomId)?.status === 'released'
          && routingVersion.get(output.routingId)?.status === 'released'
      ))
        && modelSource.includes('失效或未发布版本禁止输出至制造'),
      { obsoleteOutputCount: canary.manufacturingOutputs.filter(output => output.obsoleteVersionSelected).length },
    ),
    result(
      'PDE-MFG-005',
      relationshipByCode.get('PDE_BOM_SHORTAGE_SCM_PURCHASE_REQUIREMENT_BASIS')?.relationshipType === 'read_only_basis'
        && !modelSource.includes('PurchaseOrder.objects.create')
        && !modelSource.includes('PurchaseRequest.objects.create'),
      { scmRelationship: 'read_only_basis', purchaseOrderWrites: 0 },
    ),
    result(
      'PDE-MFG-006',
      scmBaseline?.unchanged === true,
      { checkpointId: scmBaseline?.checkpointId, hashes: scmBaseline?.current },
    ),
  ]
}
