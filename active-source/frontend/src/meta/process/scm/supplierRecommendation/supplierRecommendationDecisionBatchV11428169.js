import { canPerformAction } from '../../../runtime/permissionEngine.js'
import { executeSupplierRecommendationBatchTaskEntryV11428167,
  supplierRecommendationTaskStoreV11428167 } from './supplierRecommendationTaskRuntimeV11428167.js'

export const SUPPLIER_RECOMMENDATION_DECISION_BATCH_VERSION_V11428169 = 'V1.14.2.8.18.16.9'
export const SUPPLIER_RECOMMENDATION_DECISION_REOPEN_VERSION_V11428202 = 'V1.14.2.8.18.20.2'
export const SUPPLIER_RECOMMENDATION_DECISION_REVISION_VERSION_V11428203 = 'V1.14.2.8.18.20.3'
export const SUPPLIER_RECOMMENDATION_DECISION_BATCH_STORAGE_KEY_V11428169 =
  'pce.scm.supplier-recommendation.decision-batch.v11428169'

const text = value => String(value ?? '').trim()
const clone = value => JSON.parse(JSON.stringify(value))
const freeze = value => Object.freeze(value)
const frozen = value => freeze(clone(value))
const browserStorage = () => typeof window !== 'undefined' ? window.localStorage : null
const memoryState = { batches: [], bindings: [], results: [], handoffs: [], reopenAudits: [], activeBatchId: '' }
const uniqueBy = (values, keyOf) => [...new Map(values.map(value => [keyOf(value), value])).values()]

const mergeSupplierCandidates = inputs => {
  const values = new Map()
  for (const input of inputs) for (const candidate of input.supplierCandidates || []) {
    const supplierCode = text(candidate.supplierCode)
    if (!supplierCode) continue
    const current = values.get(supplierCode) || { ...candidate, quoteComparisonIds: [] }
    current.quoteComparisonIds = [...new Set([...(current.quoteComparisonIds || []),
      text(input.quoteComparisonId)].filter(Boolean))]
    values.set(supplierCode, current)
  }
  return [...values.values()]
}

const mergeMaterialInputs = inputs => {
  const source = inputs[0] || {}
  const sourcePriceApprovalIds = [...new Set(inputs.map(input => text(input.priceApprovalId)).filter(Boolean))]
  const quoteComparisonIds = [...new Set(inputs.map(input => text(input.quoteComparisonId)).filter(Boolean))]
  const priceEvidence = uniqueBy(inputs.flatMap(input => (input.priceEvidence || []).map(evidence => ({
    ...evidence, quoteComparisonId: text(evidence.quoteComparisonId || input.quoteComparisonId),
  }))), evidence => `${text(evidence.quoteComparisonId)}::${text(evidence.supplierCode)}::${evidence.currentPrice ?? ''}`)
  const historicalPriceEvidence = uniqueBy(inputs.flatMap(input => input.historicalPriceEvidence || []),
    evidence => `${text(evidence.supplierCode)}::${JSON.stringify(evidence.priceReferenceContext || evidence)}`)
  const priceReferenceRecords = uniqueBy(inputs.flatMap(input => input.priceReferenceRecords || []),
    record => `${text(record.materialCode || source.materialCode)}::${text(record.supplierCode)}::${record.currentQuote ?? ''}`)
  return { ...source, sourcePriceApprovalIds, quoteComparisonIds,
    supplierCandidates: mergeSupplierCandidates(inputs),
    priceEvidence, historicalPriceEvidence, priceReferenceRecords }
}

const aggregateInputsBy = (inputs, keyOf) => [...inputs.reduce((groups, input) => {
  const key = keyOf(input)
  if (!groups.has(key)) groups.set(key, [])
  groups.get(key).push(input)
  return groups
}, new Map()).values()].map(mergeMaterialInputs)

