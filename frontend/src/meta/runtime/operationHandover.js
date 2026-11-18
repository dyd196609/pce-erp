import { readPceFactLoadEnvelope, factLoadFailureFromError } from './pceFactLoadContract.js'
import { OPERATION_HANDOVER_PAGE, OPERATION_HANDOVER_METRICS } from './operationHandoverContract.js'
import { resolvePceOperationHandoverAction, resolvePceOperationRangeReceiptAction } from './pceBusinessActionRegistry.js'
import { createHandoverIntentJournal, canonicalHandoverIntent, hashHandoverText } from './operationHandoverIntent.js'

const positive = value => Number.isSafeInteger(value) && value > 0
const text = value => typeof value === 'string' && !!value.trim()
const decimal = value => typeof value === 'string' && /^(?:0|[1-9]\d*)(?:\.\d+)?$/.test(value)
const same = (left, right) => JSON.stringify(left) === JSON.stringify(right)
const requireFact = (condition, message) => { if (!condition) throw new Error(message) }

export function validateGovernedHandoverResponse(response, expected = {}, contract = {}) {
  const apiUrl = expected.apiUrl || contract.apiUrl
  const { data, factLoadFacts } = readPceFactLoadEnvelope(response, apiUrl, contract.label || '工序交接')
  requireFact(factLoadFacts.factLoadStatus !== 'read_failed', factLoadFacts.errorMessage)
  const facts = data[contract.factKey], actor = facts?.currentActorEvidence
  requireFact(facts?.contractVersion === contract.contractVersion && facts.moduleCode === contract.moduleCode
    && facts.factSource === 'server' && facts.currentStateSource === 'server', '正式事实合同、对象或服务端权威来源不一致。')
  requireFact(actor && positive(actor.userId) && positive(actor.companyId) && text(actor.username)
    && actor.userId === expected.actorId && actor.companyId === expected.companyId
    && facts.companyId === expected.companyId, '本次读取账号或公司与当前登录身份不一致。')
  const rows = facts[contract.listField]
  requireFact(Array.isArray(rows) && Number.isSafeInteger(data.resultCount) && data.resultCount >= 0
    && data.resultCount === rows.length, '正式列表及其服务端数量不一致。')
  for (const row of rows) {
    requireFact(positive(row.id) && text(row.statusLabel) && Number.isSafeInteger(row.version)
      && row.version >= 0 && (!Object.hasOwn(row, 'companyId') || row.companyId === actor.companyId),
    '正式记录身份、状态、版本或公司未核实。')
    if (Object.hasOwn(row, 'statusTransitionHistory')) requireFact(row.stateMachineConsistent === true
      && Array.isArray(row.statusTransitionHistory) && row.statusTransitionCount === row.statusTransitionHistory.length,
    '正式状态历史或计数不一致。')
  }
  requireFact(facts.availableActions && typeof facts.availableActions === 'object', '当前可用动作事实未读取。')
  for (const surface of ['apiFacts', 'pageFacts', 'diagnosticFacts', 'strictFacts', 'acceptanceFacts']) {
    requireFact(same(data[surface]?.[contract.factKey], facts) && data[surface]?.resultCount === data.resultCount,
      'API、页面、诊断、strictFacts及验收的正式事实或数量不一致。')
  }
  return { facts, factLoadFacts, serverSurface: data.strictFacts }
}

