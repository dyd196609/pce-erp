import { readPceFactLoadEnvelope, factLoadFailureFromError } from './pceFactLoadContract.js'
import { resolvePceResourceHandoffAction } from './pceBusinessActionRegistry.js'
import { assertOperationSelectedDetailDirectory, latestOwnFormalLocation } from './operationSelectedDetailContract.js'

export const RESOURCE_HANDOFF_CONTRACT = 'PCE-PRODUCTION-OPERATION-RESOURCE-HANDOFF-V1'
export const RESOURCE_HANDOFF_API = '/api/planning/resource-handoffs/'
const id = value => Number.isSafeInteger(value) && value > 0
const count = value => Number.isSafeInteger(value) && value >= 0
const text = value => typeof value === 'string' && !!value.trim()
const hash = value => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value)
export const canonicalResourceHandoff = value => JSON.stringify(value, (_, item) => item && typeof item === 'object' && !Array.isArray(item)
  ? Object.fromEntries(Object.keys(item).sort().map(key => [key, item[key]])) : item)
const same = (left, right) => canonicalResourceHandoff(left) === canonicalResourceHandoff(right)
function requireFact(condition, message) { if (!condition) throw new Error(message) }
const actorValid = (actor, companyId, userId) => actor && id(actor.userId) && actor.companyId === companyId
  && (!userId || actor.userId === userId) && ['username', 'companyName', 'companyCode'].every(key => text(actor[key]))

