export const CREATE_FORMAL_PRICE_APPROVAL_COMMAND_MODEL_VERSION = 'V1.14.2.8.6.9'

export const CREATE_FORMAL_PRICE_APPROVAL_COMMAND_STATES = Object.freeze([
  Object.freeze({ code: 'not_requested', currentEnabled: true }),
  Object.freeze({ code: 'submitted', currentEnabled: true }),
  Object.freeze({ code: 'validated', currentEnabled: true }),
  Object.freeze({ code: 'rejected', currentEnabled: true }),
  Object.freeze({ code: 'approved_for_execution', currentEnabled: false }),
  Object.freeze({ code: 'executed', currentEnabled: false }),
])

export const CREATE_FORMAL_PRICE_APPROVAL_COMMAND = Object.freeze({
  commandCode: 'SCM_CREATE_FORMAL_PRICE_APPROVAL_COMMAND',
  version: CREATE_FORMAL_PRICE_APPROVAL_COMMAND_MODEL_VERSION,
  commandKind: 'DESIGN_ONLY',
  triggerMode: 'manual_only',
  fields: Object.freeze([
    'commandNo',
    'inquiryNo',
    'requestedBy',
    'requestedAt',
    'simulationStatus',
    'commandStatus',
  ]),
  lifecycle: Object.freeze(CREATE_FORMAL_PRICE_APPROVAL_COMMAND_STATES.map((item) => item.code)),
  closedStates: Object.freeze(['approved_for_execution', 'executed']),
  commandInstanceCount: 0,
  dispatcherConnected: false,
  automaticExecution: false,
  businessWriteCount: 0,
  productionDataWritten: false,
})

export function validateCreateFormalPriceApprovalCommand(model = CREATE_FORMAL_PRICE_APPROVAL_COMMAND) {
  const valid = model.commandCode === 'SCM_CREATE_FORMAL_PRICE_APPROVAL_COMMAND'
    && model.commandKind === 'DESIGN_ONLY'
    && model.triggerMode === 'manual_only'
    && model.lifecycle.join(',') === 'not_requested,submitted,validated,rejected,approved_for_execution,executed'
    && model.closedStates.join(',') === 'approved_for_execution,executed'
    && model.commandInstanceCount === 0
    && model.dispatcherConnected === false
    && model.automaticExecution === false
    && model.businessWriteCount === 0
    && model.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
