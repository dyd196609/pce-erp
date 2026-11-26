import test from 'node:test'
import assert from 'node:assert/strict'

import { executeProcessAction } from '../../src/meta/process/runtime/processRuntimeEngine.js'
import {
  createPurchaseRequestProcessAcceptanceDefinition,
  PURCHASE_REQUEST_WALKTHROUGH_STEPS,
  runPurchaseRequestEndToEndBusinessWalkthrough,
  validatePurchaseRequestProcessAcceptance,
} from '../../src/meta/process/scm/purchaseRequest/purchaseRequestProcessAcceptanceProfile.js'
import { validatePurchaseRequestStateSeparation } from '../../src/meta/process/scm/purchaseRequest/purchaseRequestStateTransitionContract.js'

function walkthroughAdapters(callOrder = []) {
  return {
    async createPurchaseRequest() {
      callOrder.push('CREATE_PURCHASE_REQUEST')
      return { requestNo: 'PR-PROCESS-006-UNIT', items: [{ materialCode: 'MAT-001', quantity: 2 }] }
    },
    async savePurchaseRequest(request) {
      callOrder.push('SAVE_PURCHASE_REQUEST')
      return { ...request, objectId: 'PR-UNIT-1', statusCode: 'draft', approvalStatus: 'not_submitted' }
    },
    async submitPurchaseRequest(request) {
      callOrder.push('SUBMIT_PURCHASE_REQUEST')
      return { ...request, statusCode: 'submitted', approvalStatus: 'pending' }
    },
    async approvePurchaseRequest(request) {
      callOrder.push('APPROVE_PURCHASE_REQUEST')
      return { ...request, statusCode: 'approved', approvalStatus: 'completed' }
    },
    async generateInquiryPreparation(request) {
      callOrder.push('GENERATE_INQUIRY_PREPARATION')
      return {
        modelCode: 'SCM_INQUIRY_PREPARATION_OBJECT',
        inquiryPreparationNo: `IPR-${request.requestNo}`,
        sourceRequestNo: request.requestNo,
        status: 'prepared',
        inquiryLines: request.items,
      }
    },
    async enterPurchaseInquiry(preparation) {
      callOrder.push('ENTER_PURCHASE_INQUIRY')
      return { route: '/scm/purchase-inquiry', inquiryPreparationNo: preparation.inquiryPreparationNo }
    },
  }
}

test('PROCESS-006 executes the required purchase request business path in order', async () => {
  const callOrder = []
  const walkthrough = await runPurchaseRequestEndToEndBusinessWalkthrough(walkthroughAdapters(callOrder))

  assert.equal(walkthrough.result, 'PASS')
  assert.equal(walkthrough.completed, true)
  assert.deepEqual(callOrder, PURCHASE_REQUEST_WALKTHROUGH_STEPS)
  assert.deepEqual(walkthrough.steps.map(item => item.stepCode), PURCHASE_REQUEST_WALKTHROUGH_STEPS)
})

test('purchase request acceptance profile passes Page Runtime Action State Handoff Regression and PROCESS-006', async () => {
  const walkthrough = await runPurchaseRequestEndToEndBusinessWalkthrough(walkthroughAdapters())
  const acceptance = validatePurchaseRequestProcessAcceptance(walkthrough)

  assert.equal(acceptance.status, 'SCM_PURCHASE_REQUEST_RUNTIME_READY')
  for (const family of ['page', 'runtime', 'action', 'state', 'handoff', 'regression', 'process006']) {
    assert.equal(acceptance.report.sections[family].result, 'PASS', family)
  }
})

test('approval status and business status remain separate projections', () => {
  assert.deepEqual(validatePurchaseRequestStateSeparation(), {
    result: 'PASS',
    valid: true,
    rule: 'APPROVAL_STATUS_AND_BUSINESS_STATUS_SEPARATED',
  })
})

test('four Action Contracts drive the declared state sequence and final handoff', async () => {
  const walkthrough = await runPurchaseRequestEndToEndBusinessWalkthrough(walkthroughAdapters())
  const definition = createPurchaseRequestProcessAcceptanceDefinition(walkthrough)
  let context = definition.contexts[0]
  let finalResult

  for (const actionCode of ['SAVE_PURCHASE_REQUEST', 'SUBMIT_PURCHASE_REQUEST', 'APPROVE_PURCHASE_REQUEST', 'GENERATE_INQUIRY_PREPARATION']) {
    finalResult = executeProcessAction(definition, context, actionCode)
    context = finalResult.context
  }

  assert.equal(context.state, 'inquiry_prepared')
  assert.equal(finalResult.handoff.objectType, 'InquiryPreparationBatch')
  assert.equal(finalResult.handoff.toNode, 'scm-purchase-inquiry-entry')
})

test('PROCESS-006 fails when an actual path step does not reach its required state', async () => {
  const adapters = walkthroughAdapters()
  adapters.approvePurchaseRequest = async request => ({ ...request, statusCode: 'approved', approvalStatus: 'pending' })
  const walkthrough = await runPurchaseRequestEndToEndBusinessWalkthrough(adapters)
  const acceptance = validatePurchaseRequestProcessAcceptance(walkthrough)

  assert.equal(walkthrough.result, 'FAIL')
  assert.equal(acceptance.report.sections.process006.result, 'FAIL')
  assert.equal(acceptance.status, 'FAIL')
})

