import { readPceFactLoadEnvelope, factLoadFailureFromError } from './pceFactLoadContract.js'
import { resolvePceOperationResourceActions } from './pceBusinessActionRegistry.js'
import { createOperationResourcePendingStore } from './operationResourcePendingIntent.js'
import { assertOperationSelectedDetailDirectory, latestOwnFormalLocation } from './operationSelectedDetailContract.js'

export const OPERATION_RESOURCE_API = '/api/planning/operation-resources/'
export const OPERATION_RESOURCE_CONTRACT = 'PCE-PRODUCTION-OPERATION-RESOURCE-SELECTION-V1'
const id = value => Number.isSafeInteger(value) && value > 0
const count = value => Number.isSafeInteger(value) && value >= 0
const text = value => typeof value === 'string' && !!value.trim()
const hash = value => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value)
export const canonicalOperationResource = value => JSON.stringify(value, (_, item) => item && typeof item === 'object' && !Array.isArray(item)
  ? Object.fromEntries(Object.keys(item).sort().map(key => [key, item[key]])) : item)
const same = (a, b) => canonicalOperationResource(a) === canonicalOperationResource(b)
function requireFact(condition, message) { if (!condition) throw new Error(message) }
function proofVersion(proof) { return proof?.projectionVersion ?? proof?.version }

export function validateOperationResourceResponse(response, expected) {
  const { data, factLoadFacts } = readPceFactLoadEnvelope(response, expected.apiUrl || OPERATION_RESOURCE_API, '执行资源选择与逐工序接收')
  const facts = data.operationResourceFacts
  requireFact(['loaded', 'empty_valid', 'success'].includes(factLoadFacts.factLoadStatus)
    && facts?.contractVersion === OPERATION_RESOURCE_CONTRACT && facts.moduleCode === 'production-work-order'
    && facts.factSource === 'server' && facts.currentStateSource === 'server'
    && facts.companyId === expected.companyId && facts.workOrderId === expected.workOrderId
    && facts.currentActorEvidence?.companyId === expected.companyId
    && facts.currentActorEvidence?.userId === expected.userId && text(facts.currentActorEvidence.username)
    && Array.isArray(facts.operations) && data.resultCount === facts.operations.length,
  '执行资源后台身份、公司、工单或正式事实不一致。')
  if (expected.readOnly !== false) requireFact(data.businessWriteCount === 0 && data.auditWriteCount === 0
    && data.stateTransitionWriteCount === 0, '只读资源回查返回了业务写入变化，已停止使用。')
  const suggested=latestOwnFormalLocation(facts, expected),expectedOperationId=expected.operationId||suggested?.operationId||null
  assertOperationSelectedDetailDirectory(facts, expectedOperationId)
  for (const row of facts.operations) {
    requireFact(id(row.operationId) && row.workOrderId === facts.workOrderId
      && ['operationName', 'workOrderNo', 'statusLabel'].every(key => text(row[key]))
      && hash(row.workOrderSnapshotHash) && hash(row.operationSnapshotHash)
      && count(row.workOrderVersion) && count(row.selectionVersion) && count(row.receiptVersion)
      && (hash(row.currentResourceHash) || row.currentResourceHash === null && !row.selectionFact)
      && Array.isArray(row.blockingReasons) && row.blockingReasons.every(text)
      && Array.isArray(row.candidateWorkCenters), '本工序资源、接收、版本或具体准入事实未完整读取。')
    requireFact(row.candidateWorkCenters.every(option => id(option.id) && text(option.name)
      && id(option.workshopId) && text(option.workshopName) && hash(option.candidateSnapshotHash)
      && typeof option.enabled === 'boolean' && Array.isArray(option.blockingReasons)
      && option.blockingReasons.every(text)), '正式工作中心候选的公司、车间、能力或范围依据不完整。')
    for (const [field, version] of [['resourceSelectionProof', row.selectionVersion], ['preciseReceiptProof', row.receiptVersion]]) {
      const proof = row[field]
      if (proof) requireFact(id(proof.id) && proof.companyId === facts.companyId && proof.workOrderId === row.workOrderId
        && proof.operationId === row.operationId && proofVersion(proof) === version
        && (proof.version === undefined || proof.version === proofVersion(proof)) && id(proof.actorId)
        && ['proofHash', 'requestHash', 'requestKeyHash'].every(key => hash(proof[key]))
        && ['reason', 'actorLabel', 'confirmedAt', 'timeLabel', 'auditReference', 'statusLabel'].every(key => text(proof[key]))
        && proof.stateMachineConsistent === true && Array.isArray(proof.statusTransitionHistory)
        && proof.statusTransitionCount === proof.statusTransitionHistory.length,
      '正式选择或精确接收证明与本公司、本工单、本工序或审计不一致。')
    }
    if (row.selectionFact?.proofType === 'FROZEN_ORDER_RESOURCE') requireFact(row.selectionVersion === 0
      && !row.resourceSelectionProof && id(row.selectionFact.workCenterId), '原冻结资源不能冒充新资源选择记录。')
    requireFact((row.resourceSelectionProof || row.selectionVersion === 0) && (row.preciseReceiptProof || row.receiptVersion === 0),
      '资源或精确接收版本缺少对应正式证明，当前结果待核实。')
    const actions = resolvePceOperationResourceActions(row)
    requireFact(!row.resourceSelectionProof || !actions.selectResource.enabled, '已选择的同一记录不得再次选择资源。')
    requireFact(!row.preciseReceiptProof || !actions.receiveOperation.enabled, '已精确接收的同一记录不得再次接收。')
  }
  const selected = expectedOperationId ? facts.operations.find(row => row.operationId === expectedOperationId) : null
  requireFact(same(facts.selectedOperation, selected || null), '当前工序与明确选择不一致。')
  if (selected && expected.workCenterId) requireFact(selected.candidateWorkCenters.some(row => row.id === expected.workCenterId),
    '所选工作中心不属于本次正式候选范围。')
  for (const surface of ['apiFacts', 'pageFacts', 'diagnosticFacts', 'strictFacts', 'acceptanceFacts'])
    requireFact(same(data[surface]?.operationResourceFacts, facts), '资源选择服务端五面事实不一致。')
  return { facts, factLoadFacts }
}

