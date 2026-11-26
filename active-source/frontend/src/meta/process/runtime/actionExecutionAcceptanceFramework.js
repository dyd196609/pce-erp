export const ACTION_EXECUTION_ACCEPTANCE_FRAMEWORK_VERSION = 'V1.14.2.8.18.5'

export function evaluateActionExecutionAcceptance(execution = {}) {
  const checks = Object.freeze({
    button: Boolean(execution.buttonCode),
    actionContract: Boolean(execution.actionCode && execution.contractCode && execution.contractAllowed),
    router: Boolean(execution.route),
    targetPage: Boolean(execution.targetPageCode && execution.targetPageName),
    runtimeContext: Boolean(execution.contextId && execution.objectType && execution.objectId),
  })
  const valid = Object.values(checks).every(Boolean)
  return Object.freeze({ frameworkVersion: ACTION_EXECUTION_ACCEPTANCE_FRAMEWORK_VERSION,
    result: valid ? 'PASS' : 'FAIL', valid, checks, chain: Object.freeze([
      'Button', 'Action Contract', 'Router', 'Target Page', 'Runtime Context',
    ]) })
}
