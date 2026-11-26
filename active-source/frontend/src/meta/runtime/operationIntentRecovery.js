// Transport continuation only. The native read validators and authority own
// quantities, history, eligibility and state. Never persist/replay a payload.
import { createHandoverIntentJournal, canonicalHandoverJson, hashHandoverText } from './operationHandoverIntent.js'
import { canonicalExecutionIntent } from './operationExecutionMode.js'
import { factLoadFailureFromError } from './pceFactLoadContract.js'

const canonical = value => JSON.stringify(canonicalHandoverJson(value))
const proofText = value => typeof value === 'string' && !!value.trim()
export async function operationRequestHashes(actorId, actionCode, taskId, payload, kind) {
  const requestKeyHash = await hashHandoverText(payload.idempotencyKey)
  const body = { ...payload, reason: payload.reason.trim() }
  let intent
  if (kind === 'confirmExecution') intent = canonicalExecutionIntent({ actorId, action: actionCode, taskId, payload: body })
  else if (kind === 'completionLegacy') {
    delete body.idempotencyKey; body.requestKeyHash = requestKeyHash
    intent = canonical({ actorId, action: actionCode, taskId, payload: body })
  } else intent = canonical({ actorId, action: actionCode, taskId, payload: body })
  return { requestKeyHash, requestHash: await hashHandoverText(intent) }
}

export function verifiedOperationRequest(facts, intent) {
  const actor = facts?.currentActorEvidence
  if (actor?.userId !== intent.actorId || actor?.companyId !== intent.companyId) return false
  const task = facts.tasks?.find(row => row.taskId === intent.taskId)
  if (!task) return false
  if (intent.domain === 'report') {
    return facts.operationRequestProofs?.some(proof => proof.taskId === intent.taskId
      && proof.actorId === intent.actorId && proof.companyId === intent.companyId
      && proof.actionCode === intent.actionCode && proof.requestKeyHash === intent.requestKeyHash
      && proof.requestHash === intent.requestHash && proofText(proof.auditReference)) === true
  }
  const completion = task.completionFact, approve = intent.actionKey === 'approve'
  return completion?.stateMachineConsistent === true
    && (approve ? completion.reviewerId : completion.applicantId) === intent.actorId
    && (approve ? completion.approvalRequestKeyHash : completion.requestKeyHash) === intent.requestKeyHash
    && (approve ? completion.approvalRequestHash : completion.requestHash) === intent.requestHash
    && proofText(approve ? completion.approvalAuditReference : completion.requestAuditReference)
}

export function createOperationIntentRecovery({ state, api, owner, companyId, userId, domain, validator, apiUrl,
  methods, journal = createHandoverIntentJournal() }) {
  let lastRead = null, observed = null, executing = false
  const who = () => ({ actorId: Number(userId()), companyId: Number(companyId()) })
  function pending() {
    const principal = who(), row = journal.read(principal.actorId, principal.companyId, domain)
    if (observed && (observed.actorId !== principal.actorId || observed.companyId !== principal.companyId)) observed = null
    if (!row && observed) throw new Error('原请求恢复标识缺失，不能据此判定未提交或解除操作锁。')
    if (row) observed = row
    return row
  }
  function block(error) { state.intentRecoveryError = error.message; state.writeState = 'recovery_blocked'; state.message = error.message }
  function remove(intent) { journal.remove(intent); observed = null; state.intentRecoveryError = '' }
  const guardedApi = { ...api, async read(params) { const response = await api.read(params); lastRead = response; return response } }
  for (const [method, actionKey] of Object.entries(methods)) {
    guardedApi[method] = async (taskId, payload) => {
      // V3 retains its existing, separately governed generation journal.
      if (domain === 'completionLegacy' && payload.completionProtocolVersion === 3) return api[method](taskId, payload)
      const principal = who(), facts = state.lastDisplayFacts || state.facts
      const actionCode = facts?.availableActions?.[actionKey]?.actionCode
      if (!actionCode) throw new Error('本次原动作权限声明未核实，不能提交。')
      const hashes = await operationRequestHashes(principal.actorId, actionCode, taskId, payload,
        domain === 'completionLegacy' ? domain : method)
      observed = journal.save({ domain, ...principal, actionKey, actionCode, taskId, objectId: taskId,
        expectedVersion: payload.expectedVersion, ...hashes })
      return api[method](taskId, payload)
    }
  }
  return { api: guardedApi, attach(controller) {
    async function load() {
      let intent
      try { intent = pending(); state.intentRecoveryError = '' }
      catch (error) { const result = await controller.load(); block(error); return result }
      if (!intent) return controller.load()
      const identity = owner(), previous = state.factLoadFacts
      try {
        const response = await (api.readRecovery || api.read)({ taskId: intent.taskId })
        if (owner() !== identity) { controller.invalidate(); return false }
        const loaded = validator(response, { companyId: intent.companyId, userId: intent.actorId, taskId: intent.taskId, apiUrl })
        const verified = verifiedOperationRequest(loaded.facts, intent)
        // Read the requested route independently: never replace it with facts
        // belonging to the pending action's other task/order.
        const result = await controller.load()
        if (owner() !== identity) return false
        if (verified) {
          remove(intent); state.writeState = 'verified'; state.quantity = ''; state.reason = ''
          state.message = '原操作已按同一请求和正式审计只读核实；未重复提交或办理下一动作。'
        } else {
          state.writeState = 'readback_pending'
          state.message = '原操作结果仍待核实；未查到对应证明不等于失败。请仅重新读取，不换标识再次提交。'
        }
        return result
      } catch (error) {
        if (owner() !== identity) return false
        state.lastDisplayFacts = state.facts || state.lastDisplayFacts; state.facts = null; state.serverSurface = null
        state.readState = 'read_failed'; state.writeState = 'readback_pending'
        state.factLoadFacts = factLoadFailureFromError(error, apiUrl, previous)
        state.error = `原操作结果未读回，当前资格未知。${error.message}`
        return false
      }
    }
    return { ...controller, load,
      async select(taskId = '') {
        if (executing) return false
        let intent
        try { intent = pending() } catch (error) { const result = await controller.select(taskId); block(error); return result }
        if (!intent) return controller.select(taskId)
        controller.invalidate(); state.taskId = String(taskId || '')
        return load()
      },
      submission(...args) {
        try {
          if (pending() || state.intentRecoveryError || executing) return { enabled: false,
            disabledReason: state.intentRecoveryError || '原操作结果待核实，请仅重新读取，不重复提交。' }
        } catch (error) { block(error); return { enabled: false, disabledReason: error.message } }
        return controller.submission(...args)
      },
      async execute(...args) {
        if (executing) return false
        let prior
        try { prior = pending() } catch (error) { block(error); return false }
        // A click while recovery is pending is only a read, even if verified.
        if (prior) return load()
        executing = true; const identity = owner()
        try {
          const result = await controller.execute(...args)
          if (owner() !== identity) return false
          const intent = pending()
          if (intent && state.writeState === 'rejected') remove(intent)
          else if (intent && state.writeState === 'verified') {
            const loaded = validator(lastRead, { companyId: intent.companyId, userId: intent.actorId, apiUrl })
            if (verifiedOperationRequest(loaded.facts, intent)) remove(intent)
            else { state.writeState = 'readback_pending'; state.message = '原操作的准确请求证明尚未核实，请仅重新读取。' }
          }
          return result
        } catch (error) { block(error); return false }
        finally { executing = false }
      },
    }
  } }
}
