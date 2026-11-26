// Transport identifiers only. No business payload, quantity, reason, raw key,
// permissions or server facts are persisted or replayed by this module.
export const HANDOVER_INTENT_NAMESPACE = 'pce_operation_handover_intent_v1'
const positive = value => Number.isSafeInteger(value) && value > 0
const nullableId = value => value === null || positive(value)
const digest = value => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value)
const failure = (code,message) => Object.assign(new Error(message),{code})
const domains = Object.freeze(['handover', 'output', 'responsibility', 'completion', 'finishedGoods', 'report', 'completionLegacy'])
const fields = Object.freeze(['domain', 'actorId', 'companyId', 'actionKey', 'actionCode', 'objectId',
  'taskId', 'workOrderId', 'handoverId', 'transferId', 'outputId', 'exceptionId', 'custodyWorkCenterId', 'scopeId', 'workCenterId', 'expectedVersion',
  'generationId', 'requestHash', 'requestKeyHash'])
const valid = row => row && Object.keys(row).length === fields.length
  && fields.every(key => Object.hasOwn(row, key)) && domains.includes(row.domain)
  && positive(row.actorId) && positive(row.companyId)
  && typeof row.actionKey === 'string' && /^[a-z][a-zA-Z.]*$/.test(row.actionKey)
  && typeof row.actionCode === 'string' && /^(?:production\.[a-z0-9._]+|warehouse\.production\.(?:test_putaway|putaway)|pde\.work_center_responsibility\.[a-z]+)$/.test(row.actionCode)
  && (row.actionCode !== 'warehouse.production.putaway' || row.domain === 'finishedGoods' && row.actionKey === 'receive')
  && ['objectId', 'taskId', 'workOrderId', 'handoverId', 'transferId', 'outputId', 'exceptionId', 'custodyWorkCenterId', 'scopeId', 'workCenterId'].every(key => nullableId(row[key]))
  && (row.expectedVersion === null || Number.isSafeInteger(row.expectedVersion) && row.expectedVersion >= 0)
  && (row.generationId === null || Number.isSafeInteger(row.generationId) && row.generationId >= 0)
  && digest(row.requestHash) && digest(row.requestKeyHash)

export function canonicalHandoverJson(value) {
  if (Array.isArray(value)) return value.map(canonicalHandoverJson)
  if (value && typeof value === 'object') return Object.fromEntries(Object.keys(value).sort()
    .map(key => [key, canonicalHandoverJson(value[key])]))
  return value
}
export async function hashHandoverText(value) {
  if (!globalThis.crypto?.subtle) throw new Error('当前环境无法核验原操作意图，本次未提交。')
  const bytes = await globalThis.crypto.subtle.digest('SHA-256', new TextEncoder().encode(value))
  return [...new Uint8Array(bytes)].map(part => part.toString(16).padStart(2, '0')).join('')
}
export function canonicalHandoverIntent({ actorId, actionCode, objectId = null, payload }) {
  return JSON.stringify(canonicalHandoverJson({ actorId, actionCode, objectId,
    payload: Object.fromEntries(Object.entries(payload).filter(([key]) => key !== 'idempotencyKey')) }))
}

export function createHandoverIntentJournal(storage) {
  let accessError = null
  if (storage === undefined) {
    try { storage = globalThis.window?.sessionStorage } catch (error) { accessError = error }
  }
  const key = (actorId, companyId, domain) => {
    if (!positive(actorId) || !positive(companyId) || !domains.includes(domain)) throw new Error('恢复身份或动作范围未核实。')
    return `${HANDOVER_INTENT_NAMESPACE}:${companyId}:${actorId}:${domain}`
  }
  const ready = () => {
    if (accessError || !storage?.getItem || !storage?.setItem || !storage?.removeItem) {
      throw failure('INTENT_STORAGE_UNAVAILABLE','本标签页无法保留原请求恢复标识；仅可读取，不能提交或重复操作。')
    }
  }
  const read = (actorId, companyId, domain) => {
    ready()
    const raw = storage.getItem(key(actorId, companyId, domain))
    if (raw === null) return null
    let row
    try { row = JSON.parse(raw); if(row && row.domain!=='finishedGoods' && !Object.hasOwn(row,'transferId') && Object.keys(row).length===fields.length-1) row.transferId=null } catch { throw failure('INTENT_JOURNAL_CORRUPT','原请求恢复标识损坏；请保留本页并仅进行只读核查。') }
    if (!valid(row) || row.actorId !== actorId || row.companyId !== companyId || row.domain !== domain) {
      throw failure('INTENT_JOURNAL_CORRUPT','原请求恢复标识或归属不完整；仅可只读核查，不能另行提交。')
    }
    return { ...row }
  }
  return {
    read,
    save(intent) {
      const row = Object.fromEntries(fields.map(field => [field, intent[field] ?? null]))
      if (!valid(row)) throw new Error('无法建立完整原请求恢复标识，本次未提交。')
      const previous = read(row.actorId, row.companyId, row.domain)
      if (previous && (previous.requestHash !== row.requestHash || previous.requestKeyHash !== row.requestKeyHash)) {
        throw new Error('本范围已有结果待核实的原请求；只能核查原动作，不可换标识另行提交。')
      }
      storage.setItem(key(row.actorId, row.companyId, row.domain), JSON.stringify(row))
      if (JSON.stringify(read(row.actorId, row.companyId, row.domain)) !== JSON.stringify(row)) {
        throw new Error('原请求恢复标识未安全保存，本次未提交。')
      }
      return row
    },
    remove(intent) {
      const previous = read(intent.actorId, intent.companyId, intent.domain)
      if (!previous) return
      if (previous.actionCode !== intent.actionCode || previous.requestHash !== intent.requestHash
        || previous.requestKeyHash !== intent.requestKeyHash) throw new Error('回查与原恢复标识不一致，不能解除原写入锁。')
      storage.removeItem(key(intent.actorId, intent.companyId, intent.domain))
      if (read(intent.actorId, intent.companyId, intent.domain)) throw new Error('原请求恢复标识尚未解除；请仅重新核查。')
    },
  }
}