export function validateOperationHandoverResponse(response, expected = {}) {
  const result = validateGovernedHandoverResponse(response, expected, {
    apiUrl: OPERATION_HANDOVER_PAGE.apiUrl, factKey: 'operationHandoverFacts',
    contractVersion: OPERATION_HANDOVER_PAGE.factContractVersion, moduleCode: OPERATION_HANDOVER_PAGE.moduleId,
    listField: 'handovers', label: OPERATION_HANDOVER_PAGE.title,
  })
  const facts = result.facts
  if (facts.currentRoute != null) {
    const route = facts.currentRoute
    requireFact(route.contractVersion === 'PCE-CURRENT-OPERATION-ROUTE-V1'
      && text(route.workOrderNo) && Array.isArray(route.productTypeCodes)
      && Array.isArray(route.operations) && Array.isArray(route.nextExecutionOperations)
      && Array.isArray(route.unresolvedSuccessors) && Array.isArray(route.physicalHandoverTargets)
      && Array.isArray(route.blockingReasons) && Array.isArray(facts.legalPrepareTargets)
      && text(route.handoverTargetStatusLabel),
    '正式工艺与后序承接事实结构不完整。')
    if (route.continuationPlan != null) requireFact(text(route.continuationPlan.businessLabel)
      && text(route.continuationPlan.ref) && /^[a-f0-9]{64}$/.test(route.continuationPlan.proofHash)
      && text(route.continuationPlan.statusLabel)
      && route.continuationPlan.automaticDispatch === false && route.continuationPlan.automaticStart === false,
    '正式承接方案引用或生产边界未核实。')
    for (const row of route.operations) {
      requireFact(positive(row.operationId) && positive(row.sequence)
        && text(row.operationName) && ['REQUIRED','NOT_APPLICABLE','PENDING'].includes(row.applicability)
        && row.capacitySource && typeof row.capacitySource === 'object'
        && Array.isArray(row.blockingReasons), '工序适用、产能或数量依据未核实。')
      if (route.continuationPlan != null) requireFact(row.continuationRouteRef === route.continuationPlan.ref
        && text(row.productionPlanningStatusLabel) && Array.isArray(row.productionInputBatchNos)
        && row.productionInputBatchNos.every(text)
        && (row.productionInputPlanRef == null ? row.productionInputQuantity == null && row.productionInputUomLabel == null
          : text(row.productionInputPlanRef) && decimal(row.productionInputQuantity) && text(row.productionInputUomLabel)),
      '投产投入引用、数量单位或来源批次未完整核实。')
    }
  }
  for (const header of facts.handovers) {
    const display=header.directionDisplay,current=display?.current
    requireFact(header.historicalRecordReadStatus==='loaded'
      && Array.isArray(header.historicalDispatches) && Array.isArray(header.historicalReceipts)
      && header.historicalDispatches.every(event=>positive(event.eventId) && /^[a-f0-9]{64}$/.test(event.eventHash)
        && text(event.occurredAt) && decimal(event.quantity) && text(event.uomLabel))
      && header.historicalReceipts.every(event=>positive(event.eventId) && /^[a-f0-9]{64}$/.test(event.eventHash)
        && text(event.occurredAt) && decimal(event.rawQuantity) && decimal(event.matchedQuantity) && text(event.uomLabel)),
    '原交出或实收事件读取不完整，不能显示为空记录。')
    requireFact(display?.contractVersion==='PCE-HANDOVER-DIRECTION-DISPLAY-V1'
      && display.originalHistoryPreserved===true && display.businessWriteCount===0
      && display.routeSectionTitle==='工艺适用与后序依据'
      && text(display.historical?.title) && text(display.historical?.processLabel)
      && text(display.historical?.workCenterLabel) && ['loaded','pending','read_failed'].includes(current?.readStatus)
      && text(current.processLabel) && text(current.workCenterLabel) && text(current.explanation)
      && (current.readStatus==='loaded' ? Array.isArray(current.nextExecutionOperations) : current.nextExecutionOperations===null)
      && Array.isArray(current.waiting) && current.waiting.every(row=>positive(row.operationId)
        && ['operationName','title','missing','impact','history'].every(key=>text(row[key]))),
    '历史与当前方向或等待说明未完整读取；不能沿用历史目标推定当前后序。')
  }
  requireFact(facts.readDirection === (expected.direction || 'outgoing')
    && text(facts.readDirectionLabel), '本次交接读取方向与明确定位不一致。')
  if (expected.businessNo) requireFact(facts.selectedHandover && [facts.selectedHandover.businessNo,facts.selectedHandover.legacyNo,facts.selectedHandover.no].includes(expected.businessNo),'交接编号与当前服务端对象不一致。')
  if (expected.workOrderId) requireFact(facts.handovers.every(row => row.workOrderId === Number(expected.workOrderId)),
    '交接记录不属于本次明确工单。')
  requireFact(Array.isArray(facts.slices) && facts.slices.every(row=>row && Object.hasOwn(row,'currentResponsibilityWorkCenterId')
    && (row.currentResponsibilityWorkCenterId===null || positive(row.currentResponsibilityWorkCenterId))),
  '正式份额的当前责任中心未完整核实；不能用原物理保管中心推定可操作责任。')
  for (const key of ['taskOptions', 'outputs', 'quantityAccounts']) requireFact(Array.isArray(facts[key])
    || ['outputs', 'quantityAccounts'].includes(key) && facts.outputReadStatus === 'read_denied' && facts[key] === null,
  '任务、产出或数量账户读取状态不完整。')
  for(const output of facts.outputs || []) requireFact(positive(output.id) && text(output.statusLabel)
    && Number.isSafeInteger(output.version) && decimal(output.quantity) && text(output.batchLabel)
    && text(output.scopeManifest?.reference) && text(output.scopeManifest?.range)
    && text(output.proof?.ref) && /^[a-f0-9]{64}$/.test(output.proof?.proofHash)
    && output.proof.stateMachineConsistent===true && Array.isArray(output.proof.statusTransitionHistory)
    && output.proof.statusTransitionCount===output.proof.statusTransitionHistory.length,
  '正式产出、真实批次范围或原审计证明未完整读取。')
  for(const header of facts.handovers)requireFact(Array.isArray(header.allocations)
    && header.allocations.every(row=>positive(row.id) && positive(row.uomId) && Number.isSafeInteger(row.version)
      && row.version>=0 && decimal(row.quantity)), '本交接单的原准确分量、版本或来源单位未完整读取。')
  for (const [selectedKey, rowsKey, locator] of [['selectedTask', 'taskOptions', 'taskId'],
    ['selectedOutput', 'outputs', 'outputId'], ['selectedHandover', 'handovers', 'handoverId'], ['selectedException','exceptions','exceptionId']]) {
    const selected = facts[selectedKey]
    if (selected) requireFact((facts[rowsKey] || []).some(row => Number(row.id ?? row.taskId) === Number(selected.id ?? selected.taskId)),
      '所选正式对象不属于本次读取范围。')
    const located=selectedKey==='selectedTask' && !selected ? facts.selectedCustodySource : selected
    if (expected[locator]) requireFact(Number(located?.id ?? located?.taskId) === Number(expected[locator]),
      '所选对象与本次明确定位不一致。')
  }
  if (expected.custodyWorkCenterId) requireFact(facts.selectedCustodyWorkCenterId===Number(expected.custodyWorkCenterId),
    '本次保管中心上下文与明确读取定位不一致。')
  if (facts.selectedCustodySource) requireFact(positive(facts.selectedCustodySource.taskId)
    && /^[a-f0-9]{64}$/.test(facts.selectedCustodySource.sourceSnapshotHash || facts.selectedCustodySource.expectations?.expectedSourceSnapshotHash),
  '物流原来源身份或冻结Hash未正式核实。')
  if(Object.hasOwn(facts,'rangeReleases')) {
    requireFact(Array.isArray(facts.rangeReleases),'正式来源范围用途证明集合未读取。')
    for(const row of facts.rangeReleases)requireFact(positive(row.id) && text(row.statusLabel)
      && /^[a-f0-9]{64}$/.test(row.eventHash) && positive(row.source?.target?.workCenterId)
      && (row.source.target.taskId===null || positive(row.source.target.taskId))
      && text(row.source?.reference) && Array.isArray(row.source?.ranges)
      && row.source.ranges.every(part=>positive(part.sliceId)&&decimal(part.quantity)),
    '来源负责人范围用途的真实事件、目标或准确份额证明不完整。')
  }
  if (facts.selectedQuantityAccount) {
    const account = facts.selectedQuantityAccount
    requireFact(facts.quantityAccounts.some(row => same(row, account)), '所选数量账户不属于本次正式范围。')
    for (const { field } of (account.quantityApplicable === false ? OPERATION_HANDOVER_METRICS.filter(row => ['P','R','E'].includes(row.field)) : OPERATION_HANDOVER_METRICS)) requireFact(Object.hasOwn(account, field)
      && (account[field] === null || decimal(account[field])), '数量账户缺少正式十进制数量或明确不适用值。')
  }
  if (facts.selectedTask) {
    const task=facts.selectedTask
    requireFact(task.directoryOnly === false && task.qualificationEvaluated === true
      && typeof task.quantityApplicable === 'boolean' && text(task.taskNo), '任务目录不能作为本次正式详情或资格依据。')
    requireFact(task.expectations && positive(task.expectations.taskId) && task.expectations.taskId === task.id
      && Number.isSafeInteger(task.expectations.expectedVersion) && /^[a-f0-9]{64}$/.test(task.expectations.expectedSourceSnapshotHash),
    '本次正式任务详情缺少准确对象、来源或原版本提交期望。')
  }
  for (const key of Object.keys(facts.availableActions)) {
    if (key !== 'read' && facts.availableActions[key]?.httpMethod === 'POST') resolvePceOperationHandoverAction(facts, key)
  }
  return result
}