export function createSupplierRecommendationDecisionItemV11428169(input = {}) {
  const materialCode = text(input.materialCode)
  const materialName = text(input.materialName)
  const sourcePriceApprovalIds = [...new Set((input.sourcePriceApprovalIds || [input.priceApprovalId])
    .map(text).filter(Boolean))]
  const quoteComparisonIds = [...new Set((input.quoteComparisonIds || [input.quoteComparisonId])
    .map(text).filter(Boolean))]
  const supplierCandidates = Array.isArray(input.supplierCandidates) ? input.supplierCandidates : []
  const priceEvidence = [...(input.priceEvidence || []), ...(input.historicalPriceEvidence || [])]
  if (!materialCode || !materialName || !sourcePriceApprovalIds.length || !quoteComparisonIds.length
    || !supplierCandidates.length || !priceEvidence.length) {
    throw new Error('SUPPLIER_RECOMMENDATION_DECISION_ITEM_INCOMPLETE')
  }
  return freeze({
    decisionItemId: text(input.decisionItemId)
      || `SRDI-${sourcePriceApprovalIds.join('-')}-${materialCode}`,
    materialCode,
    materialName,
    sourcePriceApprovalIds: freeze(sourcePriceApprovalIds),
    quoteComparisonIds: freeze(quoteComparisonIds),
    supplierCandidates: frozen(supplierCandidates),
    priceEvidence: frozen(priceEvidence),
    decisionSupplier: null,
    decisionReason: '',
    selectedSupplierCode: '',
    selectedSupplierName: '',
    selectionReason: '',
    reviewStatus: 'manual_review',
    reviewer: '',
    reviewedAt: '',
    status: 'pending_manual_decision',
  })
}

export function createSupplierRecommendationDecisionBatchV11428169(inputs = [], batchId = '') {
  if (!inputs.length) throw new Error('SUPPLIER_RECOMMENDATION_DECISION_BATCH_EMPTY')
  const materialInputs = aggregateInputsBy(inputs, input => text(input.materialCode))
  const items = materialInputs.map(createSupplierRecommendationDecisionItemV11428169)
  const sourcePriceApprovalBatch = [...new Set(inputs.map(item => text(item.priceApprovalId)).filter(Boolean))]
  const sourceQuoteComparisonBatch = [...new Set(inputs.map(item => text(item.quoteComparisonId)).filter(Boolean))]
  if (!sourcePriceApprovalBatch.length || !sourceQuoteComparisonBatch.length) {
    throw new Error('SUPPLIER_RECOMMENDATION_DECISION_BATCH_SOURCE_INCOMPLETE')
  }
  return freeze({
    batchId: text(batchId) || `SRDB-${sourcePriceApprovalBatch.join('-')}`,
    sourcePriceApprovalBatch: freeze(sourcePriceApprovalBatch),
    sourceQuoteComparisonBatch: freeze(sourceQuoteComparisonBatch),
    items: freeze(items),
  })
}

