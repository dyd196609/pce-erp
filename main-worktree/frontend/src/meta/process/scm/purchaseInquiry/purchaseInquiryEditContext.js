import { normalizePurchaseInquirySupplierCandidate } from './purchaseInquirySupplierCandidateContext.js'
import { buildMaterialSupplierCandidates, createMaterialSupplierCandidateContext,
  validateMaterialSupplierCandidateContext } from './materialSupplierCandidateContext.js'

export const PURCHASE_INQUIRY_EDIT_CONTEXT_VERSION = 'V1.14.2.8.18.7-SUPPLEMENT'

const cloneLine = (line = {}, fallbackCandidates = []) => {
  const ownCandidates = line.supplierCandidates || line.materialSupplierCandidates
  return {
    materialCode: String(line.materialCode || ''), materialName: String(line.materialName || ''),
    specification: String(line.specification || ''), quantity: Number(line.quantity || 0),
    requiredDate: String(line.requiredDate || ''), unit: String(line.unit || ''),
    supplierCandidates: ownCandidates ? ownCandidates.map(cloneSupplier) : fallbackCandidates,
  }
}
const cloneSupplier = supplier => ({ ...normalizePurchaseInquirySupplierCandidate(supplier) })

export function createPurchaseInquiryEditContext(inquiry = {}) {
  if (!inquiry.inquiryNo || inquiry.statusCode !== 'draft') throw new Error('PURCHASE_INQUIRY_DRAFT_EDIT_CONTEXT_REQUIRED')
  const supplierCandidates = (inquiry.supplierCandidates || inquiry.suppliers || []).map(cloneSupplier)
  const materialLines = (inquiry.materialLines || inquiry.lines || [])
    .map(line => cloneLine(line, supplierCandidates))
  return {
    objectType: 'PurchaseInquiryEditContext', inquiryNo: inquiry.inquiryNo,
    sourceRequestNo: String(inquiry.sourceRequestNo || ''),
    inquiryTitle: String(inquiry.inquiryTitle || ''), inquiryDate: String(inquiry.inquiryDate || ''),
    buyer: String(inquiry.buyer || inquiry.buyerName || ''),
    materialLines, supplierCandidates,
    initialSupplierCandidateSnapshot: JSON.stringify(supplierCandidates),
    materialSupplierCandidates: [...buildMaterialSupplierCandidates(materialLines, supplierCandidates)],
    statusCode: 'draft', statusLabel: inquiry.statusLabel || '草稿',
    sourceRuntimeState: inquiry.runtimeState || 'inquiry_draft',
    runtimeState: 'inquiry_editing', productionDataWritten: false,
  }
}

export function addPurchaseInquiryEditLine(context, line = {}) {
  context.materialLines.push(cloneLine({ quantity: 1, ...line }, context.supplierCandidates || []))
  return context
}

export function removePurchaseInquiryEditLine(context, index) {
  if (context.materialLines.length <= 1) throw new Error('PURCHASE_INQUIRY_LINE_REQUIRED')
  context.materialLines.splice(index, 1)
  return context
}

export function validatePurchaseInquiryEditContext(context = {}) {
  const materialCandidateContext = createMaterialSupplierCandidateContext(context.materialLines || [],
    context.supplierCandidates || [])
  const valid = context.objectType === 'PurchaseInquiryEditContext'
    && Boolean(context.inquiryNo && context.inquiryTitle && context.inquiryDate && context.buyer)
    && Array.isArray(context.materialLines) && context.materialLines.length > 0
    && context.materialLines.every(line => line.materialCode && line.materialName
      && Number(line.quantity) > 0 && line.requiredDate)
    && validateMaterialSupplierCandidateContext(materialCandidateContext).valid
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