export function validateResourceHandoffResponse(response, expected) {
  const { data, factLoadFacts } = readPceFactLoadEnvelope(response, expected.apiUrl || RESOURCE_HANDOFF_API, '工序资源归属承接')
  const facts = data.resourceHandoffFacts
  requireFact(['loaded', 'empty_valid', 'success'].includes(factLoadFacts.factLoadStatus)
    && facts?.contractVersion === RESOURCE_HANDOFF_CONTRACT && facts.moduleCode === 'production-work-order'
    && facts.factSource === 'server' && facts.currentStateSource === 'server'
    && id(expected.companyId) && facts.companyId === expected.companyId
    && actorValid(facts.currentActorEvidence, expected.companyId, expected.userId)
    && facts.workOrderId === expected.workOrderId && text(facts.statusLabel)
    && Array.isArray(facts.operations) && Array.isArray(facts.workOrderOptions)
    && data.resultCount === facts.operations.length, '归属承接后台身份、公司、工单或事实合同不一致。')
  requireFact(facts.workOrderOptions.every(row => id(row.workOrderId) && id(row.productionPlanId) && text(row.workOrderNo))
    && new Set(facts.operations.map(row => row.operationId)).size === facts.operations.length,
  '归属承接工单目录或工序身份不完整。')
  const suggested=latestOwnFormalLocation(facts,expected),expectedOperationId=expected.operationId||suggested?.operationId||null
  assertOperationSelectedDetailDirectory(facts, expectedOperationId)
  if (expected.readOnly !== false) requireFact(['businessWriteCount', 'auditWriteCount', 'stateTransitionWriteCount',
    'resourceHandoffCreatedCount', 'idempotencyWriteCount', 'taskUpdatedCount', 'workOrderUpdatedCount',
    'originalReceiptUpdatedCount', 'operationSourceUpdatedCount', 'masterDataUpdatedCount', 'actualStartCount',
    'actualReportCount', 'completionCreatedCount', 'inventoryUpdatedCount', 'scheduleUpdatedCount', 'downstreamReleasedCount']
    .every(key => data[key] === 0), '归属承接只读回查返回了写入变化，已停止使用。')
  for (const row of facts.operations) {
    requireFact(id(row.operationId) && row.id === row.operationId && row.workOrderId === expected.workOrderId
      && ['workOrderNo', 'operationName', 'statusLabel', 'sourceBasisLabel'].every(key => text(row[key]))
      && ['changeRequired', 'masterDataConsistent', 'sourceReady', 'stateMachineConsistent'].every(key => typeof row[key] === 'boolean')
      && count(row.handoffVersion) && count(row.workOrderVersion) && hash(row.workOrderSnapshotHash)
      && hash(row.operationSnapshotHash) && hash(row.currentSnapshotHash)
      && Array.isArray(row.blockingReasons) && row.blockingReasons.every(text)
      && row.qualification && typeof row.qualification.ready === 'boolean' && text(row.qualification.statusLabel)
      && actorValid(row.qualification.currentActorEvidence, expected.companyId, expected.userId),
    '本工序原接收、当前差异、责任资格或来源版本不完整。')
    if (row.originalReceipt) requireFact(id(row.originalReceipt.id) && hash(row.originalReceipt.snapshotHash)
      && hash(row.originalMembershipHash), '原冻结接收身份或哈希未完整读取。')
    const proof = row.resourceHandoff
    if (proof) requireFact(id(proof.id) && proof.companyId === expected.companyId && proof.workOrderId === row.workOrderId
      && proof.operationId === row.operationId && id(proof.actorId) && proof.version === row.handoffVersion
      && proof.currentSnapshotHash === row.currentSnapshotHash && proof.originalReceiptId === row.originalReceipt?.id
      && proof.originalReceiptHash === row.originalReceipt?.snapshotHash && proof.stateMachineConsistent === true
      && ['proofHash', 'requestKeyHash', 'requestHash'].every(key => hash(proof[key]))
      && ['reason', 'confirmedAt', 'timeLabel', 'auditReference', 'actorLabel', 'statusLabel'].every(key => text(proof[key])),
    '正式归属承接证明与公司、工单、工序、原接收或当前资源不一致。')
    if (Object.hasOwn(row, 'handoffFact')) requireFact(same(row.handoffFact, proof), '正式归属承接事实别名不一致。')
    const action = resolvePceResourceHandoffAction(row)
    requireFact(!action.enabled || row.qualification.ready && row.changeRequired && row.masterDataConsistent
      && !!row.originalReceipt && !proof && hash(row.originalMembershipHash), '归属承接服务端动作与正式准入结论冲突。')
    if (row.availableActions) requireFact(same(row.availableActions.confirm, row.availableAction), '归属承接动作事实不一致。')
  }
  const selected = expectedOperationId ? facts.operations.find(row => row.operationId === expectedOperationId) : null
  requireFact(same(facts.selectedOperation, selected || null), '归属承接当前工序与明确选择不一致。')
  if (selected) requireFact(same(facts.qualification, selected.qualification) && same(facts.availableAction, selected.availableAction),
    '归属承接当前资格或动作未对应本工序。')
  for (const key of ['apiFacts', 'pageFacts', 'diagnosticFacts', 'strictFacts', 'acceptanceFacts']) {
    requireFact(same(data[key]?.resourceHandoffFacts, facts), '归属承接服务端五表面事实不一致。')
  }
  return { facts, factLoadFacts }
}

