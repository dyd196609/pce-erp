export const FORMAL_PRICE_APPROVAL_OPERATION_READINESS_VERSION = 'V1.14.2.8.6.25'

export const FORMAL_PRICE_APPROVAL_OPERATION_READINESS = Object.freeze({
  readinessCode: 'SCM_FORMAL_PRICE_APPROVAL_OPERATION_READINESS',
  version: FORMAL_PRICE_APPROVAL_OPERATION_READINESS_VERSION,
  statuses: Object.freeze(['not_assessed', 'validation_ready', 'manual_review', 'blocked']),
  readinessStatus: 'validation_ready',
  validationMeansOperation: false,
  passMeansAutoRun: false,
  operationEnabled: false,
  autoRunEnabled: false,
  productionExecutionEnabled: false,
  operationCount: 0,
  executorConnected: false,
  persistenceAdapterConnected: false,
})

export function validateFormalPriceApprovalOperationReadiness(model = FORMAL_PRICE_APPROVAL_OPERATION_READINESS) {
  const valid = model.readinessCode === 'SCM_FORMAL_PRICE_APPROVAL_OPERATION_READINESS'
    && model.statuses.includes(model.readinessStatus) && model.readinessStatus === 'validation_ready'
    && model.validationMeansOperation === false && model.passMeansAutoRun === false
    && model.operationEnabled === false && model.autoRunEnabled === false && model.productionExecutionEnabled === false
    && model.operationCount === 0 && model.executorConnected === false && model.persistenceAdapterConnected === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
