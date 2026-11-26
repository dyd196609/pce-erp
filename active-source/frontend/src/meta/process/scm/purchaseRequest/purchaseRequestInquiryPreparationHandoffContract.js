import { createProcessHandoffContract } from '../../contract/processHandoffContract.js'
import { readPurchaseRequestState } from './state/purchaseRequestStateContract.js'

export const PURCHASE_REQUEST_INQUIRY_PREPARATION_HANDOFF_CONTRACT = createProcessHandoffContract({
  handoffCode: 'PURCHASE_REQUEST_TO_INQUIRY_PREPARATION_V2',
  fromNode: 'scm-purchase-request', toNode: 'SCM_INQUIRY_PREPARATION',
  outputObject: 'PurchaseRequest', inputObject: 'InquiryPreparationContext',
  mappingCode: 'MAP_PURCHASE_REQUEST_TO_INQUIRY_PREPARATION_V2',
  actionCode: 'CREATE_INQUIRY_PREPARATION',
  requiredContextKeys: ['processInstanceId', 'objectId', 'correlationId', 'state'],
})

const text = value => String(value ?? '').trim()

export function validatePurchaseRequestInquiryPreparationHandoff(source = {}, target = {}) {
  const sourceLines = source.items || source.inquiryEligibility?.items || []
  const targetLines = target.inquiryLines || []
  const state = readPurchaseRequestState(source)
  const sourceQuantity = sourceLines.reduce((sum, line) => sum + Number(line.quantity || 0), 0)
  const targetQuantity = targetLines.reduce((sum, line) => sum + Number(line.quantity || 0), 0)
  const sourceSuppliers = new Set(sourceLines.map(line => text(line.suggestedSupplierId
    || line.suggestedSupplierCode || line.suggestedSupplierName)).filter(Boolean))
  const targetSuppliers = new Set((target.supplierCandidates || []).map(item => text(item.supplierId
    || item.supplierCode || item.supplierName)).filter(Boolean))
  const valid = state.approvalStatus === 'approved'
    && text(target.sourceRequestNo) === text(source.requestNo || source.sourceRequestNo)
    && text(target.requestDepartment) === text(source.department || source.requestDepartment)
    && text(target.purchaseDepartment) === text(source.purchaseDepartment)
    && sourceLines.length > 0 && sourceLines.length === targetLines.length
    && sourceLines.every((line, index) => text(line.materialCode) === text(targetLines[index]?.materialCode)
      && text(line.materialName) === text(targetLines[index]?.materialName)
      && text(line.specification) === text(targetLines[index]?.specification)
      && Number(line.quantity) === Number(targetLines[index]?.quantity)
      && text(line.requiredDate) === text(targetLines[index]?.requiredDate))
    && sourceQuantity > 0 && sourceQuantity === targetQuantity
    && sourceSuppliers.size === targetSuppliers.size
    && [...sourceSuppliers].every(item => targetSuppliers.has(item))
    && target.approvalEvidence?.approvalStatus === 'approved'
    && target.approvalEvidence?.sourceRequestNo === target.sourceRequestNo
    && target.sourceTrace?.sourceObjectType === 'PurchaseRequest'
    && target.sourceTrace?.sourceRequestNo === target.sourceRequestNo
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid,
    transferredFields: Object.freeze(['sourceRequestNo', 'materialCode', 'materialName', 'specification',
      'quantity', 'requiredDate', 'supplierCandidate', 'sourceTrace']) })
}