export function createOperationHandoverState() {
  return { params: {}, facts: null, lastDisplayFacts: null, factLoadFacts: null, serverSurface: null,
    readState: 'idle', writeState: 'idle', message: '', error: '', recoveryError: '',
    pendingIntent: null, selectionSummary: null, verifiedRecovery: null }
}

const recoveryParams = intent => ({ recoveryAction: intent.actionCode, requestHash: intent.requestHash,
  requestKeyHash: intent.requestKeyHash })
function requireMatchingRecovery(recovery, intent) {
  requireFact(recovery && ['verified', 'unknown', 'rejected'].includes(recovery.status)
    && recovery.actionCode === intent.actionCode && recovery.requestHash === intent.requestHash
    && recovery.requestKeyHash === intent.requestKeyHash && (recovery.status === 'unknown' || recovery.objectId === intent.objectId)
    && (!Object.hasOwn(recovery, 'actorId') || recovery.actorId === intent.actorId),
  '只读回查未准确绑定本次原动作、对象或请求标识。')
  if (recovery.status !== 'unknown') requireFact(text(recovery.proofReference), '对应动作的正式回查证明不完整。')
}
function explicitRejection(value) {
  const response = value?.response?.data || value
  const failure = response?.factLoadFacts || response?.data?.factLoadFacts || response
  const status = Number(failure?.httpStatus || response?.meta?.status || value?.response?.status || 0)
  const code = response?.error?.code || failure?.errorCode || ''
  return response?.success === false && status >= 400 && status < 500 && ![408, 429].includes(status)
    && code !== 'AUTHENTICATION_CONTEXT_CHANGED' ? response?.error?.message || failure.errorMessage || '服务端明确拒绝本次提交。' : null
}

