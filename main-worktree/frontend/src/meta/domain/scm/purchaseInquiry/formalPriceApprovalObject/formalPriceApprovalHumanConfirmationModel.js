export const FORMAL_PRICE_APPROVAL_HUMAN_CONFIRMATION_MODEL_VERSION = 'V1.14.2.8.6.12'

export const FORMAL_PRICE_APPROVAL_HUMAN_CONFIRMATION_STATES = Object.freeze([
  'not_requested',
  'pending_confirmation',
  'confirmed_design_only',
  'rejected',
])

export const FORMAL_PRICE_APPROVAL_HUMAN_CONFIRMATION = Object.freeze({
  confirmationCode: 'SCM_FORMAL_PRICE_APPROVAL_HUMAN_CONFIRMATION',
  version: FORMAL_PRICE_APPROVAL_HUMAN_CONFIRMATION_MODEL_VERSION,
  confirmationKind: 'HUMAN_DESIGN_CONFIRMATION_ONLY',
  fields: Object.freeze([
    'confirmationNo',
    'sandboxNo',
    'confirmedBy',
    'confirmedAt',
    'confirmationStatus',
    'confirmationNote',
  ]),
  lifecycle: FORMAL_PRICE_APPROVAL_HUMAN_CONFIRMATION_STATES,
  humanConfirmationRequired: true,
  executionPermissionGranted: false,
  confirmationInstanceCount: 0,
  persistenceMode: 'none',
  businessWriteCount: 0,
  productionDataWritten: false,
})

export function validateFormalPriceApprovalHumanConfirmation(model = FORMAL_PRICE_APPROVAL_HUMAN_CONFIRMATION) {
  const valid = model.confirmationCode === 'SCM_FORMAL_PRICE_APPROVAL_HUMAN_CONFIRMATION'
    && model.confirmationKind === 'HUMAN_DESIGN_CONFIRMATION_ONLY'
    && model.lifecycle.join(',') === 'not_requested,pending_confirmation,confirmed_design_only,rejected'
    && model.humanConfirmationRequired === true
    && model.executionPermissionGranted === false
    && model.confirmationInstanceCount === 0
    && model.persistenceMode === 'none'
    && model.businessWriteCount === 0
    && model.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