export function createSupplierRecommendationDecisionBatchStoreV11428169({
  storage = browserStorage(), storageKey = SUPPLIER_RECOMMENDATION_DECISION_BATCH_STORAGE_KEY_V11428169,
} = {}) {
  const empty = () => ({ batches: [], bindings: [], results: [], handoffs: [], reopenAudits: [], activeBatchId: '' })
  const normalize = value => {
    const state = { ...empty(), ...value }
    const revisions = new Map()
    state.results = (state.results || []).map((result, index) => {
      const current = revisions.get(result.batchId) || 0
      const revision = Number(result.decisionRevision) > 0 ? Number(result.decisionRevision)
        : result.status === 'confirmed' ? current + 1 : current
      revisions.set(result.batchId, Math.max(current, revision))
      return { ...result, decisionRevision: revision,
        resultEventSequence: Number(result.resultEventSequence) || index + 1 }
    })
    return state
  }
  const read = () => {
    if (!storage) return normalize(clone(memoryState))
    try {
      const value = JSON.parse(storage.getItem(storageKey) || 'null')
      return value && Array.isArray(value.batches) ? normalize(value) : empty()
    } catch { return empty() }
  }
  const write = state => {
    Object.assign(memoryState, clone(state))
    storage?.setItem(storageKey, JSON.stringify(state))
    return clone(state)
  }
  const saveBatch = (batch, bindings = []) => {
    const state = read()
    state.batches = state.batches.filter(item => item.batchId !== batch.batchId)
    state.bindings = state.bindings.filter(item => item.batchId !== batch.batchId)
    state.batches.push(clone(batch))
    state.bindings.push(...clone(bindings))
    state.activeBatchId = batch.batchId
    write(state)
    return frozen(batch)
  }
  return freeze({
    list: () => read().batches,
    findById: batchId => read().batches.find(item => item.batchId === text(batchId)) || null,
    listBindings: batchId => read().bindings.filter(item => item.batchId === text(batchId)),
    findResult: batchId => [...read().results].reverse()
      .find(item => item.batchId === text(batchId)) || null,
    listResults: batchId => read().results.filter(item => item.batchId === text(batchId)),
    listResultRevisions: batchId => read().results.filter(item => item.batchId === text(batchId)
      && item.status === 'confirmed'),
    findHandoff: batchId => read().handoffs.find(item => item.batchId === text(batchId)) || null,
    listReopenAudits: batchId => read().reopenAudits.filter(item => item.batchId === text(batchId)),
    activeBatchId: () => read().activeBatchId,
    saveBatch,
    updateItem(batchId, materialCode, changes = {}) {
      const batch = this.findById(batchId)
      if (!batch) throw new Error('SUPPLIER_RECOMMENDATION_DECISION_BATCH_NOT_FOUND')
      const items = batch.items.map(item => item.materialCode === text(materialCode)
        ? { ...item, ...clone(changes) } : item)
      return saveBatch(freeze({ ...batch, items: frozen(items) }), this.listBindings(batchId))
    },
    saveResult(result) {
      const state = read()
      const batchResults = state.results.filter(item => item.batchId === result.batchId)
      const currentRevision = batchResults.reduce((maximum, item) =>
        Math.max(maximum, Number(item.decisionRevision) || 0), 0)
      const decisionRevision = result.status === 'confirmed'
        ? Number(result.decisionRevision) || currentRevision + 1
        : Number(result.decisionRevision) || currentRevision
      const versioned = { ...clone(result), decisionRevision,
        resultEventSequence: batchResults.length + 1,
        previousDecisionRevision: currentRevision || null }
      state.results.push(versioned); write(state); return frozen(versioned)
    },
    saveHandoff(handoff) {
      const state = read()
      state.handoffs = state.handoffs.filter(item => item.batchId !== handoff.batchId)
      state.handoffs.push(clone(handoff)); state.activeBatchId = handoff.batchId
      write(state); return frozen(handoff)
    },
    markActive(batchId) {
      if (!this.findById(batchId)) return freeze({ result: 'FAIL', error: 'DECISION_BATCH_NOT_FOUND' })
      const state = read(); state.activeBatchId = text(batchId); write(state)
      return freeze({ result: 'PASS', batchId: text(batchId) })
    },
    reopenItem(batchId, materialCode, { reopenedBy = '', reopenedAt = new Date().toISOString() } = {}) {
      const state = read()
      const batchIndex = state.batches.findIndex(item => item.batchId === text(batchId))
      const source = state.batches[batchIndex]
      const sourceItem = source?.items.find(item => item.materialCode === text(materialCode))
      if (!source || !sourceItem || sourceItem.reviewStatus !== 'confirmed'
        || sourceItem.status !== 'confirmed') {
        throw new Error('CONFIRMED_DECISION_ITEM_REQUIRED')
      }
      const transitions = [
        { from: 'confirmed', to: 'reopen_review', at: reopenedAt, by: text(reopenedBy) },
        { from: 'reopen_review', to: 'manual_review', at: reopenedAt, by: text(reopenedBy) },
      ]
      const items = source.items.map(item => item.materialCode === text(materialCode) ? {
        ...item, reviewStatus: 'manual_review', reviewer: '', reviewedAt: '',
        status: 'pending_manual_decision', reopenStatus: 'reopen_review',
        reopenTransitions: [...(item.reopenTransitions || []), ...transitions],
      } : item)
      const reopenedBatch = { ...source, items }
      state.batches.splice(batchIndex, 1, reopenedBatch)
      const latestResult = [...state.results].reverse().find(item => item.batchId === text(batchId))
      if (latestResult) state.results.push({
        ...latestResult, items, status: 'reopen_review',
        reopenedMaterialCode: text(materialCode), reopenedBy: text(reopenedBy), reopenedAt,
        resultEventSequence: state.results.filter(item => item.batchId === text(batchId)).length + 1,
        purchaseOrderCreated: false,
      })
      const handoffIndex = state.handoffs.findIndex(item => item.batchId === text(batchId))
      if (handoffIndex >= 0) state.handoffs.splice(handoffIndex, 1, {
        ...state.handoffs[handoffIndex], status: 'reopen_review',
        reopenedMaterialCode: text(materialCode), reopenedBy: text(reopenedBy), reopenedAt,
        purchaseOrderCreated: false,
      })
      const audit = { auditId: `SR-REOPEN-${text(batchId)}-${text(materialCode)}-${state.reopenAudits.length + 1}`,
        batchId: text(batchId), materialCode: text(materialCode), reopenedBy: text(reopenedBy),
        reopenedAt, transitions, result: 'PASS', purchaseOrderCreated: false }
      state.reopenAudits.push(audit)
      state.activeBatchId = text(batchId)
      write(state)
      return freeze({ batch: frozen(reopenedBatch), item: frozen(items.find(item =>
        item.materialCode === text(materialCode))), audit: frozen(audit) })
    },
    buildPageUrl() {
      const batchId = read().activeBatchId
      return batchId ? `/scm/supplier-recommendations?decisionBatchId=${encodeURIComponent(batchId)}` : ''
    },
    clear: () => write(empty()),
  })
}

