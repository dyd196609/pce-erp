export const SCM_SUPPLIER_SETTLEMENT_BASELINE_RULESET_VERSION = 'PCE-SCM-SUPPLIER-SETTLEMENT-BASELINE-V863'

export const scmSupplierSettlementBaselineRules = Object.freeze([
  Object.freeze({
    ruleId: 'SCM-BASELINE-001',
    title: '关键对象变更必须检查SCM基线',
    requirement: '涉及Supplier、Material、PurchaseOrder、Settlement的后续修改必须检查SCM最终基线。',
  }),
  Object.freeze({
    ruleId: 'SCM-BASELINE-002',
    title: 'PDE不得修改供应商结算流程节点',
    requirement: 'PDE只能声明依赖，不得修改SCM供应商结算16节点。',
  }),
  Object.freeze({
    ruleId: 'SCM-BASELINE-003',
    title: '后续制造模块只能通过接口引用SCM',
    requirement: 'MRP、MES、WMS引用SCM时必须使用接口，不得复制供应商结算业务逻辑。',
  }),
])

const result = (ruleId, passed, evidence) => ({
  ruleId,
  status: passed ? 'PASS' : 'FAIL',
  title: scmSupplierSettlementBaselineRules
    .find(rule => rule.ruleId === ruleId)?.title || '',
  evidence,
})

export function evaluateScmSupplierSettlementBaselineRules(dependency = {}) {
  const protectedObjects = dependency.protectedObjects || []
  const consumers = dependency.downstreamConsumers || []
  const pde = consumers.find(consumer => consumer.moduleCode === 'PDE')
  const apiConsumers = consumers.filter(consumer => ['MRP', 'MES', 'WMS'].includes(consumer.moduleCode))
  return [
    result(
      'SCM-BASELINE-001',
      ['Supplier', 'Material', 'PurchaseOrder', 'Settlement']
        .every(objectName => protectedObjects.includes(objectName))
        && dependency.baselineCheckpoint === 'pce_scm_supplier_settlement_final_ready',
      {
        protectedObjects,
        baselineCheckpoint: dependency.baselineCheckpoint,
      },
    ),
    result(
      'SCM-BASELINE-002',
      pde?.integrationMode === 'dependency_reference' && pde?.mayModifyProcessNodes === false,
      { pde },
    ),
    result(
      'SCM-BASELINE-003',
      apiConsumers.length === 3
        && apiConsumers.every(consumer => (
          consumer.integrationMode === 'api_reference'
          && consumer.mayCopyBusinessLogic === false
        )),
      { consumers: apiConsumers },
    ),
  ]
}
