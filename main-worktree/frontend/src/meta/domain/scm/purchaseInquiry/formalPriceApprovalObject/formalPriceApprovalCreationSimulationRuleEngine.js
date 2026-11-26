export const FORMAL_PRICE_APPROVAL_CREATION_SIMULATION_RULE_VERSION = 'V1.14.2.8.6.8'

export const FORMAL_PRICE_APPROVAL_CREATION_SIMULATION_RULES = Object.freeze([
  Object.freeze({ ruleCode: 'FORMAL-PRICE-SIM-001', name: '正式对象运行就绪检查' }),
  Object.freeze({ ruleCode: 'FORMAL-PRICE-SIM-002', name: '只读投影证据检查' }),
  Object.freeze({ ruleCode: 'FORMAL-PRICE-SIM-003', name: '证据包完整性检查' }),
  Object.freeze({ ruleCode: 'FORMAL-PRICE-SIM-004', name: '创建冻结评估检查' }),
  Object.freeze({ ruleCode: 'FORMAL-PRICE-SIM-005', name: '审批流程隔离检查' }),
])

export function evaluateFormalPriceApprovalCreationSimulationRules(input = {}) {
  const checks = Object.freeze([
    Object.freeze({ ruleCode: 'FORMAL-PRICE-SIM-001', pass: input.runtimeEvaluatedStatus === 'ready_for_creation' }),
    Object.freeze({ ruleCode: 'FORMAL-PRICE-SIM-002', pass: input.projectionStatus === 'available' }),
    Object.freeze({ ruleCode: 'FORMAL-PRICE-SIM-003', pass: input.evidencePackageStatus === 'available' }),
    Object.freeze({ ruleCode: 'FORMAL-PRICE-SIM-004', pass: input.creationAssessmentStatus === 'ready' }),
    Object.freeze({ ruleCode: 'FORMAL-PRICE-SIM-005', pass: input.workflowEngineConnected !== true }),
  ])
  const allowed = checks.every((item) => item.pass)
  return Object.freeze({
    result: allowed ? 'PASS' : 'FAIL',
    decision: allowed ? 'simulate_only' : 'blocked',
    simulatedStatus: allowed ? 'simulated_ready' : 'blocked',
    checks: Object.freeze(checks.map((item) => Object.freeze({ ruleCode: item.ruleCode, result: item.pass ? 'PASS' : 'FAIL' }))),
    simulationOnly: true,
    formalPriceApprovalObjectCreated: false,
    approvalWorkflowStarted: false,
    approvalTaskCreated: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}
