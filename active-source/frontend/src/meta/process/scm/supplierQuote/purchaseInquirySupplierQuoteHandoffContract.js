import { createProcessHandoffContract } from '../../contract/processHandoffContract.js'
import {
  PURCHASE_INQUIRY_HANDOFF_SOURCE_NODE_CODE,
  SUPPLIER_QUOTE_NODE_CODE,
} from './supplierQuoteNodeRuntimeContract.js'

export const PURCHASE_INQUIRY_SUPPLIER_QUOTE_HANDOFF_CONTRACT = createProcessHandoffContract({
  handoffCode: 'PURCHASE_INQUIRY_TO_SUPPLIER_QUOTE_CONTEXT',
  fromNode: PURCHASE_INQUIRY_HANDOFF_SOURCE_NODE_CODE,
  toNode: SUPPLIER_QUOTE_NODE_CODE,
  outputObject: 'PurchaseInquiry',
  inputObject: 'SupplierQuoteContext',
  mappingCode: 'MAP_PURCHASE_INQUIRY_TO_SUPPLIER_QUOTE_CONTEXT',
  actionCode: 'CREATE_SUPPLIER_QUOTE_CONTEXT',
  requiredContextKeys: ['processInstanceId', 'objectId', 'correlationId', 'state'],
})

export function validatePurchaseInquirySupplierQuoteHandoff(inquiry = {}, context = {}) {
  const candidateIds = (context.supplierCandidates || []).map(item => item.supplierId)
  const valid = Boolean(inquiry.inquiryNo)
    && context.objectType === 'SupplierQuoteContext'
    && context.inquiryNo === inquiry.inquiryNo
    && Array.isArray(context.materials) && context.materials.length > 0
    && context.materials.every(item => item.materialCode && item.quantity > 0)
    && candidateIds.length > 0 && candidateIds.every(Boolean)
    && Boolean(context.deadline)
    && context.supplierApiCalled === false
  return Object.freeze({
    result: valid ? 'PASS' : 'FAIL',
    valid,
    transferredFields: Object.freeze(['inquiryNo', 'materials', 'quantity', 'supplierCandidates', 'deadline']),
    mappingCode: PURCHASE_INQUIRY_SUPPLIER_QUOTE_HANDOFF_CONTRACT.mappingCode,
  })
}

