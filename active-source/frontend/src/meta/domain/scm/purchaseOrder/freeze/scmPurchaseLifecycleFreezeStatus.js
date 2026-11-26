export const SCM_PURCHASE_LIFECYCLE_FREEZE_STATUS_VERSION = 'V1.14.2.8.5.11'
export const SCM_PURCHASE_LIFECYCLE_FREEZE_STATUS_CODE = 'SCM_PURCHASE_LIFECYCLE_FREEZE_STATUS'

export const SCM_PURCHASE_LIFECYCLE_FREEZE_STATUS = Object.freeze({
  definitionCode: SCM_PURCHASE_LIFECYCLE_FREEZE_STATUS_CODE,
  status: 'FROZEN',
  activationStatus: 'READY',
  mode: 'read_only',
  allowedTransitions: Object.freeze([]),
  modelMutationAllowed: false,
  businessExecutionAllowed: false,
  automaticGenerationAllowed: false,
  businessWriteCount: 0,
  productionDataWritten: false,
})

export function validateScmPurchaseLifecycleFreezeStatus(status = SCM_PURCHASE_LIFECYCLE_FREEZE_STATUS) {
  const valid = status?.status === 'FROZEN'
    && status?.activationStatus === 'READY'
    && status?.mode === 'read_only'
    && status?.allowedTransitions?.length === 0
    && status?.modelMutationAllowed === false
    && status?.businessExecutionAllowed === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