export const supplierRecommendationDecisionBatchStoreV11428169 =
  createSupplierRecommendationDecisionBatchStoreV11428169()

export function executeSupplierRecommendationDecisionBatchEntryV11428169(inputs = [], options = {}) {
  try {
    const values = Array.isArray(inputs) ? inputs : [inputs]
    const entryInputs = aggregateInputsBy(values, input => [text(input.priceApprovalId),
      text(input.quoteComparisonId), text(input.materialCode)].join('::'))
    const batchStore = options.decisionBatchStore || supplierRecommendationDecisionBatchStoreV11428169
    const taskResult = executeSupplierRecommendationBatchTaskEntryV11428167(entryInputs, options)
    if (taskResult.result !== 'PASS') return freeze({ ...taskResult, decisionBatches: freeze([]) })
    const sourceTasks = taskResult.batches.flatMap(group => group.tasks)
    const batchInputs = sourceTasks.map(task => entryInputs.find(input =>
      text(input.priceApprovalId) === task.sourcePriceApprovalId
      && text(input.materialCode) === task.materialCode
      && text(input.quoteComparisonId) === task.quoteComparisonId))
    if (batchInputs.some(item => !item)) throw new Error('DECISION_BATCH_INPUT_BINDING_MISSING')
    const batch = createSupplierRecommendationDecisionBatchV11428169(batchInputs)
    const bindings = sourceTasks.map(task => ({ batchId: batch.batchId, materialCode: task.materialCode,
      taskId: task.taskId, runtimeContextId: task.runtimeContextId,
      priceApprovalId: task.sourcePriceApprovalId, quoteComparisonId: task.quoteComparisonId }))
    const decisionBatches = freeze([batchStore.saveBatch(batch, bindings)])
    return freeze({ result: 'PASS', decisionBatches: freeze(decisionBatches),
      activeBatch: decisionBatches[0], taskCount: taskResult.taskCount,
      sourceRowCount: values.length,
      materialCount: new Set(values.map(value => text(value.materialCode))).size,
      decisionItemCount: decisionBatches.reduce((count, batch) => count + batch.items.length, 0),
      batchSourceTaskCount: bindings.length,
      diagnostics: freeze({ selectedRowsCount: values.length,
        taskCreationCount: taskResult.taskCount, batchSourceTaskCount: bindings.length,
        decisionItemCount: decisionBatches[0].items.length }),
      navigationTarget: '/scm/supplier-recommendations', productionDataWritten: false,
      purchaseOrderCreated: false })
  } catch (error) {
    return freeze({ result: 'FAIL', error: error.message, decisionBatches: freeze([]),
      productionDataWritten: false, purchaseOrderCreated: false })
  }
}

export function executeSelectDecisionBatchSupplierV11428169(batchId, materialCode, supplierCode, reason,
  { store = supplierRecommendationDecisionBatchStoreV11428169, permissionContext = {} } = {}) {
  if (!canPerformAction(permissionContext.role, 'EXECUTE')) {
    return freeze({ result: 'FAIL', error: 'ACTION_PERMISSION_DENIED' })
  }
  const batch = store.findById(batchId)
  const item = batch?.items.find(value => value.materialCode === text(materialCode))
  const supplier = item?.supplierCandidates.find(value => value.supplierCode === text(supplierCode))
  if (!item || !supplier || !text(reason) || !item.priceEvidence.length || item.status === 'confirmed') {
    return freeze({ result: 'FAIL', error: 'DECISION_ITEM_ACTION_NOT_EXECUTABLE' })
  }
  const updated = store.updateItem(batchId, materialCode, { decisionSupplier: supplier,
    decisionReason: text(reason), selectedSupplierCode: supplier.supplierCode,
    selectedSupplierName: supplier.supplierName, selectionReason: text(reason),
    reviewStatus: 'manual_review', reviewer: '', reviewedAt: '', status: 'selected' })
  return freeze({ result: 'PASS', batch: updated,
    item: updated.items.find(value => value.materialCode === text(materialCode)) })
}

