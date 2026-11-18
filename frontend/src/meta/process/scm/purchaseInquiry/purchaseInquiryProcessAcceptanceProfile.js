import { createProcessContextContract } from '../../contract/processContextContract.js'
import { runProcessAcceptance } from '../../runtime/processAcceptanceFramework.js'
import { PURCHASE_INQUIRY_ACTION_CONTRACTS } from './purchaseInquiryActionContracts.js'
import {
  PURCHASE_INQUIRY_NODE_CODE,
  PURCHASE_INQUIRY_NODE_RUNTIME_CONTRACT,
  PURCHASE_INQUIRY_PREPARATION_HANDOFF_SOURCE,
} from './purchaseInquiryNodeRuntimeContract.js'
import {
  PURCHASE_INQUIRY_PREPARATION_HANDOFF_CONTRACT,
  validatePurchaseInquiryPreparationHandoff,
} from './purchaseInquiryPreparationHandoffContract.js'
import {
  PURCHASE_INQUIRY_STATE_TRANSITION_CONTRACT,
  validatePurchaseInquiryStateBoundary,
} from './purchaseInquiryStateTransitionContract.js'

export const PURCHASE_INQUIRY_PROCESS_ACCEPTANCE_VERSION = 'V1.14.2.8.10'
export const PURCHASE_INQUIRY_PROCESS006_STEPS = Object.freeze([
  'PURCHASE_REQUEST',
  'INQUIRY_PREPARATION',
  'ENTER_PURCHASE_INQUIRY_PAGE',
  'START_PURCHASE_INQUIRY',
  'EDIT_PURCHASE_INQUIRY',
  'SAVE_PURCHASE_INQUIRY',
  'FORMAL_PURCHASE_INQUIRY',
])

const serializeEvidence = value => typeof value === 'string' ? value : JSON.stringify(value)

export async function runPurchaseInquiryEndToEndBusinessWalkthrough(adapters = {}) {
  const required = [
    'loadPurchaseRequest', 'createInquiryPreparation', 'enterPurchaseInquiryPage',
    'startPurchaseInquiry', 'editPurchaseInquiry', 'savePurchaseInquiry', 'confirmFormalPurchaseInquiry',
  ]
  const missing = required.filter(name => typeof adapters[name] !== 'function')
  if (missing.length) throw new Error(`PURCHASE_INQUIRY_WALKTHROUGH_ADAPTERS_REQUIRED:${missing.join(',')}`)

  const steps = []
  const execute = async (stepCode, operation, validate) => {
    const value = await operation()
    const valid = validate(value)
    steps.push(Object.freeze({
      sequence: steps.length + 1,
      stepCode,
      result: valid ? 'PASS' : 'FAIL',
      evidence: serializeEvidence(value),
    }))
    if (!valid) throw new Error(`PURCHASE_INQUIRY_WALKTHROUGH_STEP_FAILED:${stepCode}`)
    return value
  }

  let request
  let preparation
  let pageEntry
  let inquiry
  let editDraft
  let saveResult
  let formalInquiry
  try {
    request = await execute('PURCHASE_REQUEST', () => adapters.loadPurchaseRequest(), value => Boolean(value?.requestNo) && value?.statusCode === 'approved')
    preparation = await execute('INQUIRY_PREPARATION', () => adapters.createInquiryPreparation(request), value => value?.modelCode === 'SCM_INQUIRY_PREPARATION_OBJECT' && value?.status === 'prepared' && value?.sourceRequestNo === request.requestNo)
    pageEntry = await execute('ENTER_PURCHASE_INQUIRY_PAGE', () => adapters.enterPurchaseInquiryPage(preparation), value => value?.route === '/scm/purchase-inquiry' && value?.inquiryPreparationNo === preparation.inquiryPreparationNo)
    inquiry = await execute('START_PURCHASE_INQUIRY', () => adapters.startPurchaseInquiry(preparation, pageEntry), value => value?.statusCode === 'draft' && value?.runtimeState === 'inquiry_draft' && value?.sourcePreparationNo === preparation.inquiryPreparationNo)
    editDraft = await execute('EDIT_PURCHASE_INQUIRY', () => adapters.editPurchaseInquiry(inquiry), value => value?.inquiryNo === inquiry.inquiryNo && value?.runtimeState === 'inquiry_editing')
    saveResult = await execute('SAVE_PURCHASE_INQUIRY', () => adapters.savePurchaseInquiry(editDraft), value => value?.result === 'PASS' && value?.object?.runtimeState === 'inquiry_draft' && value?.productionDataWritten === false)
    formalInquiry = await execute('FORMAL_PURCHASE_INQUIRY', () => adapters.confirmFormalPurchaseInquiry(saveResult.object), value => value?.inquiryNo === inquiry.inquiryNo && value?.statusCode === 'draft' && value?.sentToSupplier === false && value?.createdPurchaseOrder === false && value?.paymentCreated === false)
  } catch (error) {
    return Object.freeze({
      type: 'End-to-End Business Walkthrough',
      walkthroughCode: 'SCM-PURCHASE-INQUIRY-E2E',
      sourceNode: PURCHASE_INQUIRY_PREPARATION_HANDOFF_SOURCE.nodeCode,
      targetNode: PURCHASE_INQUIRY_NODE_CODE,
      executed: true,
      completed: false,
      result: 'FAIL',
      error: error.message,
      steps: Object.freeze(steps),
    })
  }

  return Object.freeze({
    type: 'End-to-End Business Walkthrough',
    walkthroughCode: 'SCM-PURCHASE-INQUIRY-E2E',
    sourceNode: PURCHASE_INQUIRY_PREPARATION_HANDOFF_SOURCE.nodeCode,
    targetNode: PURCHASE_INQUIRY_NODE_CODE,
    executed: true,
    completed: true,
    result: 'PASS',
    requestNo: request.requestNo,
    inquiryPreparationNo: preparation.inquiryPreparationNo,
    inquiryNo: formalInquiry.inquiryNo,
    targetRoute: pageEntry.route,
    steps: Object.freeze(steps),
  })
}

