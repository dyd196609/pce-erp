import { createProcessHandoffContract } from '../../contract/processHandoffContract.js'
import {
  PURCHASE_INQUIRY_NODE_CODE,
  PURCHASE_INQUIRY_PREPARATION_SOURCE_NODE_CODE,
} from './purchaseInquiryNodeRuntimeContract.js'

export const PURCHASE_INQUIRY_PREPARATION_HANDOFF_CONTRACT = createProcessHandoffContract({
  handoffCode: 'INQUIRY_PREPARATION_TO_PURCHASE_INQUIRY',
  fromNode: PURCHASE_INQUIRY_PREPARATION_SOURCE_NODE_CODE,
  toNode: PURCHASE_INQUIRY_NODE_CODE,
  outputObject: 'InquiryPreparationBatch',
  inputObject: 'InquiryPreparationBatch',
  actionCode: 'START_PURCHASE_INQUIRY',
  requiredContextKeys: ['processInstanceId', 'objectId', 'correlationId', 'state'],
})

export function validatePurchaseInquiryPreparationHandoff(preparation = {}, inquiry = {}) {
  const valid = preparation.modelCode === 'SCM_INQUIRY_PREPARATION_OBJECT'
    && preparation.status === 'prepared'
    && Boolean(preparation.inquiryPreparationNo)
    && inquiry.sourcePreparationNo === preparation.inquiryPreparationNo
    && inquiry.sourceRequestNo === preparation.sourceRequestNo
    && inquiry.statusCode === 'draft'
    && inquiry.runtimeState === 'inquiry_draft'
  return Object.freeze({
    result: valid ? 'PASS' : 'FAIL',
    valid,
    inputObject: 'InquiryPreparationBatch',
    outputObject: 'PurchaseInquiry',
  })
}

