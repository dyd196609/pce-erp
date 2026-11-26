import { priceApprovalSupplierRecommendationHandoffStoreV11428161 } from '../process/scm/priceApproval/priceApprovalSupplierRecommendationHandoffV11428161.js'
import { supplierRecommendationTaskStoreV11428167 } from '../process/scm/supplierRecommendation/supplierRecommendationTaskRuntimeV11428167.js'
import { supplierRecommendationDecisionBatchStoreV11428169 } from '../process/scm/supplierRecommendation/supplierRecommendationDecisionBatchV11428169.js'

export const SUPPLIER_RECOMMENDATION_DATA_HANDOFF_PROVIDER_VERSION_V1142818 = 'V1.14.2.8.18.18'

const text = value => String(value ?? '').trim()
const freeze = value => Object.freeze(value)
const frozen = value => freeze(JSON.parse(JSON.stringify(value)))
const hasForbiddenFact = value => /PI-TEST-SR|(?:^|[-_])DEMO(?:[-_]|$)|(?:^|[-_])ACCEPTANCE(?:[-_]|$)/i
  .test(JSON.stringify(value || {}))

export function createSupplierRecommendationDataHandoffProviderV1142818({
  taskStore = supplierRecommendationTaskStoreV11428167,
  decisionBatchStore = supplierRecommendationDecisionBatchStoreV11428169,
  priceApprovalHandoffStore = priceApprovalSupplierRecommendationHandoffStoreV11428161,
} = {}) {
  return freeze({
    providerCode: 'SupplierRecommendationDataHandoffProviderV1142818',
    sourcePriority: freeze(['SupplierRecommendationTask', 'SupplierRecommendationDecisionBatch',
      'PriceApprovalRuntimeContext']),
    productionMode: true,
    load({ taskId } = {}) {
      const entryTaskId = text(taskId)
      const batch = decisionBatchStore.findById(entryTaskId)
      if (!entryTaskId || !batch) return freeze({ result: 'FAIL', error: 'DECISION_BATCH_ENTRY_NOT_FOUND',
        batch: null, items: freeze([]), productionDataWritten: false })
      const bindings = decisionBatchStore.listBindings(batch.batchId)
      const runtimeContexts = priceApprovalHandoffStore.listRuntimeContexts()
      const preparations = priceApprovalHandoffStore.listPreparations()
      const errors = []
      const items = batch.items.map(item => {
        const itemBindings = bindings.filter(binding => binding.materialCode === item.materialCode)
        if (!itemBindings.length) { errors.push(`ITEM_BINDING_COUNT_INVALID:${item.materialCode}`); return null }
        const tasks = itemBindings.map(binding => taskStore.findById(binding.taskId))
        if (tasks.some((task, index) => !task
          || task.runtimeContextId !== itemBindings[index].runtimeContextId
          || !task.sourcePriceApprovalIds.includes(itemBindings[index].priceApprovalId))) {
          errors.push(`TASK_DATA_MISMATCH:${item.materialCode}`); return null
        }
        const itemRuntimeContexts = tasks.map(task => runtimeContexts.find(value =>
          value.runtimeContextNo === task.runtimeContextId))
        if (itemRuntimeContexts.some(value => !value)) {
          errors.push(`RUNTIME_CONTEXT_NOT_FOUND:${item.materialCode}`); return null
        }
        const itemPreparations = itemBindings.map(binding => preparations.find(value =>
          value.priceApprovalId === binding.priceApprovalId
          && value.quoteComparisonId === binding.quoteComparisonId
          && value.materialCode === item.materialCode))
        if (itemPreparations.some(value => !value)) {
          errors.push(`PRICE_APPROVAL_CONTEXT_NOT_FOUND:${item.materialCode}`); return null
        }
        const materialMatches = itemRuntimeContexts.every(value => value.materialCode === item.materialCode
          && value.materialName === item.materialName)
          && itemPreparations.every(value => value.materialCode === item.materialCode
            && value.materialName === item.materialName)
        const quoteComparisonIds = [...new Set(itemBindings.map(binding => binding.quoteComparisonId))]
        const quoteMatches = quoteComparisonIds.length === item.quoteComparisonIds.length
          && quoteComparisonIds.every(id => item.quoteComparisonIds.includes(id))
          && itemRuntimeContexts.every(value => quoteComparisonIds.includes(value.quoteComparisonId))
          && itemPreparations.every(value => quoteComparisonIds.includes(value.quoteComparisonId))
        const preparationCandidates = [...new Map(itemPreparations.flatMap(preparation =>
          (preparation.supplierCandidates || []).map(candidate => [candidate.supplierCode, candidate]))).values()]
        const supplierMatches = item.supplierCandidates.length === preparationCandidates.length
          && item.supplierCandidates.every(candidate => preparationCandidates.some(source =>
            source.supplierCode === candidate.supplierCode
            && Number(source.quotePrice) === Number(candidate.quotePrice)))
        if (!materialMatches) errors.push(`MATERIAL_MISMATCH:${item.materialCode}`)
        if (!quoteMatches) errors.push(`QUOTE_COMPARISON_MISMATCH:${item.materialCode}`)
        if (!supplierMatches) errors.push(`SUPPLIER_CANDIDATE_MISMATCH:${item.materialCode}`)
        const priceApprovalIds = [...new Set(itemPreparations.map(value => value.priceApprovalId))]
        const priceApprovalNos = [...new Set(itemPreparations.map(value => value.priceApprovalNo))]
        const sourcePriceApprovalMatches = priceApprovalIds.length === item.sourcePriceApprovalIds.length
          && priceApprovalIds.every(id => item.sourcePriceApprovalIds.includes(id))
        if (!sourcePriceApprovalMatches) errors.push(`SOURCE_PRICE_APPROVAL_MISMATCH:${item.materialCode}`)
        const projected = { ...item, taskId: tasks[0].taskId, taskIds: frozen(tasks.map(task => task.taskId)),
          runtimeContextId: tasks[0].runtimeContextId,
          runtimeContextIds: frozen(tasks.map(task => task.runtimeContextId)),
          priceApprovalId: priceApprovalIds[0], priceApprovalIds: frozen(priceApprovalIds),
          sourcePriceApprovalIds: frozen(priceApprovalIds),
          priceApprovalNo: priceApprovalNos[0], priceApprovalNos: frozen(priceApprovalNos),
          quoteComparisonId: quoteComparisonIds[0], quoteComparisonIds: frozen(quoteComparisonIds),
          sourceRequestNo: itemPreparations[0].sourceRequestNo,
          sourceInquiryNo: itemPreparations[0].sourceInquiryNo,
          supplierCandidates: frozen(preparationCandidates),
          priceEvidence: frozen(itemPreparations.flatMap(preparation => [
            ...(preparation.priceEvidence || []), ...(preparation.historicalPriceEvidence || [])])),
          priceReferenceContexts: frozen(itemPreparations.flatMap(preparation =>
            preparation.priceReferenceRecords || [])),
          factScope: itemPreparations.every(value => value.factScope === 'real_price_approval_handoff')
            ? 'real_price_approval_handoff' : 'invalid' }
        if (projected.factScope !== 'real_price_approval_handoff' || hasForbiddenFact(projected)) {
          errors.push(`NON_PRODUCTION_FACT:${item.materialCode}`)
        }
        return frozen(projected)
      }).filter(Boolean)
      const priceApprovalIds = [...new Set(items.flatMap(item => item.priceApprovalIds))]
      const priceApprovalNos = [...new Set(items.flatMap(item => item.priceApprovalNos))]
      const sourceRequestNos = [...new Set(items.map(item => item.sourceRequestNo).filter(Boolean))]
      const sourceInquiryNos = [...new Set(items.map(item => item.sourceInquiryNo).filter(Boolean))]
      const complete = !errors.length && items.length === batch.items.length
        && priceApprovalIds.length === batch.sourcePriceApprovalBatch.length
        && batch.sourcePriceApprovalBatch.every(id => priceApprovalIds.includes(id))
        && batch.sourceQuoteComparisonBatch.every(id => items.some(item => item.quoteComparisonIds.includes(id)))
      if (!complete && !errors.length) errors.push('DECISION_BATCH_SOURCE_MISMATCH')
      return freeze({ result: complete ? 'PASS' : 'FAIL',
        error: errors.join('|'), entryTask: freeze({ taskId: entryTaskId,
          objectType: 'SupplierRecommendationDecisionBatchTask' }),
        batch: frozen({ ...batch, items }),
        purchaseContext: freeze({ sourceRequestNos: freeze(sourceRequestNos),
          sourceInquiryNos: freeze(sourceInquiryNos), priceApprovalIds: freeze(priceApprovalIds),
          priceApprovalNos: freeze(priceApprovalNos) }),
        items: freeze(items), sourcePriority: this.sourcePriority,
        factScope: complete ? 'real_price_approval_handoff' : 'blocked',
        businessWriteCount: 0, productionDataWritten: false,
        automaticRecommendationCount: 0, purchaseOrderCreated: false })
    },
  })
}

export const supplierRecommendationDataHandoffProviderV1142818 =
  createSupplierRecommendationDataHandoffProviderV1142818()