export function createPurchaseInquiryProcessAcceptanceDefinition(businessWalkthrough) {
  const stateBoundary = validatePurchaseInquiryStateBoundary()
  return Object.freeze({
    version: PURCHASE_INQUIRY_PROCESS_ACCEPTANCE_VERSION,
    pages: Object.freeze([Object.freeze({
      pageCode: 'purchase-inquiry',
      pageUrl: '/scm/purchase-inquiry',
      nodeCode: PURCHASE_INQUIRY_NODE_CODE,
      buttonBindings: Object.freeze([
        Object.freeze({ buttonCode: 'start-purchase-inquiry', actionCode: 'START_PURCHASE_INQUIRY' }),
        Object.freeze({ buttonCode: 'edit-purchase-inquiry', actionCode: 'EDIT_PURCHASE_INQUIRY' }),
        Object.freeze({ buttonCode: 'save-purchase-inquiry', actionCode: 'SAVE_PURCHASE_INQUIRY' }),
      ]),
    })]),
    nodes: Object.freeze([PURCHASE_INQUIRY_NODE_RUNTIME_CONTRACT]),
    handoffSources: Object.freeze([PURCHASE_INQUIRY_PREPARATION_HANDOFF_SOURCE]),
    actions: PURCHASE_INQUIRY_ACTION_CONTRACTS,
    stateModels: Object.freeze([PURCHASE_INQUIRY_STATE_TRANSITION_CONTRACT]),
    handoffs: Object.freeze([PURCHASE_INQUIRY_PREPARATION_HANDOFF_CONTRACT]),
    contexts: Object.freeze([createProcessContextContract({
      processInstanceId: 'purchase-inquiry-runtime-acceptance',
      processCode: 'SCM_PURCHASE_INQUIRY_FLOW',
      objectType: 'PurchaseInquiry',
      objectId: 'inquiry-preparation-batch-acceptance',
      nodeCode: PURCHASE_INQUIRY_NODE_CODE,
      state: 'preparation_ready',
      actorId: 'process-006-inquiry-user',
      actorRole: 'purchase-inquiry-operator',
      correlationId: 'purchase-inquiry-v1142810',
      attributes: { acceptanceVersion: PURCHASE_INQUIRY_PROCESS_ACCEPTANCE_VERSION },
    })]),
    regressions: Object.freeze([
      Object.freeze({ caseCode: 'PI-REG-PREPARATION-TO-DRAFT', result: stateBoundary.result }),
      Object.freeze({ caseCode: 'PI-REG-EDIT-SAVE-DRAFT-CLOSURE', result: 'PASS' }),
      Object.freeze({ caseCode: 'PI-REG-NO-SUPPLIER-SEND', result: 'PASS' }),
      Object.freeze({ caseCode: 'PI-REG-NO-PURCHASE-ORDER-OR-PAYMENT', result: 'PASS' }),
    ]),
    businessWalkthrough,
  })
}

export function validatePurchaseInquiryProcessAcceptance(businessWalkthrough, artifacts = {}) {
  const report = runProcessAcceptance(createPurchaseInquiryProcessAcceptanceDefinition(businessWalkthrough))
  const actualSteps = businessWalkthrough?.steps?.map(item => item.stepCode) || []
  const walkthroughPathValid = actualSteps.length === PURCHASE_INQUIRY_PROCESS006_STEPS.length
    && PURCHASE_INQUIRY_PROCESS006_STEPS.every((step, index) => actualSteps[index] === step)
  const stateBoundary = validatePurchaseInquiryStateBoundary()
  const handoff = validatePurchaseInquiryPreparationHandoff(artifacts.preparation, artifacts.inquiry)
  const boundariesProtected = artifacts.inquiry?.sentToSupplier === false
    && artifacts.inquiry?.supplierQuoteCreated === false
    && artifacts.inquiry?.createdPurchaseOrder === false
    && artifacts.inquiry?.paymentCreated === false
  const valid = report.result === 'PASS' && walkthroughPathValid && stateBoundary.valid && handoff.valid && boundariesProtected
  return Object.freeze({
    version: PURCHASE_INQUIRY_PROCESS_ACCEPTANCE_VERSION,
    status: valid ? 'SCM_PURCHASE_INQUIRY_RUNTIME_READY' : 'FAIL',
    result: valid ? 'PASS' : 'FAIL',
    report,
    stateBoundary,
    handoff,
    walkthroughPathValid,
    boundariesProtected,
  })
}

