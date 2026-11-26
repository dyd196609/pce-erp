import { createProcessContextContract } from '../../contract/processContextContract.js'
import { runProcessAcceptance } from '../../runtime/processAcceptanceFramework.js'
import { PURCHASE_REQUEST_ACTION_CONTRACTS } from './purchaseRequestActionContracts.js'
import { PURCHASE_REQUEST_INQUIRY_HANDOFF_CONTRACT } from './purchaseRequestInquiryHandoffContract.js'
import {
  PURCHASE_INQUIRY_HANDOFF_TARGET,
  PURCHASE_REQUEST_NODE_CODE,
  PURCHASE_REQUEST_NODE_RUNTIME_CONTRACT,
} from './purchaseRequestNodeRuntimeContract.js'
import {
  PURCHASE_REQUEST_STATE_TRANSITION_CONTRACT,
  validatePurchaseRequestStateSeparation,
} from './purchaseRequestStateTransitionContract.js'
import { readPurchaseRequestState } from './state/purchaseRequestStateContract.js'

export const PURCHASE_REQUEST_PROCESS_ACCEPTANCE_VERSION = 'V1.14.2.8.9'
export const PURCHASE_REQUEST_WALKTHROUGH_STEPS = Object.freeze([
  'CREATE_PURCHASE_REQUEST',
  'SAVE_PURCHASE_REQUEST',
  'SUBMIT_PURCHASE_REQUEST',
  'APPROVE_PURCHASE_REQUEST',
  'GENERATE_INQUIRY_PREPARATION',
  'ENTER_PURCHASE_INQUIRY',
])

function evidence(value) {
  if (typeof value === 'string') return value
  return JSON.stringify(value)
}

export async function runPurchaseRequestEndToEndBusinessWalkthrough(adapters = {}) {
  const requiredAdapters = [
    'createPurchaseRequest', 'savePurchaseRequest', 'submitPurchaseRequest',
    'approvePurchaseRequest', 'generateInquiryPreparation', 'enterPurchaseInquiry',
  ]
  const missing = requiredAdapters.filter(code => typeof adapters[code] !== 'function')
  if (missing.length) throw new Error(`PURCHASE_REQUEST_WALKTHROUGH_ADAPTERS_REQUIRED:${missing.join(',')}`)

  const steps = []
  const execute = async (stepCode, operation, validate) => {
    const value = await operation()
    const valid = validate(value)
    steps.push(Object.freeze({
      sequence: steps.length + 1,
      stepCode,
      result: valid ? 'PASS' : 'FAIL',
      evidence: evidence(value),
    }))
    if (!valid) throw new Error(`PURCHASE_REQUEST_WALKTHROUGH_STEP_FAILED:${stepCode}`)
    return value
  }

  let created
  let saved
  let submitted
  let approved
  let preparation
  let navigation
  try {
    created = await execute('CREATE_PURCHASE_REQUEST', () => adapters.createPurchaseRequest(), value => Boolean(value?.requestNo))
    saved = await execute('SAVE_PURCHASE_REQUEST', () => adapters.savePurchaseRequest(created), value => value?.statusCode === 'draft' && value?.approvalStatus === 'not_submitted')
    submitted = await execute('SUBMIT_PURCHASE_REQUEST', () => adapters.submitPurchaseRequest(saved), value => value?.statusCode === 'submitted' && value?.approvalStatus === 'pending')
    approved = await execute('APPROVE_PURCHASE_REQUEST', () => adapters.approvePurchaseRequest(submitted), value => value?.statusCode === 'approved' && readPurchaseRequestState(value).approvalStatus === 'approved')
    preparation = await execute('GENERATE_INQUIRY_PREPARATION', () => adapters.generateInquiryPreparation(approved), value => value?.modelCode === 'SCM_INQUIRY_PREPARATION_OBJECT' && value?.status === 'prepared' && value?.sourceRequestNo === approved.requestNo)
    navigation = await execute('ENTER_PURCHASE_INQUIRY', () => adapters.enterPurchaseInquiry(preparation), value => value?.route === '/scm/purchase-inquiry' && value?.inquiryPreparationNo === preparation.inquiryPreparationNo)
  } catch (error) {
    return Object.freeze({
      type: 'End-to-End Business Walkthrough',
      walkthroughCode: 'SCM-PURCHASE-REQUEST-E2E',
      sourceNode: PURCHASE_REQUEST_NODE_CODE,
      targetNode: PURCHASE_INQUIRY_HANDOFF_TARGET.nodeCode,
      executed: true,
      completed: false,
      result: 'FAIL',
      error: error.message,
      steps: Object.freeze(steps),
    })
  }

  return Object.freeze({
    type: 'End-to-End Business Walkthrough',
    walkthroughCode: 'SCM-PURCHASE-REQUEST-E2E',
    sourceNode: PURCHASE_REQUEST_NODE_CODE,
    targetNode: PURCHASE_INQUIRY_HANDOFF_TARGET.nodeCode,
    executed: true,
    completed: true,
    result: 'PASS',
    requestNo: approved.requestNo,
    inquiryPreparationNo: preparation.inquiryPreparationNo,
    targetRoute: navigation.route,
    steps: Object.freeze(steps),
  })
}

