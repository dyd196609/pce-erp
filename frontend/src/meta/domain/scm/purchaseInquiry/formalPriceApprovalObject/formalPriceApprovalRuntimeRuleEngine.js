export const FORMAL_PRICE_APPROVAL_RUNTIME_RULE_ENGINE_VERSION = 'V1.14.2.8.6.7'

export const FORMAL_PRICE_APPROVAL_RUNTIME_RULES = Object.freeze([
  Object.freeze({ ruleCode: 'FORMAL-PRICE-RUNTIME-001', name: '只读投影可用性' }),
  Object.freeze({ ruleCode: 'FORMAL-PRICE-RUNTIME-002', name: '证据包完整性' }),
  Object.freeze({ ruleCode: 'FORMAL-PRICE-RUNTIME-003', name: '创建冻结状态' }),
  Object.freeze({ ruleCode: 'FORMAL-PRICE-RUNTIME-004', name: '审批流程隔离' }),
])

export function evaluateFormalPriceApprovalRuntimeReadiness(input = {}) {
  const projectionReady = input.projectionStatus === 'available'
  const evidenceReady = input.evidencePackageStatus === 'available'
  const freezeReady = input.creationAssessmentStatus === 'ready'
  const isolated = input.workflowEngineConnected !== true
  const readyForCreationDesign = projectionReady && evidenceReady && freezeReady && isolated
  return Object.freeze({
    result: readyForCreationDesign ? 'PASS' : 'FAIL',
    evaluatedState: readyForCreationDesign ? 'ready_for_creation' : 'definition_only',
    rules: Object.freeze([
      Object.freeze({ ruleCode: 'FORMAL-PRICE-RUNTIME-001', result: projectionReady ? 'PASS' : 'FAIL' }),
      Object.freeze({ ruleCode: 'FORMAL-PRICE-RUNTIME-002', result: evidenceReady ? 'PASS' : 'FAIL' }),
      Object.freeze({ ruleCode: 'FORMAL-PRICE-RUNTIME-003', result: freezeReady ? 'PASS' : 'FAIL' }),
      Object.freeze({ ruleCode: 'FORMAL-PRICE-RUNTIME-004', result: isolated ? 'PASS' : 'FAIL' }),
    ]),
    designOnly: true,
    stateChanged: false,
    automaticProgression: false,
    formalPriceApprovalObjectCreated: false,
    approvalWorkflowStarted: false,
    approvalTaskCreated: false,
    priceApproved: false,
    purchaseOrderCreated: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}
