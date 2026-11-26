import { createInquiryPreparationContext, validateInquiryPreparationContext,
  transitionInquiryPreparationState } from '../process/scm/inquiryPreparation/index.js'
import { assessInquiryPreparationCreation } from '../domain/scm/inquiryPreparation/inquiryPreparationRuleEngine.js'
import { evaluateInquiryPreparationCreationGuard } from '../domain/scm/inquiryPreparation/inquiryPreparationCreationGuard.js'

export const INQUIRY_PREPARATION_RUNTIME_VERSION = 'V1.14.2.8.7.9'
export const INQUIRY_PREPARATION_STORAGE_KEY = 'pce.scm.inquiry-preparations.v1142879'
export const INQUIRY_PREPARATION_CONTEXT_STORAGE_KEY = 'pce.scm.inquiry-preparation-contexts.v11428183'
let memoryObjects = []
let runtimeRevision = 0

const contextStorage = () => typeof window !== 'undefined' ? window.localStorage : null
const legacyStorage = () => typeof window !== 'undefined' ? window.sessionStorage : null

function normalizeStoredContext(object = {}) {
  if (object.objectType === 'InquiryPreparationContext') return object
  if (object.modelCode !== 'SCM_INQUIRY_PREPARATION_OBJECT' || !object.inquiryPreparationNo) return object
  const materialLines = object.materialLines || object.inquiryLines || []
  return Object.freeze({ ...object, objectType: 'InquiryPreparationContext',
    contextContractCode: 'SCM_INQUIRY_PREPARATION_CONTEXT',
    stateContractCode: 'SCM_INQUIRY_PREPARATION_STATE_CONTRACT',
    sourceObjectType: 'PurchaseRequest', sourceObjectId: object.sourceObjectId || object.sourceRequestNo,
    materialLines, requiredDate: object.requiredDate
      || materialLines.map(line => line.requiredDate).filter(Boolean).sort()[0] || '',
    preparationStatus: 'ready_for_inquiry', createdFrom: object.createdFrom || 'LEGACY_RUNTIME_CONTEXT_MIGRATION',
    createdAt: object.createdAt || 'legacy-session-runtime',
    sourceTrace: object.sourceTrace || Object.freeze({ sourceObjectType: 'PurchaseRequest',
      sourceObjectId: object.sourceRequestNo, sourceRequestNo: object.sourceRequestNo }),
    stateHistory: object.stateHistory || Object.freeze(['created', 'prepared', 'ready_for_inquiry']),
    inquiryCreated: false, supplierSent: false, quotationCreated: false,
    purchaseOrderCreated: false, productionDataWritten: false })
}

function readStorageList(target, key) {
  if (!target) return []
  try { return JSON.parse(target.getItem(key) || '[]') } catch { return [] }
}

function readObjects() {
  const storedContexts = readStorageList(contextStorage(), INQUIRY_PREPARATION_CONTEXT_STORAGE_KEY)
  const storedLegacy = readStorageList(legacyStorage(), INQUIRY_PREPARATION_STORAGE_KEY)
  const merged = new Map()
  ;[...storedLegacy, ...storedContexts, ...memoryObjects].forEach(item => {
    const normalized = normalizeStoredContext(item)
    const key = String(normalized?.inquiryPreparationNo || normalized?.sourceRequestNo || '')
    if (key) merged.set(key, normalized)
  })
  return [...merged.values()]
}
function writeObjects(objects) {
  memoryObjects = objects.map(normalizeStoredContext)
  runtimeRevision += 1
  try { contextStorage()?.setItem(INQUIRY_PREPARATION_CONTEXT_STORAGE_KEY, JSON.stringify(memoryObjects)) } catch { /* memory fallback */ }
  try { legacyStorage()?.setItem(INQUIRY_PREPARATION_STORAGE_KEY, JSON.stringify(memoryObjects)) } catch { /* compatibility fallback */ }
}

export function listInquiryPreparationObjects() { return Object.freeze(readObjects().map(item => Object.freeze(item))) }
export function listInquiryPreparationContexts() {
  return Object.freeze(listInquiryPreparationObjects().filter(item => item.objectType === 'InquiryPreparationContext'))
}
export function readInquiryPreparationContextSnapshot() {
  const objects = listInquiryPreparationContexts()
  const identity = objects.map(item => `${item.inquiryPreparationNo}:${item.sourceRequestNo}`).sort().join('|')
  return Object.freeze({ snapshotId: `INQUIRY_PREPARATION_CONTEXT_SNAPSHOT:${objects.length}:${identity}`,
    revision: runtimeRevision, recordCount: objects.length, objects,
    storageLocation: typeof window === 'undefined' ? 'memory_runtime' : 'browser_local_context_store' })
}
export function readInquiryPreparationRuntimeSnapshot() {
  return readInquiryPreparationContextSnapshot()
}
export function findInquiryPreparationBySource(sourceRequestNo) {
  return listInquiryPreparationObjects().find(item => item.sourceRequestNo === String(sourceRequestNo || '')) || null
}
export function createInquiryPreparation(request = {}) {
  const assessment = assessInquiryPreparationCreation(request)
  const guard = evaluateInquiryPreparationCreationGuard({ action: 'createInquiryPreparation', request })
  if (!assessment.eligible || !guard.allowed) return Object.freeze({ result: 'FAIL', created: false, assessment, guard, object: null })
  const existing = findInquiryPreparationBySource(request.requestNo || request.sourceRequestNo)
  if (existing) return Object.freeze({ result: 'PASS', created: false, idempotent: true, assessment, guard, object: existing,
    businessWriteCount: 0, productionDataWritten: false, database: 'UNCHANGED' })
  const createdContext = createInquiryPreparationContext(request)
  if (!validateInquiryPreparationContext(createdContext).valid) {
    return Object.freeze({ result: 'FAIL', created: false, assessment, guard, object: null,
      reason: 'INQUIRY_PREPARATION_CONTEXT_INVALID' })
  }
  const preparedContext = transitionInquiryPreparationState(createdContext, 'prepared')
  const object = transitionInquiryPreparationState(preparedContext, 'ready_for_inquiry')
  writeObjects([...readObjects(), object])
  return Object.freeze({ result: 'PASS', created: true, idempotent: false, assessment, guard, object,
    businessWriteCount: 1, productionDataWritten: false, database: 'UNCHANGED' })
}

export function createInquiryPreparationsBatch(requests = []) {
  const input = Array.isArray(requests) ? requests : []
  const results = Object.freeze(input.map(request => createInquiryPreparation(request)))
  const objects = Object.freeze(results.filter(item => item.result === 'PASS').map(item => item.object))
  const failures = Object.freeze(results.filter(item => item.result !== 'PASS'))
  const valid = input.length > 0 && objects.length === input.length
    && new Set(objects.map(item => item.sourceRequestNo)).size === input.length
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid, inputCount: input.length,
    outputCount: objects.length, objects, failures, snapshot: readInquiryPreparationRuntimeSnapshot() })
}
