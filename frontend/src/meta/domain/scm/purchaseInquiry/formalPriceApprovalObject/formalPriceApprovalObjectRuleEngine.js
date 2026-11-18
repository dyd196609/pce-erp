export const FORMAL_PRICE_APPROVAL_OBJECT_RULE_ENGINE_VERSION = 'V1.14.2.8.6.6'

export const FORMAL_PRICE_APPROVAL_OBJECT_RULES = Object.freeze([
  Object.freeze({ ruleCode: 'FORMAL-PRICE-OBJECT-001', name: '只读投影检查' }),
  Object.freeze({ ruleCode: 'FORMAL-PRICE-OBJECT-002', name: '审批前证据包检查' }),
  Object.freeze({ ruleCode: 'FORMAL-PRICE-OBJECT-003', name: '创建冻结评估检查' }),
  Object.freeze({ ruleCode: 'FORMAL-PRICE-OBJECT-004', name: '对象创建边界检查' }),
])

export function evaluateFormalPriceApprovalObjectDefinition(input = {}) {
  const projectionReady = input.projectionStatus === 'available'
  const evidenceReady = input.evidencePackageStatus === 'available'
  const freezeReady = input.creationAssessmentStatus === 'ready'
  const readyForCreation = projectionReady && evidenceReady && freezeReady
  const modelState = readyForCreation ? 'ready_for_creation' : 'definition_only'
  const rules = Object.freeze([
    Object.freeze({ ruleCode: 'FORMAL-PRICE-OBJECT-001', result: projectionReady ? 'PASS' : 'FAIL' }),
    Object.freeze({ ruleCode: 'FORMAL-PRICE-OBJECT-002', result: evidenceReady ? 'PASS' : 'FAIL' }),
    Object.freeze({ ruleCode: 'FORMAL-PRICE-OBJECT-003', result: freezeReady ? 'PASS' : 'FAIL' }),
    Object.freeze({ ruleCode: 'FORMAL-PRICE-OBJECT-004', result: 'PASS', instanceCreationAllowed: false }),
  ])
  return Object.freeze({
    result: readyForCreation ? 'READY_FOR_CREATION' : 'DEFINITION_ONLY',
    modelState,
    rules,
    readyForCreation,
    designOnly: true,
    formalPriceApprovalObjectCreated: false,
    approvalWorkflowStarted: false,
    approvalSubmitted: false,
    priceApproved: false,
    purchaseOrderCreated: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}
