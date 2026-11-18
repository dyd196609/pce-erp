import { createQuoteComparisonModel } from '../process/scm/quoteComparison/quoteComparisonDomainModelV1142810.js'
import { evaluateQuoteComparisonActionGuard } from '../process/scm/quoteComparison/quoteComparisonActionContractsV1142810.js'
import { resolveQuoteComparisonTransition } from '../process/scm/quoteComparison/quoteComparisonStateContractV1142810.js'
import { createSupplierQuoteToQuoteComparisonHandoff } from '../process/scm/quoteComparison/supplierQuoteToQuoteComparisonHandoffContractV1142810.js'
import { quoteComparisonRuntimeStoreV1142810 } from './quoteComparisonRuntimeStoreV1142810.js'

export const QUOTE_COMPARISON_ACTION_RUNTIME_VERSION = 'V1.14.2.8.18.10'
const boundaries = Object.freeze({ supplierRecommendationCreated: false, purchaseOrderCreated: false, financeCreated: false })

export function executeCreateQuoteComparisonContext(sourceFacts = {}, store = quoteComparisonRuntimeStoreV1142810) {
  const existing = store.findContextByInquiryNo(sourceFacts.inquiryNo)
  if (existing) return Object.freeze({ result: 'PASS', idempotent: true, context: existing, ...boundaries })
  try {
    const handoff = createSupplierQuoteToQuoteComparisonHandoff(sourceFacts)
    const context = store.saveContext(handoff.context)
    return Object.freeze({ result: handoff.result, idempotent: false, context, handoff, ...boundaries })
  } catch (error) {
    return Object.freeze({ result: 'FAIL', error: error.message, ...boundaries })
  }
}

const rank = (rows, valueOf) => {
  const values = [...new Set(rows.map(valueOf))].sort((a, b) => a < b ? -1 : a > b ? 1 : 0)
  return new Map(values.map((value, index) => [value, index + 1]))
}

export function executeGenerateQuoteComparison(context = {}, store = quoteComparisonRuntimeStoreV1142810,
  asOf = new Date().toISOString().slice(0, 10)) {
  const guard = evaluateQuoteComparisonActionGuard('GENERATE_QUOTE_COMPARISON', context.comparisonStatus)
  const transition = resolveQuoteComparisonTransition(context.comparisonStatus, 'GENERATE_QUOTE_COMPARISON')
  if (!guard.allowed || !transition.allowed) return Object.freeze({ result: 'FAIL', guard, transition, ...boundaries })
  try {
    const comparisons = context.materialLines.flatMap(line => {
      const rows = context.supplierQuotes.filter(item => item.materialCode === line.materialCode)
      const priceRanks = rank(rows, item => Number(item.unitPrice || 0) * Number(item.quantity || line.quantity || 0))
      const deliveryRanks = rank(rows, item => item.deliveryDate)
      return rows.map(quote => createQuoteComparisonModel({ ...quote,
        inquiryNo: context.sourceInquiryNo, materialName: quote.materialName || line.materialName,
        quantity: quote.quantity || line.quantity }, {
        priceRank: priceRanks.get(Number(quote.unitPrice || 0) * Number(quote.quantity || line.quantity || 0)),
        deliveryRank: deliveryRanks.get(quote.deliveryDate),
        validityStatus: quote.validityDate >= asOf ? 'valid' : 'expired',
      }))
    })
    if (!comparisons.length) throw new Error('QUOTE_COMPARISON_FACTS_EMPTY')
    store.saveComparisons(context.comparisonPreparationNo, comparisons)
    const updated = store.saveContext({ ...context, comparisonStatus: transition.to,
      updatedAt: new Date().toISOString() })
    return Object.freeze({ result: 'PASS', context: updated, comparisons: Object.freeze(comparisons), ...boundaries })
  } catch (error) {
    return Object.freeze({ result: 'FAIL', error: error.message, context, ...boundaries })
  }
}

export function executeSaveQuoteComparison(context = {}, store = quoteComparisonRuntimeStoreV1142810) {
  const guard = evaluateQuoteComparisonActionGuard('SAVE_QUOTE_COMPARISON', context.comparisonStatus)
  const transition = resolveQuoteComparisonTransition(context.comparisonStatus, 'SAVE_QUOTE_COMPARISON')
  const comparisons = store.listComparisons().filter(item =>
    item.comparisonPreparationNo === context.comparisonPreparationNo)
  if (!guard.allowed || !transition.allowed || !comparisons.length) {
    return Object.freeze({ result: 'FAIL', guard, transition, reason: 'QUOTE_COMPARISON_NOT_READY', ...boundaries })
  }
  const updated = store.saveContext({ ...context, comparisonStatus: transition.to,
    updatedAt: new Date().toISOString() })
  const nextPreparation = store.saveRecommendationPreparation({
    objectType: 'SupplierRecommendationDecisionPreparationContext',
    recommendationPreparationNo: `SRDP-${context.sourceInquiryNo}`,
    comparisonPreparationNo: context.comparisonPreparationNo,
    sourceInquiryNo: context.sourceInquiryNo,
    sourceRequestNo: context.sourceRequestNo,
    comparisons,
    preparationStatus: 'comparison_ready',
    createdAt: new Date().toISOString(),
    supplierRecommendationCreated: false,
    purchaseOrderCreated: false,
    financeCreated: false,
  })
  return Object.freeze({ result: 'PASS', context: updated, comparisons: Object.freeze(comparisons),
    nextPreparation, ...boundaries })
}
