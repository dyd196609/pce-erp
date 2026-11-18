import { FORMAL_PRICE_APPROVAL_RUNTIME_STATE_MACHINE, evaluateFormalPriceApprovalRuntimeTransition } from '../domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalRuntimeStateMachine.js'
import { evaluateFormalPriceApprovalRuntimeReadiness } from '../domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalRuntimeRuleEngine.js'

export const FORMAL_PRICE_APPROVAL_RUNTIME_VERSION = 'V1.14.2.8.6.7'

export const FORMAL_PRICE_APPROVAL_RUNTIME = Object.freeze({
  runtimeCode: 'SCM_FORMAL_PRICE_APPROVAL_RUNTIME',
  version: FORMAL_PRICE_APPROVAL_RUNTIME_VERSION,
  objectCode: 'SCM_FORMAL_PRICE_APPROVAL_OBJECT',
  stateMachineCode: FORMAL_PRICE_APPROVAL_RUNTIME_STATE_MACHINE.machineCode,
  executionMode: 'design_only',
  workflowEngineConnected: false,
  approvalModuleConnected: false,
  stateMutationAllowed: false,
  automaticProgression: false,
  approvalInstanceCount: 0,
  approvalTaskCount: 0,
  businessWriteCount: 0,
  productionDataWritten: false,
})

export function evaluateFormalPriceApprovalRuntime(input = {}) {
  const readiness = evaluateFormalPriceApprovalRuntimeReadiness({ ...input, workflowEngineConnected: false })
  const transition = evaluateFormalPriceApprovalRuntimeTransition({
    fromStatus: 'definition_only',
    toStatus: readiness.evaluatedState,
  })
  return Object.freeze({
    runtimeCode: FORMAL_PRICE_APPROVAL_RUNTIME.runtimeCode,
    readiness,
    transition,
    currentStatus: 'definition_only',
    evaluatedStatus: readiness.evaluatedState,
    stateChanged: false,
    approvalInstanceCreated: false,
    approvalWorkflowStarted: false,
    approvalTaskCreated: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}
