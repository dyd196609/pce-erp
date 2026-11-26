export const FORMAL_PRICE_APPROVAL_POST_CREATION_STATE_TAKEOVER_MODEL_VERSION = 'V1.14.2.8.6.16'

export const FORMAL_PRICE_APPROVAL_POST_CREATION_STATE_TAKEOVER_STATES = Object.freeze([
  'not_assessed',
  'awaiting_created_evidence',
  'takeover_ready',
  'isolated',
  'blocked',
  'manual_review',
])

export const FORMAL_PRICE_APPROVAL_POST_CREATION_STATE_TAKEOVER = Object.freeze({
  takeoverCode: 'SCM_FORMAL_PRICE_APPROVAL_POST_CREATION_STATE_TAKEOVER',
  version: FORMAL_PRICE_APPROVAL_POST_CREATION_STATE_TAKEOVER_MODEL_VERSION,
  takeoverKind: 'POST_CREATION_STATE_OWNERSHIP_DESIGN_ONLY',
  fields: Object.freeze(['takeoverNo', 'formalPriceApprovalNo', 'createdEvidenceRef', 'currentState', 'targetState', 'takeoverStatus', 'findings', 'blockedReasons']),
  lifecycle: FORMAL_PRICE_APPROVAL_POST_CREATION_STATE_TAKEOVER_STATES,
  sourceState: 'created',
  futureTargetState: 'pending_approval',
  automaticTakeover: false,
  stateMutationAllowed: false,
  workflowEngineConnected: false,
  takeoverInstanceCount: 0,
  persistenceMode: 'none',
  businessWriteCount: 0,
  productionDataWritten: false,
})

export function validateFormalPriceApprovalPostCreationStateTakeover(model = FORMAL_PRICE_APPROVAL_POST_CREATION_STATE_TAKEOVER) {
  const valid = model.takeoverCode === 'SCM_FORMAL_PRICE_APPROVAL_POST_CREATION_STATE_TAKEOVER'
    && model.takeoverKind === 'POST_CREATION_STATE_OWNERSHIP_DESIGN_ONLY'
    && model.lifecycle.join(',') === 'not_assessed,awaiting_created_evidence,takeover_ready,isolated,blocked,manual_review'
    && model.sourceState === 'created'
    && model.futureTargetState === 'pending_approval'
    && model.automaticTakeover === false
    && model.stateMutationAllowed === false
    && model.workflowEngineConnected === false
    && model.takeoverInstanceCount === 0
    && model.persistenceMode === 'none'
    && model.businessWriteCount === 0
    && model.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