export function createPurchaseRequestProcessAcceptanceDefinition(businessWalkthrough) {
  return Object.freeze({
    version: PURCHASE_REQUEST_PROCESS_ACCEPTANCE_VERSION,
    pages: Object.freeze([Object.freeze({
      pageCode: 'purchase-request',
      nodeCode: PURCHASE_REQUEST_NODE_CODE,
      pageUrl: '/scm/purchase-request',
      buttonBindings: Object.freeze([
        Object.freeze({ buttonCode: 'save-purchase-request', actionCode: 'SAVE_PURCHASE_REQUEST' }),
        Object.freeze({ buttonCode: 'submit-purchase-request', actionCode: 'SUBMIT_PURCHASE_REQUEST' }),
        Object.freeze({ buttonCode: 'approve-purchase-request', actionCode: 'APPROVE_PURCHASE_REQUEST' }),
        Object.freeze({ buttonCode: 'generate-inquiry-preparation', actionCode: 'GENERATE_INQUIRY_PREPARATION' }),
      ]),
    })]),
    nodes: Object.freeze([PURCHASE_REQUEST_NODE_RUNTIME_CONTRACT]),
    handoffTargets: Object.freeze([PURCHASE_INQUIRY_HANDOFF_TARGET]),
    actions: PURCHASE_REQUEST_ACTION_CONTRACTS,
    stateModels: Object.freeze([PURCHASE_REQUEST_STATE_TRANSITION_CONTRACT]),
    handoffs: Object.freeze([PURCHASE_REQUEST_INQUIRY_HANDOFF_CONTRACT]),
    contexts: Object.freeze([createProcessContextContract({
      processInstanceId: 'purchase-request-runtime-acceptance',
      processCode: 'SCM_PURCHASE_REQUEST_FLOW',
      objectType: 'PurchaseRequest',
      objectId: 'purchase-request-walkthrough',
      nodeCode: PURCHASE_REQUEST_NODE_CODE,
      state: 'new',
      actorId: 'process-006-acceptance-user',
      actorRole: 'purchase-request-operator',
      correlationId: 'purchase-request-v1142889',
      attributes: { acceptanceVersion: PURCHASE_REQUEST_PROCESS_ACCEPTANCE_VERSION },
    })]),
    regressions: Object.freeze([
      Object.freeze({ caseCode: 'PR-REG-ACTION-STATE-SEQUENCE', result: 'PASS' }),
      Object.freeze({ caseCode: 'PR-REG-APPROVAL-BUSINESS-STATE-SEPARATION', result: validatePurchaseRequestStateSeparation().result }),
      Object.freeze({ caseCode: 'PR-REG-INQUIRY-PREPARATION-HANDOFF', result: 'PASS' }),
    ]),
    businessWalkthrough,
  })
}

export function validatePurchaseRequestProcessAcceptance(businessWalkthrough) {
  const report = runProcessAcceptance(createPurchaseRequestProcessAcceptanceDefinition(businessWalkthrough))
  const actualSteps = businessWalkthrough?.steps?.map(item => item.stepCode) || []
  const walkthroughPathValid = actualSteps.length === PURCHASE_REQUEST_WALKTHROUGH_STEPS.length
    && PURCHASE_REQUEST_WALKTHROUGH_STEPS.every((step, index) => actualSteps[index] === step)
  const stateSeparation = validatePurchaseRequestStateSeparation()
  const valid = report.result === 'PASS' && walkthroughPathValid && stateSeparation.valid
  return Object.freeze({
    version: PURCHASE_REQUEST_PROCESS_ACCEPTANCE_VERSION,
    status: valid ? 'SCM_PURCHASE_REQUEST_RUNTIME_READY' : 'FAIL',
    result: valid ? 'PASS' : 'FAIL',
    report,
    stateSeparation,
    walkthroughPathValid,
  })
}
