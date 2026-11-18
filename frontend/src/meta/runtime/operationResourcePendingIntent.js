// Transport recovery journal only. It never stores server facts, eligibility,
// business reasons, credentials, raw idempotency keys or a replayable payload.
export const OPERATION_RESOURCE_PENDING_KEY = 'pce_operation_resource_pending_intents_v1'
const fields = Object.freeze(['key', 'owner', 'actorId', 'workOrderId', 'operationId', 'version',
  'selectionVersion', 'receiptVersion', 'actionCode', 'requestKeyHash', 'requestHash'])
const positive = value => Number.isSafeInteger(value) && value > 0
const version = value => Number.isSafeInteger(value) && value >= 0
const hash = value => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value)
const valid = row => row && ['selectResource', 'receiveOperation'].includes(row.key)
  && typeof row.owner === 'string' && positive(row.actorId) && positive(row.workOrderId) && positive(row.operationId)
  && ['version', 'selectionVersion', 'receiptVersion'].every(key => version(row[key]))
  && row.actionCode === (row.key === 'selectResource' ? 'production.order.select_operation_resource' : 'production.order.receive_operation')
  && hash(row.requestKeyHash) && hash(row.requestHash)
export function createOperationResourcePendingStore(storage) {
  const memory = new Map()
  let storageError = null
  if (storage === undefined) { try { storage = globalThis.window?.sessionStorage } catch (error) { storageError = error } }
  const readRows = () => {
    if (storageError) throw new Error('本标签页无法保留防重复恢复标识，请先恢复会话存储再进行资源操作；本次未提交。')
    if (!storage) return [...memory.values()]
    const rows = JSON.parse(storage.getItem(OPERATION_RESOURCE_PENDING_KEY) || '[]')
    if (!Array.isArray(rows) || !rows.every(valid)) throw new Error('资源操作恢复标识不完整，请保留本页并进行只读核查。')
    return rows
  }
  const persist = rows => { if (storage) storage.setItem(OPERATION_RESOURCE_PENDING_KEY, JSON.stringify(rows))
    else { memory.clear(); rows.forEach(row => memory.set(`${row.owner}:${row.workOrderId}`, row)) } }
  return {
    readOwn(owner) { return readRows().filter(row => row.owner === owner).map(row => ({ ...row })) },
    read(owner, workOrderId) { return readRows().find(row => row.owner === owner && row.workOrderId === workOrderId) || null },
    save(intent) { const row = Object.fromEntries(fields.map(key => [key, intent[key]]))
      if (!valid(row)) throw new Error('无法建立完整的资源操作恢复标识，本次未提交。')
      persist([...readRows().filter(old => old.owner !== row.owner || old.workOrderId !== row.workOrderId), row]) },
    remove(intent) { persist(readRows().filter(row => row.owner !== intent.owner || row.workOrderId !== intent.workOrderId
      || row.requestKeyHash !== intent.requestKeyHash)) },
  }
}
