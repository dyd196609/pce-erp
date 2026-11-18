export const PURCHASE_INQUIRY_BATCH_PREPARATION_RULE_VERSION = 'V1.14.2.8.7.13.1'

export function evaluatePurchaseInquiryBatchPreparation({ preparations = [], existingInquiries = [] } = {}) {
  const seenPreparations = new Set()
  const seenSources = new Set()
  const existingPreparationNos = new Set(existingInquiries.map(item => item.sourcePreparationNo).filter(Boolean))
  const existingSourceNos = new Set(existingInquiries.map(item => item.sourceRequestNo).filter(Boolean))
  const candidates = []
  const blocked = []
  preparations.forEach(preparation => {
    const reasons = []
    if (!preparation?.inquiryPreparationNo || !preparation?.sourceRequestNo) reasons.push('source_trace_missing')
    if (preparation?.status !== 'prepared') reasons.push('preparation_not_ready')
    if (!Array.isArray(preparation?.inquiryLines) || preparation.inquiryLines.length === 0) reasons.push('inquiry_lines_missing')
    if (seenPreparations.has(preparation?.inquiryPreparationNo) || seenSources.has(preparation?.sourceRequestNo)) reasons.push('duplicate_batch_source')
    if (existingPreparationNos.has(preparation?.inquiryPreparationNo) || existingSourceNos.has(preparation?.sourceRequestNo)) reasons.push('purchase_inquiry_already_exists')
    if (reasons.length) blocked.push(Object.freeze({ preparation, reasons: Object.freeze(reasons) }))
    else candidates.push(preparation)
    seenPreparations.add(preparation?.inquiryPreparationNo)
    seenSources.add(preparation?.sourceRequestNo)
  })
  return Object.freeze({ ruleCode: 'SCM_PURCHASE_INQUIRY_BATCH_PREPARATION_RULE', result: 'PASS',
    batchInputCount: preparations.length, batchOutputCount: candidates.length, candidates: Object.freeze(candidates),
    blocked: Object.freeze(blocked), automaticActivation: false, onePreparationOneInquiry: true,
    supplierQuoteCreated: false, purchaseOrderCreated: false, financeObjectCreated: false })
}