export function createResourceHandoffState() {
  return { workOrderId: '', operationId: '', facts: null, lastDisplayFacts: null, factLoadFacts: null,
    readState: 'idle', writeState: 'idle', reason: '', error: '', message: '',allowLatestFormalLocation:false }
}
export function assessResourceHandoffSubmission(state, { currentOwner = true, externalLocked = false, secure = true } = {}) {
  const row = state.facts?.selectedOperation, action = row ? resolvePceResourceHandoffAction(row) : null
  const checks = { externalAvailable: !externalLocked, readComplete: state.readState === 'loaded' && !!state.facts,
    noPendingWrite: !['writing', 'readback_pending'].includes(state.writeState), currentOwner,
    selectionPresent: !!row, secure, serverActionAllowed: action?.enabled === true,
    reasonValid: state.reason.trim().length >= 2 && state.reason.trim().length <= 240 }
  const blockers = [ ['externalAvailable', '车间接收正在处理或结果待核实，请先完成其只读回查。'],
    ['noPendingWrite', '归属承接结果待核实，请仅重新读取，不重复提交。'],
    ['readComplete', state.readState === 'loading' ? '正在读取正式归属及承接事实。' : '请重新读取正式归属及承接事实。'],
    ['currentOwner', '账号或公司已变化，请重新读取本人事实。'], ['selectionPresent', '请选择需核对归属的正式工单工序。'],
    ['secure', '当前环境无法建立安全防重复标识，请重新进入正式页面。'],
    ['serverActionAllowed', action?.disabledReason || '当前工序尚不满足正式归属承接准入。'],
    ['reasonValid', '请填写2至240字的归属承接原因。'] ]
  const first = blockers.find(([key]) => !checks[key])
  return { enabled: !first, disabledReason: first?.[1] || '', blockingCode: first?.[0] || '', checks, action }
}
async function sha256(value) {
  const bytes = await globalThis.crypto.subtle.digest('SHA-256', new TextEncoder().encode(value))
  return Array.from(new Uint8Array(bytes), byte => byte.toString(16).padStart(2, '0')).join('')
}
export function createResourceHandoffController({ state, api, owner, companyId, userId, externalLocked = () => false }) {
  let sequence = 0, generation = 0, factOwner = null, writing = false, pending = null, inFlight = null
  const submission = () => assessResourceHandoffSubmission(state, { currentOwner: factOwner === owner(),
    externalLocked: externalLocked(), secure: !!globalThis.crypto?.randomUUID && !!globalThis.crypto?.subtle })
  function invalidate() { sequence++; generation++; factOwner = null; pending = null; Object.assign(state, createResourceHandoffState()) }
  function load({ force = false } = {}) {
    const key = JSON.stringify([owner(), generation, state.workOrderId, state.operationId, pending?.requestHash,state.allowLatestFormalLocation])
    if (!force && inFlight?.key === key) return inFlight.promise
    const promise = loadCurrent(), item = { key, promise }; inFlight = item
    promise.then(() => { if (inFlight === item) inFlight = null }, () => { if (inFlight === item) inFlight = null })
    return promise
  }
  async function loadCurrent() {
    if (writing) return false
    if (factOwner && factOwner !== owner() || pending && pending.owner !== owner()) { invalidate(); return false }
    const request = ++sequence, epoch = generation, identity = owner(), orderId = state.workOrderId, operationId = state.operationId,
      allowLatest=state.allowLatestFormalLocation&&!pending&&!operationId
    const current = () => { if (identity !== owner() && epoch === generation) invalidate()
      return request === sequence && epoch === generation && identity === owner() && orderId === state.workOrderId && operationId === state.operationId }
    const previous = state.factLoadFacts
    if (state.facts) state.lastDisplayFacts = state.facts
    Object.assign(state, { facts: null, factLoadFacts: null, readState: 'loading', error: '', message: pending ? '结果待核实，请仅重新读取正式承接记录。' : '' })
    try {
      const response = await api.read({ ...(orderId ? { workOrderId: Number(orderId) } : {}), ...(operationId ? { operationId: Number(operationId) } : {}),
        ...(allowLatest?{locateOwnLatestFormalAction:1}:{}) })
      if (!current()) return false
      const validated=validateResourceHandoffResponse(response, { companyId: Number(companyId()), userId: Number(userId()),allowLatestFormalLocation:allowLatest,
        workOrderId: orderId ? Number(orderId) : null, operationId: operationId ? Number(operationId) : null })
      if(allowLatest&&validated.facts.viewLocationSuggestion)state.operationId=String(validated.facts.viewLocationSuggestion.operationId)
      Object.assign(state,validated,{ readState: 'loaded', lastDisplayFacts: null })
      if(allowLatest)state.message=validated.facts.viewLocationStatusLabel||validated.facts.viewLocationSuggestion?.statusLabel||''
      factOwner = identity
      if (pending) {
        const row = state.facts.selectedOperation, proof = row?.resourceHandoff
        if (row?.operationId === pending.operationId && row.workOrderId === pending.workOrderId
          && proof?.requestKeyHash === pending.requestKeyHash && proof.requestHash === pending.requestHash
          && proof.actorId === pending.actorId && proof.reason === pending.reason
          && row.handoffVersion === pending.version + 1 && row.currentSnapshotHash === pending.currentSnapshotHash) {
          pending = null; state.writeState = 'verified'; state.reason = ''; state.message = '本工序正式归属承接已独立回读核实；原接收及既有执行历史保留，未派工或开工。'
        } else { state.writeState = 'readback_pending'; state.message = '本次承接意图仍未核实，请仅重新读取；其他人员的承接或状态变化不能证明本次操作成功。' }
      } else state.writeState = 'idle'
      return true
    } catch (error) {
      if (!current()) return false
      state.facts = null; state.readState = 'read_failed'; state.factLoadFacts = factLoadFailureFromError(error, RESOURCE_HANDOFF_API, previous)
      state.error = `归属承接读取失败，当前归属、责任及操作结果未知。${error?.message || ''}`
      if (pending) state.writeState = 'readback_pending'
      return false
    }
  }
  async function selectWorkOrder(value = '', { operationId = '',allowLatestFormalLocation=false } = {}) { if (writing || pending) return false
    invalidate(); state.workOrderId = String(value || ''); state.operationId = String(operationId || '');state.allowLatestFormalLocation=allowLatestFormalLocation; return load() }
  async function selectOperation(value = '') { if (writing || pending || externalLocked()) return false
    const order = state.workOrderId; invalidate(); state.workOrderId = order; state.operationId = String(value || ''); return load() }
  async function confirm() {
    if (!submission().enabled) return false
    const row = state.facts.selectedOperation, identity = owner(), epoch = generation, actorId = state.facts.currentActorEvidence.userId
    const current = () => { if (identity !== owner() && epoch === generation) invalidate(); return epoch === generation && identity === owner() }
    const payload = { expectedWorkOrderVersion: row.workOrderVersion, expectedWorkOrderSnapshotHash: row.workOrderSnapshotHash,
      expectedOperationSnapshotHash: row.operationSnapshotHash, expectedOriginalReceiptHash: row.originalReceipt.snapshotHash,
      expectedOriginalMembershipHash: row.originalMembershipHash, expectedCurrentSnapshotHash: row.currentSnapshotHash,
      expectedHandoffVersion: row.handoffVersion, reason: state.reason.trim(), idempotencyKey: globalThis.crypto.randomUUID() }
    writing = true; sequence++; state.writeState = 'writing'; state.error = ''
    try {
      const requestKeyHash = await sha256(payload.idempotencyKey), intent = { ...payload, requestKeyHash }
      delete intent.idempotencyKey
      const requestHash = await sha256(canonicalResourceHandoff({ actorId, actionCode: 'production.order.resource_handoff', operationId: row.operationId, payload: intent }))
      if (!current()) return false
      pending = { owner: identity, actorId, operationId: row.operationId, workOrderId: row.workOrderId,
        version: row.handoffVersion, currentSnapshotHash: row.currentSnapshotHash, requestKeyHash, requestHash, reason: payload.reason }
      state.lastDisplayFacts = state.facts; state.facts = null; state.factLoadFacts = null
      state.message = '正在提交本工序明确的归属承接意图，随后独立只读回查。'
      const response = await api.confirm(row.operationId, payload)
      if (!current()) return false
      if (response?.success === false) {
        const status = Number(response.factLoadFacts?.httpStatus || response.data?.factLoadFacts?.httpStatus || response.meta?.status || 0)
        if (status >= 400 && status < 500 && ![408, 429].includes(status)) {
          pending = null; state.writeState = 'rejected'; state.readState = 'write_rejected'
          state.message = response.error?.message || '服务端拒绝本次归属承接，请重新读取正式事实。'; return false
        }
        throw new Error(response.error?.message || '归属承接响应未确认。')
      }
      validateResourceHandoffResponse(response, { apiUrl: `${RESOURCE_HANDOFF_API}${row.operationId}/confirm/`,
        companyId: Number(companyId()), userId: Number(userId()), workOrderId: row.workOrderId, operationId: row.operationId, readOnly: false })
      state.writeState = 'readback_pending'
    } catch (error) { if (!current()) return false
      state.writeState = pending ? 'readback_pending' : 'rejected'
      state.message = pending ? `本次承接可能已保存，请仅重新读取，不自动重试。${error?.message || ''}` : error.message
    } finally { writing = false }
    return current() && pending ? load() : false
  }
  return { invalidate, load, selectWorkOrder, selectOperation, confirm, submission }
}