export function executeReopenSupplierRecommendationDecisionItemV11428202(batchId, materialCode, input = {},
  { store = supplierRecommendationDecisionBatchStoreV11428169,
    taskStore = supplierRecommendationTaskStoreV11428167, permissionContext = {},
    now = new Date().toISOString() } = {}) {
  if (!canPerformAction(permissionContext.role, 'EXECUTE')) {
    return freeze({ result: 'FAIL', error: 'ACTION_PERMISSION_DENIED', purchaseOrderCreated: false })
  }
  const reopenedBy = text(input.reopenedBy || permissionContext.userName || permissionContext.user?.name
    || permissionContext.userId || permissionContext.role)
  if (!reopenedBy) return freeze({ result: 'FAIL', error: 'REOPEN_REVIEWER_REQUIRED',
    purchaseOrderCreated: false })
  try {
    const reopened = store.reopenItem(batchId, materialCode, { reopenedBy, reopenedAt: now })
    for (const binding of store.listBindings(batchId).filter(item =>
      item.materialCode === text(materialCode))) {
      if (taskStore.findById(binding.taskId)) taskStore.update(binding.taskId,
        { status: 'manual_review', currentAssignee: reopenedBy })
    }
    return freeze({ result: 'PASS', ...reopened, stateTransitions: frozen([
      'confirmed -> reopen_review', 'reopen_review -> manual_review']),
      purchaseOrderCreated: false })
  } catch (error) {
    return freeze({ result: 'FAIL', error: error.message, purchaseOrderCreated: false })
  }
}

export function executeConfirmSupplierRecommendationDecisionBatchV11428169(batchId, input = {},
  { store = supplierRecommendationDecisionBatchStoreV11428169, taskStore = supplierRecommendationTaskStoreV11428167,
    permissionContext = {}, now = new Date().toISOString() } = {}) {
  if (!canPerformAction(permissionContext.role, 'EXECUTE')) {
    return freeze({ result: 'FAIL', error: 'ACTION_PERMISSION_DENIED' })
  }
  const batch = store.findById(batchId)
  const confirmedBy = text(input.confirmedBy)
  if (!batch || !confirmedBy || !batch.items.length || batch.items.some(item =>
    !['selected', 'confirmed'].includes(item.status) || !item.decisionSupplier?.supplierCode
      || !text(item.decisionReason))) {
    return freeze({ result: 'FAIL', error: 'DECISION_BATCH_CONFIRMATION_INCOMPLETE' })
  }
  const items = batch.items.map(item => ({ ...item,
    objectType: 'SupplierRecommendationDecision',
    decisionId: `SRD-${item.decisionItemId || `${batch.batchId}-${item.materialCode}`}`,
    selectedSupplierCode: item.selectedSupplierCode || item.decisionSupplier.supplierCode,
    selectedSupplierName: item.selectedSupplierName || item.decisionSupplier.supplierName,
    selectionReason: item.selectionReason || item.decisionReason,
    reviewStatus: 'confirmed', reviewer: confirmedBy, reviewedAt: now,
    status: 'confirmed' }))
  store.saveBatch(freeze({ ...batch, items: frozen(items) }), store.listBindings(batchId))
  const result = store.saveResult({ objectType: 'SupplierRecommendationDecisionBatchResult',
    batchId: batch.batchId, items: frozen(items), confirmedBy, confirmedAt: now,
    status: 'confirmed', purchaseOrderCreated: false })
  for (const binding of store.listBindings(batchId)) {
    if (taskStore.findById(binding.taskId)) taskStore.update(binding.taskId,
      { status: 'confirmed', currentAssignee: confirmedBy })
  }
  const handoff = store.saveHandoff({ objectType: 'SupplierRecommendationDecisionBatchGateHandoff',
    batchId: batch.batchId, resultId: `SRDBR-${batch.batchId}-R${result.decisionRevision}`,
    decisionRevision: result.decisionRevision, items: frozen(items.map(item => ({
      materialCode: item.materialCode, materialName: item.materialName,
      supplierCode: item.selectedSupplierCode, supplierName: item.selectedSupplierName,
      decisionReason: item.selectionReason, selectionReason: item.selectionReason,
      reviewer: item.reviewer, reviewedAt: item.reviewedAt }))), confirmedBy, confirmedAt: now,
    status: 'handoff_ready', purchaseOrderCreated: false })
  return freeze({ result: 'PASS', decisionBatchResult: result, handoff })
}
