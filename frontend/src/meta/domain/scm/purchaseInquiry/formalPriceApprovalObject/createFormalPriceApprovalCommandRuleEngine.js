export const CREATE_FORMAL_PRICE_APPROVAL_COMMAND_RULE_VERSION = 'V1.14.2.8.6.9'

export const CREATE_FORMAL_PRICE_APPROVAL_COMMAND_RULES = Object.freeze([
  Object.freeze({ ruleCode: 'FORMAL-PRICE-COMMAND-001', name: '人工触发检查' }),
  Object.freeze({ ruleCode: 'FORMAL-PRICE-COMMAND-002', name: '请求人证据检查' }),
  Object.freeze({ ruleCode: 'FORMAL-PRICE-COMMAND-003', name: '创建模拟完成检查' }),
  Object.freeze({ ruleCode: 'FORMAL-PRICE-COMMAND-004', name: '正式对象运行就绪检查' }),
])

export function evaluateCreateFormalPriceApprovalCommand(input = {}) {
  const checks = Object.freeze([
    Object.freeze({ ruleCode: 'FORMAL-PRICE-COMMAND-001', pass: input.triggerMode === 'manual' }),
    Object.freeze({ ruleCode: 'FORMAL-PRICE-COMMAND-002', pass: typeof input.requestedBy === 'string' && input.requestedBy.trim().length > 0 }),
    Object.freeze({ ruleCode: 'FORMAL-PRICE-COMMAND-003', pass: input.simulationStatus === 'completed' }),
    Object.freeze({ ruleCode: 'FORMAL-PRICE-COMMAND-004', pass: input.runtimeEvaluatedStatus === 'ready_for_creation' }),
  ])
  const validated = checks.every((item) => item.pass)
  return Object.freeze({
    result: validated ? 'PASS' : 'FAIL',
    decision: validated ? 'validated_design_only' : 'rejected',
    evaluatedStatus: validated ? 'validated' : 'rejected',
    checks: Object.freeze(checks.map((item) => Object.freeze({ ruleCode: item.ruleCode, result: item.pass ? 'PASS' : 'FAIL' }))),
    manualTriggerRecognized: input.triggerMode === 'manual',
    commandInstanceCreated: false,
    commandDispatched: false,
    approvedForExecution: false,
    executed: false,
    formalPriceApprovalObjectCreated: false,
    approvalWorkflowStarted: false,
    approvalTaskCreated: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}
