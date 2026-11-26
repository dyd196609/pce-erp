import { createProcessHandoffContract } from '../../contract/processHandoffContract.js'
import { PURCHASE_INQUIRY_ENTRY_NODE_CODE, PURCHASE_REQUEST_NODE_CODE } from './purchaseRequestNodeRuntimeContract.js'

export const PURCHASE_REQUEST_INQUIRY_HANDOFF_CONTRACT = createProcessHandoffContract({
  handoffCode: 'PURCHASE_REQUEST_TO_INQUIRY_PREPARATION',
  fromNode: PURCHASE_REQUEST_NODE_CODE,
  toNode: PURCHASE_INQUIRY_ENTRY_NODE_CODE,
  outputObject: 'InquiryPreparationBatch',
  inputObject: 'InquiryPreparationBatch',
  actionCode: 'GENERATE_INQUIRY_PREPARATION',
  requiredContextKeys: ['processInstanceId', 'objectId', 'correlationId', 'state'],
})

export function validatePurchaseRequestInquiryHandoff(preparation = {}) {
  const valid = preparation.modelCode === 'SCM_INQUIRY_PREPARATION_OBJECT'
    && Boolean(preparation.inquiryPreparationNo)
    && Boolean(preparation.sourceRequestNo)
    && preparation.status === 'prepared'
    && Array.isArray(preparation.inquiryLines)
    && preparation.inquiryLines.length > 0
  return Object.freeze({
    result: valid ? 'PASS' : 'FAIL',
    valid,
    sourceObject: 'PurchaseRequest',
    targetObject: 'InquiryPreparationBatch',
  })
}