// Shared only by the handover page and its governed WC maintenance subpanel.
// Every business decision and quantity still comes from the configured service.
export function createGovernedHandoverController({ state, api, identity, owner, validator,
  resolveAction, apiUrl, domain = 'handover', journal = createHandoverIntentJournal(), canonicalIntent = canonicalHandoverIntent }) {
  let sequence = 0, generation = 0, factOwner = null, readRequest = null, writeLock = null
  const principal = () => ({ actorId: Number(identity()?.userId), companyId: Number(identity()?.companyId) })
  const writing = () => writeLock?.owner === owner()
  function invalidate() {
    generation += 1; sequence += 1; factOwner = null; readRequest = null
    Object.assign(state, createOperationHandoverState())
  }
  function restoreIntent() {
    const who = principal()
    try {
      const stored = journal.read(who.actorId, who.companyId, domain)
      if (!stored && state.pendingIntent) throw new Error('原请求恢复标识缺失，不能推定本次未提交或解除写入锁。')
      state.pendingIntent = stored
      if (stored) {
        const locator={...state.params}
        for(const key of ['taskId','workOrderId','handoverId','transferId','outputId','exceptionId','custodyWorkCenterId','scopeId','workCenterId']) {
          if(stored[key]===null)delete locator[key]
          else locator[key]=stored[key]
        }
        state.params=locator;state.writeState = 'readback_pending'
      }
    } catch (error) {
      state.recoveryError = error.message
      if (!state.pendingIntent) state.writeState = 'recovery_blocked'
    }
  }
  async function load() {
    if (writing()) return false
    if (factOwner && factOwner !== owner()) invalidate()
    restoreIntent()
    const who = principal(), identityKey = owner(), epoch = generation, intent = state.pendingIntent
    const params = { ...state.params, ...(intent ? recoveryParams(intent) : {}) }
    const requestKey = JSON.stringify([identityKey, params])
    if (readRequest?.key === requestKey) return readRequest.promise
    const request = ++sequence, current = () => {
      if (identityKey !== owner() && epoch === generation) invalidate()
      return epoch === generation && request === sequence && identityKey === owner()
    }
    const previous = state.factLoadFacts
    if (state.facts) state.lastDisplayFacts = state.facts
    Object.assign(state, { facts: null, serverSurface: null, factLoadFacts: null, readState: 'loading', error: '',
      message: intent ? (domain==='responsibility' ? '正在按原动作只读核查负责人维护结果；不重复提交或另换标识。' : '正在只读核查原动作；不重复提交，也不释放已占份额。') : '' })
    const promise = (async () => {
      try {
        // Publish the in-flight read before invoking a transport which may
        // throw synchronously, so finally can always release the GET lock.
        await Promise.resolve()
        if (!current()) return false
        const response = await api.read(params)
        if (!current()) return false
        const loaded = validator(response, { ...who, ...state.params, apiUrl })
        if (intent) requireMatchingRecovery(loaded.facts.resultRecovery, intent)
        Object.assign(state, loaded, { readState: 'loaded', lastDisplayFacts: null }); factOwner = identityKey
        if (intent) {
          const recovery = loaded.facts.resultRecovery
          if (recovery.status === 'unknown') {
            state.writeState = 'readback_pending'
            state.message = '原动作结果仍待核实；本次未查到对应证明不能确定失败。请仅重新读取，不重新提交或换标识。'
          } else {
            state.verifiedRecovery = recovery
            try { journal.remove(intent); state.pendingIntent = null; state.recoveryError = '' }
            catch (error) { state.recoveryError = error.message }
            state.writeState = state.recoveryError ? `${recovery.status}_locked` : recovery.status
            state.message = recovery.status === 'verified'
              ? '本次原动作已按原请求独立回查核实，请核对对应正式记录与审计；未自动办理下一动作。'
              : '本次原动作已由正式回查证明明确拒绝，请核对原因；不会自动重试。'
          }
        } else if (!state.recoveryError) state.writeState = 'idle'
        return true
      } catch (error) {
        if (!current()) return false
        state.facts = null; state.serverSurface = null; state.readState = 'read_failed'
        state.factLoadFacts = factLoadFailureFromError(error, apiUrl, previous)
        state.error = `本次正式事实未读回，当前数量及资格未知。${error?.message || ''}`
        if (intent) state.writeState = 'readback_pending'
        return false
      } finally { if (readRequest?.key === requestKey) readRequest = null }
    })()
    readRequest = { key: requestKey, promise }
    return promise
  }
  async function select(params = {}) {
    if (writing() || state.pendingIntent || state.recoveryError) return false
    invalidate(); state.params = { ...params }
    return load()
  }
  function submission(key) {
    let action
    try { if (state.facts) action = resolveAction(state.facts, key) } catch (error) {
      return { enabled: false, disabledReason: error.message, action: null }
    }
    const disabledReason = writing() ? '正在提交原动作，请勿重复操作。'
      : state.pendingIntent ? '原动作结果待核实，请仅重新读取，不重新提交。'
        : state.recoveryError || (state.readState === 'loading' ? '正在读取当前正式事实，请等待读取完成。'
          : !state.facts || state.readState !== 'loaded' || factOwner !== owner() ? '当前正式事实尚未核实，请仅重新读取。'
            : !action?.enabled ? action?.disabledReason || '服务端未允许本动作。' : '')
    return { enabled: !disabledReason, disabledReason, action }
  }
  async function execute(key, input, summary = null) {
    restoreIntent()
    const assessment = submission(key)
    if (!assessment.enabled) return false
    if (!input || Object.hasOwn(input, 'idempotencyKey') || typeof input.reason !== 'string'
      || input.reason.trim().length < 2 || input.reason.trim().length > 300) {
      state.error = '请填写2至300字真实原因；原请求标识由本次明确提交建立。'; return false
    }
    if (!globalThis.crypto?.randomUUID || !globalThis.crypto?.subtle) {
      state.error = '当前环境无法安全生成原请求标识，本次未提交。'; return false
    }
    const who = principal(), identityKey = owner(), epoch = generation, action = assessment.action
    const lock = { owner: identityKey }; writeLock = lock; sequence += 1
    const current = () => {
      if (identityKey !== owner() && epoch === generation) invalidate()
      return epoch === generation && identityKey === owner()
    }
    const payload = { ...input, reason: input.reason.trim(), idempotencyKey: globalThis.crypto.randomUUID() }
    state.selectionSummary = summary; state.writeState = 'writing'; state.error = ''; state.verifiedRecovery=null
    let intent = null, sent = false
    try {
      const [requestHash, requestKeyHash] = await Promise.all([
        hashHandoverText(canonicalIntent({ ...who, actionCode: action.actionCode, objectId: action.objectId, payload })),
        hashHandoverText(payload.idempotencyKey),
      ])
      if (!current()) return false
      const locators=Object.fromEntries(['taskId','workOrderId','handoverId','transferId','outputId','exceptionId','custodyWorkCenterId','scopeId','workCenterId']
        .map(field=>[field,positive(Number(state.params[field]))?Number(state.params[field]):null]))
      if(domain==='handover' || domain==='output') {
        const source=state.facts?.selectedTask || state.facts?.selectedCustodySource
        const taskId=input.taskId ?? source?.taskId ?? state.facts?.selectedHandover?.taskId
        if(positive(Number(taskId)))locators.taskId=Number(taskId)
        if(positive(Number(source?.workOrderId)))locators.workOrderId=Number(source.workOrderId)
        locators.handoverId=null;locators.outputId=null;locators.exceptionId=null
        if(['dispatch','cancel','receive'].includes(key))locators.handoverId=action.objectId
        if(['excess.review','input.confirm'].includes(key))locators.outputId=action.objectId
        if(['exception.confirm','correct'].includes(key) || key==='exception.submit' && action.objectId!==null)locators.exceptionId=action.objectId
      } else if(domain==='responsibility') {
        locators.scopeId=action.objectId
        const center=input.workCenterId ?? state.facts?.rows?.find(row=>row.id===action.objectId)?.workCenterId
        locators.workCenterId=positive(Number(center))?Number(center):null
      }
      intent = { domain, ...who, actionKey: key, actionCode: action.actionCode, objectId: action.objectId ?? null,...locators,
        expectedVersion: input.expectedVersion ?? null, requestHash, requestKeyHash }
      journal.save(intent); state.pendingIntent = intent
      state.lastDisplayFacts = state.facts; state.facts = null; state.serverSurface = null
      state.message = '正在提交本次明确意图，随后仅用独立GET核查；请勿再次提交。'
      if (!current()) return false
      sent = true
      const response = await api.execute(action, payload)
      if (!current()) return false
      const rejection = explicitRejection(response)
      if (rejection) {
        try { journal.remove(intent); state.pendingIntent = null } catch (failure) { state.recoveryError = failure.message }
        state.writeState = state.recoveryError ? 'rejected_locked' : 'rejected'; state.readState = 'write_rejected'
        state.message = `本次提交已被服务端明确拒绝。${rejection}请重新读取后核对；未自动重试。`
        return false
      }
      state.writeState = 'readback_pending'
      state.message = '提交响应不能替代独立回查，请核对对应原请求证明。'
    } catch (error) {
      if (!current()) return false
      if (sent) {
        const rejection = explicitRejection(error)
        if (rejection) {
          try { journal.remove(intent); state.pendingIntent = null } catch (failure) { state.recoveryError = failure.message }
          state.writeState = state.recoveryError ? 'rejected_locked' : 'rejected'; state.readState = 'write_rejected'
          state.message = `本次提交已被明确拒绝。${rejection}未自动重试。`
          return false
        }
        state.writeState = 'readback_pending'
        state.message = `原动作结果待核实，可能已经保存；请仅重新读取，不自动重试。${error?.message || ''}`
      } else {
        state.recoveryError = error.message; state.writeState = 'recovery_blocked'
        state.message = `本次尚未提交；技术恢复标识未安全建立。${error.message}`
      }
    } finally { if (writeLock === lock) writeLock = null }
    return current() && state.pendingIntent ? load() : false
  }
  return { invalidate, load, select, execute, submission }
}

export function createOperationHandoverController(options) {
  return createGovernedHandoverController({ ...options, apiUrl: OPERATION_HANDOVER_PAGE.apiUrl,
    domain: 'handover', validator: validateOperationHandoverResponse,
    resolveAction: (facts,key) => key === 'range.receive'
      ? resolvePceOperationRangeReceiptAction(facts,options.rangeReceiptSelection?.())
      : resolvePceOperationHandoverAction(facts,key) })
}
