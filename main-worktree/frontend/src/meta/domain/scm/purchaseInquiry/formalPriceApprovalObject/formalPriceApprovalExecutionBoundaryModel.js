export const FORMAL_PRICE_APPROVAL_EXECUTION_BOUNDARY_MODEL_VERSION = 'V1.14.2.8.6.14'

export const FORMAL_PRICE_APPROVAL_EXECUTION_BOUNDARY_STATES = Object.freeze([
  'not_evaluated',
  'context_checking',
  'boundary_ready',
  'blocked',
  'manual_review',
])

export const FORMAL_PRICE_APPROVAL_EXECUTION_BOUNDARY = Object.freeze({
  boundaryCode: 'SCM_FORMAL_PRICE_APPROVAL_EXECUTION_BOUNDARY',
  version: FORMAL_PRICE_APPROVAL_EXECUTION_BOUNDARY_MODEL_VERSION,
  boundaryKind: 'UNIQUE_FUTURE_EXECUTION_ENTRY_DESIGN',
  fields: Object.freeze([
    'boundaryNo',
    'inquiryNo',
    'agreementNo',
    'executionContextNo',
    'boundaryStatus',
    'findings',
    'blockedReasons',
  ]),
  lifecycle: FORMAL_PRICE_APPROVAL_EXECUTION_BOUNDARY_STATES,
  uniqueFutureExecutionBoundary: true,
  executorConnected: false,
  productionExecution: false,
  boundaryInstanceCount: 0,
  persistenceMode: 'none',
  businessWriteCount: 0,
  productionDataWritten: false,
})

export function validateFormalPriceApprovalExecutionBoundary(model = FORMAL_PRICE_APPROVAL_EXECUTION_BOUNDARY) {
  const valid = model.boundaryCode === 'SCM_FORMAL_PRICE_APPROVAL_EXECUTION_BOUNDARY'
    && model.boundaryKind === 'UNIQUE_FUTURE_EXECUTION_ENTRY_DESIGN'
    && model.lifecycle.join(',') === 'not_evaluated,context_checking,boundary_ready,blocked,manual_review'
    && model.uniqueFutureExecutionBoundary === true
    && model.executorConnected === false
    && model.productionExecution === false
    && model.boundaryInstanceCount === 0
    && model.persistenceMode === 'none'
    && model.businessWriteCount === 0
    && model.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
