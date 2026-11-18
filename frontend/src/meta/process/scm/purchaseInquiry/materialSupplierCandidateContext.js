import { normalizePurchaseInquirySupplierCandidate } from './purchaseInquirySupplierCandidateContext.js'

export const MATERIAL_SUPPLIER_CANDIDATE_CONTEXT_VERSION = 'V1.14.2.8.18.7A'

export function normalizeMaterialSupplierCandidate(material = {}, supplier = {}) {
  const candidate = normalizePurchaseInquirySupplierCandidate(supplier)
  return Object.freeze({
    materialCode: String(material.materialCode || ''),
    materialName: String(material.materialName || ''),
    supplierCode: candidate.supplierCode,
    supplierName: candidate.supplierName,
    supplierStatus: candidate.supplierStatus,
    source: candidate.source,
  })
}

export function buildMaterialSupplierCandidates(materialLines = [], fallbackCandidates = []) {
  return Object.freeze(materialLines.flatMap(line => {
    const candidates = line.supplierCandidates || line.materialSupplierCandidates || fallbackCandidates
    return candidates.map(candidate => normalizeMaterialSupplierCandidate(line, candidate))
  }))
}

export function createMaterialSupplierCandidateContext(materialLines = [], fallbackCandidates = []) {
  const materialSupplierCandidates = buildMaterialSupplierCandidates(materialLines, fallbackCandidates)
  return Object.freeze({
    objectType: 'MaterialSupplierCandidateContext',
    source: 'Supplier Master',
    allowFreeText: false,
    materialLineCount: materialLines.length,
    materialSupplierCandidates,
  })
}

export function validateMaterialSupplierCandidateContext(context = {}) {
  const records = context.materialSupplierCandidates || []
  const materialCodes = new Set(records.map(item => item.materialCode))
  const valid = context.objectType === 'MaterialSupplierCandidateContext'
    && context.allowFreeText === false && context.materialLineCount > 0
    && materialCodes.size === context.materialLineCount
    && records.every(item => ['materialCode', 'materialName', 'supplierCode', 'supplierName',
      'supplierStatus', 'source'].every(field => Boolean(item[field])))
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
