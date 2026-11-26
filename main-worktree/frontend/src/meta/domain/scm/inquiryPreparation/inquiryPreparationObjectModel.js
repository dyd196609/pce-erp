export const INQUIRY_PREPARATION_VERSION = 'V1.14.2.8.7.9'

const text = value => String(value ?? '').trim()

function normalizeLine(line = {}, index = 0) {
  return Object.freeze({
    lineNo: line.lineNo ?? index + 1,
    materialCode: text(line.materialCode),
    materialName: text(line.materialName),
    specification: text(line.specification),
    unit: text(line.unit),
    quantity: line.quantity ?? '',
    requiredDate: text(line.requiredDate),
  })
}

function supplierCandidates(lines = []) {
  const candidates = new Map()
  lines.forEach(line => {
    const supplierId = text(line.suggestedSupplierId)
    const supplierCode = text(line.suggestedSupplierCode)
    const supplierName = text(line.suggestedSupplierName)
    if (!supplierId && !supplierCode && !supplierName) return
    const key = supplierId || supplierCode || supplierName
    candidates.set(key, Object.freeze({ supplierId, supplierCode, supplierName,
      source: 'purchase_request_suggestion', inquiryTaskCreated: false }))
  })
  return Object.freeze([...candidates.values()])
}

export function createInquiryPreparationObject(request = {}) {
  const inquiryLines = Object.freeze((request.items || request.inquiryEligibility?.items || []).map(normalizeLine))
  return Object.freeze({
    modelCode: 'SCM_INQUIRY_PREPARATION_OBJECT',
    version: INQUIRY_PREPARATION_VERSION,
    inquiryPreparationNo: `IPR-${text(request.requestNo || request.sourceRequestNo)}`,
    sourceRequestNo: text(request.requestNo || request.sourceRequestNo),
    sourceRequestDate: text(request.requestDate || request.sourceRequestDate),
    requester: text(request.requester),
    requestDepartment: text(request.department || request.requestDepartment),
    purchaseDepartment: text(request.purchaseDepartment),
    approvalEvidence: Object.freeze({ approvalStatus: 'approved',
      approvedBy: text(request.approvedBy || request.approver || request.approvalCurrentApprover),
      approvalResult: text(request.approvalResult || 'approved'), sourceRequestNo: text(request.requestNo || request.sourceRequestNo) }),
    inquiryLines,
    supplierCandidates: supplierCandidates(request.items || []),
    status: 'prepared',
    statusLabel: '询价准备完成',
    formalInquiryCreated: false,
    quotationTaskCreated: false,
    supplierSent: false,
    quotationCreated: false,
    databaseWritten: false,
  })
}

export function validateInquiryPreparationObject(model) {
  const valid = model?.modelCode === 'SCM_INQUIRY_PREPARATION_OBJECT'
    && Boolean(model.inquiryPreparationNo) && Boolean(model.sourceRequestNo)
    && model.status === 'prepared' && Array.isArray(model.inquiryLines) && model.inquiryLines.length > 0
    && model.formalInquiryCreated === false && model.quotationTaskCreated === false
    && model.supplierSent === false && model.quotationCreated === false && model.databaseWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
