import { INQUIRY_PREPARATION_STATE_CONTRACT_CODE } from './inquiryPreparationStateContract.js'

const text = value => String(value ?? '').trim()
const freezeList = values => Object.freeze(values.map(item => Object.freeze(item)))

function normalizeLine(line = {}, index = 0) {
  return Object.freeze({ lineNo: line.lineNo ?? index + 1, materialCode: text(line.materialCode),
    materialName: text(line.materialName), specification: text(line.specification), unit: text(line.unit),
    quantity: Number(line.quantity || 0), requiredDate: text(line.requiredDate) })
}

function normalizeCandidates(request = {}) {
  const candidates = new Map()
  const source = request.supplierCandidates || request.items || request.inquiryEligibility?.items || []
  source.forEach(item => {
    const supplierId = text(item.supplierId || item.suggestedSupplierId)
    const supplierCode = text(item.supplierCode || item.suggestedSupplierCode)
    const supplierName = text(item.supplierName || item.suggestedSupplierName)
    const key = supplierId || supplierCode || supplierName
    if (key) candidates.set(key, Object.freeze({ supplierId, supplierCode, supplierName,
      source: 'purchase_request_suggestion', inquiryTaskCreated: false }))
  })
  return freezeList([...candidates.values()])
}

export function createInquiryPreparationContext(request = {}, clock = () => new Date().toISOString()) {
  const sourceRequestNo = text(request.requestNo || request.sourceRequestNo)
  const materialLines = freezeList((request.items || request.inquiryEligibility?.items || request.materialLines || [])
    .map(normalizeLine))
  const supplierCandidates = normalizeCandidates(request)
  const requiredDate = materialLines.map(line => line.requiredDate).filter(Boolean).sort()[0] || ''
  const context = Object.freeze({
    objectType: 'InquiryPreparationContext', modelCode: 'SCM_INQUIRY_PREPARATION_OBJECT',
    contextContractCode: 'SCM_INQUIRY_PREPARATION_CONTEXT',
    contractVersion: 'V1.14.2.8.18.3', stateContractCode: INQUIRY_PREPARATION_STATE_CONTRACT_CODE,
    inquiryPreparationNo: `IPR-${sourceRequestNo}`, sourceRequestNo,
    sourceObjectType: 'PurchaseRequest', sourceObjectId: text(request.objectId || request.id || sourceRequestNo),
    materialLines, supplierCandidates, requiredDate, preparationStatus: 'created',
    createdFrom: 'CREATE_INQUIRY_PREPARATION', createdAt: clock(),
    sourceTrace: Object.freeze({ sourceObjectType: 'PurchaseRequest',
      sourceObjectId: text(request.objectId || request.id || sourceRequestNo), sourceRequestNo }),
    approvalEvidence: Object.freeze({ approvalStatus: 'approved',
      approvedBy: text(request.approvedBy || request.approver || request.approvalCurrentApprover),
      approvalResult: text(request.approvalResult || 'approved'), sourceRequestNo }),
    stateHistory: Object.freeze(['created']),
    // V1.14.2.8.9 compatibility projection. It does not create a PurchaseInquiry.
    inquiryLines: materialLines, sourceRequestDate: text(request.requestDate || request.sourceRequestDate),
    requester: text(request.requester), requestDepartment: text(request.department || request.requestDepartment),
    purchaseDepartment: text(request.purchaseDepartment), status: 'prepared', statusLabel: '询价准备就绪',
    formalInquiryCreated: false, inquiryCreated: false, quotationTaskCreated: false,
    supplierSent: false, quotationCreated: false, purchaseOrderCreated: false,
    databaseWritten: false, productionDataWritten: false,
  })
  return context
}

export function validateInquiryPreparationContext(context = {}) {
  const valid = context.objectType === 'InquiryPreparationContext'
    && context.contextContractCode === 'SCM_INQUIRY_PREPARATION_CONTEXT'
    && Boolean(context.inquiryPreparationNo) && Boolean(context.sourceRequestNo)
    && context.sourceObjectType === 'PurchaseRequest' && Boolean(context.sourceObjectId)
    && context.materialLines?.length > 0
    && context.materialLines.every(line => line.materialCode && line.materialName
      && line.quantity > 0 && line.requiredDate)
    && Array.isArray(context.supplierCandidates) && Boolean(context.requiredDate)
    && context.createdFrom === 'CREATE_INQUIRY_PREPARATION' && Boolean(context.createdAt)
    && context.sourceTrace?.sourceRequestNo === context.sourceRequestNo
    && context.formalInquiryCreated === false && context.quotationTaskCreated === false
    && context.supplierSent === false && context.quotationCreated === false
    && context.purchaseOrderCreated === false && context.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