export function createOperationResourceState() {
  return { workOrderId: '', operationId: '', workCenterId: '', reason: '', facts: null, lastDisplayFacts: null,
    factLoadFacts: null, readState: 'idle', writeState: 'idle', message: '', error: '', pendingActionLabel: '', pendingIntent: null,
    recoveryJournalError: '', allowLatestFormalLocation: false }
}
async function digest(value) {
  const bytes = await globalThis.crypto.subtle.digest('SHA-256', new TextEncoder().encode(value))
  return Array.from(new Uint8Array(bytes), byte => byte.toString(16).padStart(2, '0')).join('')
}
export function createOperationResourceController({ state, api, owner, companyId, userId, externalLocked = () => false,
  pendingStore = createOperationResourcePendingStore(), onFactsChanged = () => {} }) {
  let sequence = 0, generation = 0, factOwner = null, writing = false, pending = null, inFlight = null
  const journalOwner = () => JSON.stringify([Number(companyId()), Number(userId())])
  function invalidate() { sequence++; generation++; factOwner = null; pending = null; Object.assign(state, createOperationResourceState()) }
  function describePending() {
    state.pendingActionLabel = pending ? pending.key === 'selectResource' ? '正式资源选择' : '本工序精确接收' : ''
    state.pendingIntent = pending ? { actionCode: pending.actionCode, workOrderId: pending.workOrderId, operationId: pending.operationId,
      selectionVersion: pending.selectionVersion, receiptVersion: pending.receiptVersion,
      requestKeyHash: pending.requestKeyHash, requestHash: pending.requestHash } : null
  }
  function clearPending() { if (pending) pendingStore.remove(pending); pending = null; describePending() }
  function recoverPending() {
    try { const saved = state.workOrderId ? pendingStore.read(journalOwner(), Number(state.workOrderId)) : null
      state.recoveryJournalError = ''
      if (saved && !pending) { pending = { ...saved, transportOwner: owner() }; state.operationId = String(saved.operationId); state.writeState = 'readback_pending'; describePending() }
    } catch (error) { state.recoveryJournalError = `防重复恢复标识待核实，只能只读核查，不能发起新提交。${error.message || ''}` }
  }
  function assessment(key) {
    const row = state.facts?.selectedOperation, action = row ? resolvePceOperationResourceActions(row)[key] : null
    const candidate = row?.candidateWorkCenters.find(item => item.id === Number(state.workCenterId))
    const checks = { currentOwner: factOwner === null || factOwner === owner(), unlocked: !externalLocked(), notPending: !writing && !pending,
      recoveryJournalReady: !state.recoveryJournalError,
      readComplete: state.readState === 'loaded' && !!state.facts, operationPresent: !!row,
      resourceExplicit: key !== 'selectResource' || !!state.workCenterId && !!candidate,
      serverAllowed: action?.enabled === true, secure: !!globalThis.crypto?.randomUUID && !!globalThis.crypto?.subtle,
      reasonValid: state.reason.trim().length >= 2 && state.reason.trim().length <= 240 }
    const messages = [['currentOwner', '账号或公司已变化，请重新读取本人事实。'],
      ['unlocked', '接收或归属承接正在处理，请先完成其只读回查。'],
      ['notPending', `${state.pendingActionLabel || '本次资源操作'}结果待核实，请仅重新读取，不重复提交。`],
      ['recoveryJournalReady', state.recoveryJournalError],
      ['readComplete', state.readState === 'loading' ? '正在读取正式资源及接收事实。' : '请重新读取本次正式资源事实。'],
      ['operationPresent', '请明确选择本工单工序。'],
      ['serverAllowed', action?.disabledReason || '当前正式资源或接收条件尚未满足。'],
      ['resourceExplicit', '请明确选择本次正式候选工作中心。'],
      ['secure', '当前环境无法建立安全防重复标识，请重新进入正式页面。'],
      ['reasonValid', '请填写2至240字的真实资源选择或接收原因。']]
    const first = messages.find(([name]) => !checks[name])
    return { action, checks, enabled: !first, disabledReason: first?.[1] || '', blockingCode: first?.[0] || '' }
  }
  function load({ force = false } = {}) {
    if (writing) return Promise.resolve(false)
    if (factOwner && factOwner !== owner() || pending && pending.transportOwner !== owner()) { invalidate(); return Promise.resolve(false) }
    recoverPending()
    const key = JSON.stringify([owner(), generation, state.workOrderId, state.operationId, state.workCenterId, pending?.requestHash,state.allowLatestFormalLocation])
    if (!force && inFlight?.key === key) return inFlight.promise
    const promise = loadCurrent(), item = { key, promise }; inFlight = item
    promise.then(() => { if (inFlight === item) inFlight = null }, () => { if (inFlight === item) inFlight = null })
    return promise
  }
  async function loadCurrent() {
    if (writing) return false
    if (factOwner && factOwner !== owner() || pending && pending.transportOwner !== owner()) { invalidate(); return false }
    recoverPending()
    const request = ++sequence, epoch = generation, identity = owner(), order = state.workOrderId,
      operation = state.operationId, center = state.workCenterId,allowLatest=state.allowLatestFormalLocation&&!pending&&!operation
    const current = () => { if (identity !== owner() && epoch === generation) invalidate()
      return request === sequence && epoch === generation && identity === owner()
        && order === state.workOrderId && operation === state.operationId && center === state.workCenterId }
    const previous = state.factLoadFacts
    if (state.facts) state.lastDisplayFacts = state.facts
    Object.assign(state, { facts: null, factLoadFacts: null, readState: 'loading', error: '',
      message: pending ? '结果待核实，请仅重新读取正式证明。' : '' })
    try {
      const response = await api.read({ ...(order ? { workOrderId: Number(order) } : {}),
        ...(operation ? { operationId: Number(operation) } : {}), ...(center ? { workCenterId: Number(center) } : {}),
        ...(allowLatest?{locateOwnLatestFormalAction:1}:{}),
        ...(pending ? { actionCode: pending.actionCode, selectionVersion: pending.selectionVersion,
          receiptVersion: pending.receiptVersion, requestHash: pending.requestHash, requestKeyHash: pending.requestKeyHash } : {}) })
      if (!current()) return false
      const validated=validateOperationResourceResponse(response, { companyId: Number(companyId()), userId: Number(userId()),allowLatestFormalLocation:allowLatest,
        workOrderId: order ? Number(order) : null, operationId: operation ? Number(operation) : null,
        workCenterId: center ? Number(center) : null })
      if(allowLatest&&validated.facts.viewLocationSuggestion)state.operationId=String(validated.facts.viewLocationSuggestion.operationId)
      Object.assign(state,validated,{ readState: 'loaded', lastDisplayFacts: null })
      if(allowLatest)state.message=validated.facts.viewLocationStatusLabel||validated.facts.viewLocationSuggestion?.statusLabel||''
      factOwner = identity
      if (pending) {
        const row = state.facts.selectedOperation, proof = row?.[pending.key === 'selectResource' ? 'resourceSelectionProof' : 'preciseReceiptProof']
        const result = state.facts.readbackResult
        if (result) requireFact(['verified', 'unknown'].includes(result.status) && result.actionCode === pending.actionCode
          && result.operationId === pending.operationId && result.selectionVersion === pending.selectionVersion
          && result.receiptVersion === pending.receiptVersion && result.requestHash === pending.requestHash
          && result.requestKeyHash === pending.requestKeyHash, '只读核查未对应本次动作、工序、资源版本及原请求。')
        if (row?.operationId === pending.operationId && row.workOrderId === pending.workOrderId
          && proof?.requestKeyHash === pending.requestKeyHash && proof.requestHash === pending.requestHash
          && proof.actorId === pending.actorId && proofVersion(proof) === pending.version + 1
          && (!result || result.status === 'verified' && result.proofHash === proof.proofHash && result.auditReference === proof.auditReference)) {
          const selected = pending.key === 'selectResource'
          clearPending(); state.writeState = 'verified'; state.reason = ''
          state.message = selected ? '本工序正式资源选择已独立回读核实；尚不代表已接收、派工或开工。'
            : '本工序精确接收已独立回读核实；原组接收和历史保持，尚未派工或开工。'
          onFactsChanged({ phase: 'verified', action: selected ? 'selectResource' : 'receiveOperation' })
        } else { state.writeState = 'readback_pending'; state.message = `${state.pendingActionLabel}结果待核实。单次未查到不代表确定失败，请仅重新读取；旧选择证明不能证明本次精确接收。` }
      } else state.writeState = 'idle'
      return true
    } catch (error) {
      if (!current()) return false
      state.facts = null; state.readState = 'read_failed'; state.factLoadFacts = factLoadFailureFromError(error, OPERATION_RESOURCE_API, previous)
      state.error = `资源事实读取失败，当前资源、接收及操作结果未知。${error.message || ''}`
      if (pending) state.writeState = 'readback_pending'
      return false
    }
  }
  async function selectWorkOrder(value = '', { operationId = '',allowLatestFormalLocation=false } = {}) { if (writing || pending) return false
    invalidate(); state.workOrderId = String(value || ''); state.operationId = String(operationId || '');state.allowLatestFormalLocation=allowLatestFormalLocation
    return state.workOrderId ? load() : true }
  async function selectOperation(value = '') { if (writing || pending || externalLocked()) return false
    const order = state.workOrderId; invalidate(); state.workOrderId = order; state.operationId = String(value || ''); return load() }
  async function selectWorkCenter(value = '') { if (writing || pending || externalLocked()) return false
    state.workCenterId = String(value || ''); state.reason = ''; return load() }
  async function execute(key) {
    if (!['selectResource', 'receiveOperation'].includes(key) || !assessment(key).enabled) return false
    const row = state.facts.selectedOperation, actorId = state.facts.currentActorEvidence.userId,
      action = resolvePceOperationResourceActions(row)[key], identity = owner(), epoch = generation
    const current = () => { if (identity !== owner() && epoch === generation) invalidate(); return epoch === generation && identity === owner() }
    const payload = { expectedWorkOrderVersion: row.workOrderVersion, expectedWorkOrderSnapshotHash: row.workOrderSnapshotHash,
      expectedOperationSnapshotHash: row.operationSnapshotHash, expectedSelectionVersion: row.selectionVersion,
      ...(key === 'selectResource' ? { expectedCandidateSnapshotHash: row.candidateWorkCenters.find(item => item.id === Number(state.workCenterId)).candidateSnapshotHash,
        workCenterId: Number(state.workCenterId) } : { expectedSelectionHash: row.selectionFact.selectionHash || row.selectionFact.proofHash,
        expectedCurrentResourceHash: row.currentResourceHash, expectedReceiptVersion: row.receiptVersion }),
      reason: state.reason.trim(), idempotencyKey: globalThis.crypto.randomUUID() }
    writing = true; sequence++; state.writeState = 'writing'; state.error = ''
    try {
      const requestKeyHash = await digest(payload.idempotencyKey), body = { ...payload, requestKeyHash }; delete body.idempotencyKey
      const requestHash = await digest(canonicalOperationResource({ actorId, actionCode: action.actionCode, operationId: row.operationId, payload: body }))
      if (!current()) return false
      const intent = { key, owner: journalOwner(), transportOwner: identity, actorId, workOrderId: row.workOrderId, operationId: row.operationId,
        version: key === 'selectResource' ? row.selectionVersion : row.receiptVersion, selectionVersion: row.selectionVersion,
        receiptVersion: row.receiptVersion, actionCode: action.actionCode, requestKeyHash, requestHash }
      try { pendingStore.save(intent) } catch (error) { state.recoveryJournalError = `无法保留防重复恢复标识，本次未提交。${error.message || ''}`; throw error }
      pending = intent; describePending()
      state.lastDisplayFacts = state.facts; state.facts = null; state.factLoadFacts = null; state.message = '正在提交明确资源意图，随后独立只读回查。'
      const response = await api[key](row.operationId, payload)
      if (!current()) return false
      if (response?.success === false) {
        const status = Number(response.factLoadFacts?.httpStatus || response.data?.factLoadFacts?.httpStatus || response.meta?.status || 0)
        if (status >= 400 && status < 500 && ![408, 429].includes(status)) {
          clearPending(); state.writeState = 'rejected'; state.readState = 'write_rejected'
          state.message = response.error?.message || '服务端拒绝本次资源操作，请重新读取正式事实。'; return false
        }
        throw new Error(response.error?.message || '资源操作响应未确认。')
      }
      validateOperationResourceResponse(response, { apiUrl: action.apiPath, companyId: Number(companyId()), userId: Number(userId()),
        workOrderId: row.workOrderId, operationId: row.operationId, readOnly: false })
      state.writeState = 'readback_pending'
    } catch (error) { if (!current()) return false
      state.writeState = pending ? 'readback_pending' : 'rejected'
      state.message = pending ? `结果待核实，请仅重新读取，不自动重试。${error.message || ''}` : error.message
    } finally { writing = false; if (pending) onFactsChanged({ phase: 'unverified', action: key }) }
    return current() && pending ? load() : false
  }
  return { invalidate, load, selectWorkOrder, selectOperation, selectWorkCenter, execute, assessment }
}
