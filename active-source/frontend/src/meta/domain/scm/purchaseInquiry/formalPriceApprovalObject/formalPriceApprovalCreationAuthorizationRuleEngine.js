export const FORMAL_PRICE_APPROVAL_CREATION_AUTHORIZATION_RULE_VERSION = 'V1.14.2.8.6.10'

export const FORMAL_PRICE_APPROVAL_CREATION_AUTHORIZATION_RULES = Object.freeze([
  Object.freeze({ ruleCode: 'FORMAL-PRICE-AUTH-001', name: '命令校验状态检查' }),
  Object.freeze({ ruleCode: 'FORMAL-PRICE-AUTH-002', name: '请求人身份检查' }),
  Object.freeze({ ruleCode: 'FORMAL-PRICE-AUTH-003', name: '授权人身份检查' }),
  Object.freeze({ ruleCode: 'FORMAL-PRICE-AUTH-004', name: '请求人与授权人职责分离' }),
  Object.freeze({ ruleCode: 'FORMAL-PRICE-AUTH-005', name: '人工授权模式检查' }),
])

export function evaluateFormalPriceApprovalCreationAuthorization(input = {}) {
  const requesterId = typeof input.requesterId === 'string' ? input.requesterId.trim() : ''
  const authorizerId = typeof input.authorizerId === 'string' ? input.authorizerId.trim() : ''
  const checks = Object.freeze([
    Object.freeze({ ruleCode: 'FORMAL-PRICE-AUTH-001', pass: input.commandStatus === 'validated' }),
    Object.freeze({ ruleCode: 'FORMAL-PRICE-AUTH-002', pass: requesterId.length > 0 }),
    Object.freeze({ ruleCode: 'FORMAL-PRICE-AUTH-003', pass: authorizerId.length > 0 }),
    Object.freeze({ ruleCode: 'FORMAL-PRICE-AUTH-004', pass: requesterId.length > 0 && authorizerId.length > 0 && requesterId !== authorizerId }),
    Object.freeze({ ruleCode: 'FORMAL-PRICE-AUTH-005', pass: input.authorizationMode === 'manual' }),
  ])
  const authorizedDesignOnly = checks.every((item) => item.pass)
  return Object.freeze({
    result: authorizedDesignOnly ? 'PASS' : 'FAIL',
    decision: authorizedDesignOnly ? 'authorized_design_only' : 'rejected',
    evaluatedStatus: authorizedDesignOnly ? 'authorized_design_only' : 'rejected',
    checks: Object.freeze(checks.map((item) => Object.freeze({ ruleCode: item.ruleCode, result: item.pass ? 'PASS' : 'FAIL' }))),
    requesterAuthorizerSeparated: requesterId.length > 0 && authorizerId.length > 0 && requesterId !== authorizerId,
    authorizationInstanceCreated: false,
    executionPermissionGranted: false,
    commandExecuted: false,
    formalPriceApprovalObjectCreated: false,
    approvalWorkflowStarted: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}
