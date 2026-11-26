import { installMesReadIntentCapture, timedMesRead } from '@/meta/runtime/mesReadTiming.js'
import request, { getAuthenticationHeaders } from './request'
import { OPERATION_HANDOVER_PAGE } from '@/meta/runtime/operationHandoverContract.js'
import { createHandoverIntentJournal } from '@/meta/runtime/operationHandoverIntent.js'
import { getTabAuthEpoch, readTabIdentity } from '@/meta/runtime/tabAuthenticationContext.js'

let initialReadStarted = false
let navigationRead

function readHandoverFacts(params) {
  return timedMesRead(() => request({
    method: 'GET', url: OPERATION_HANDOVER_PAGE.apiUrl, params, timeout: 90000,
    meta: { module: 'MES', readOnly: true },
  }), OPERATION_HANDOVER_PAGE.apiUrl)
}

function queryKey(params) {
  return JSON.stringify(Object.entries(params).sort(([left], [right]) => left.localeCompare(right)))
}

function navigationOwner() {
  const identity = readTabIdentity()
  if (!identity?.userId || !identity.companyId) return null
  const authorization = getAuthenticationHeaders().Authorization
  if (!authorization) return null
  const { userId, companyId } = identity
  if (createHandoverIntentJournal().read(Number(userId), Number(companyId), 'handover')) return null
  return JSON.stringify([userId, companyId, authorization, getTabAuthEpoch()])
}

// Reuse one original GET on a fresh numeric detail URL. The normal route and
// session checks still run, and the page validates the same response as usual.
export function startHandoverNavigationRead() {
  if (initialReadStarted || navigationRead) return
  const { pathname, hash } = window.location
  if (pathname !== '/' && pathname !== '/index.html') return
  const prefix = '#' + OPERATION_HANDOVER_PAGE.route + '?'
  if (!hash.startsWith(prefix)) return

  const query = new URLSearchParams(hash.slice(prefix.length))
  const params = { direction: query.get('direction') ?? 'outgoing' }
  if (!['incoming', 'outgoing'].includes(params.direction)) return
  for (const [key, value] of query) {
    if (query.getAll(key).length !== 1) return
    if (key === 'direction') continue
    if (!['taskId', 'handoverId', 'workOrderId'].includes(key)
        || !/^[1-9]\d*$/.test(value) || !Number.isSafeInteger(Number(value))) return
    params[key] = Number(value)
  }
  if (params.handoverId === undefined || (params.direction === 'incoming' && params.taskId === undefined)) return

  const owner = navigationOwner()
  if (!owner) return
  installMesReadIntentCapture()
  const response = readHandoverFacts(params)
  // The normal consumer still receives the original rejection, if any.
  response.catch(() => {})
  navigationRead = { owner, hash, key: queryKey(params), response }
}

function read(params) {
  initialReadStarted = true
  const early = navigationRead
  navigationRead = undefined
  if (early && early.hash === window.location.hash && early.key === queryKey(params)) {
    try {
      if (early.owner === navigationOwner()) return early.response
    } catch {
      // Continue through the normal path if the storage context changed.
    }
  }
  return readHandoverFacts(params)
}

const allowed = /^\/api\/planning\/operation-(?:handovers|outputs)\/(?:[a-z-]+\/|[a-z-]+\/[a-z-]+\/|[1-9]\d*\/[a-z-]+\/|[a-z-]+\/[1-9]\d*\/[a-z-]+\/)?$/
export const operationHandoversApi = Object.freeze({
  read(params = {}) { return read(params) },
  readOutputs(params = {}) {
    return timedMesRead(()=>request({ method: 'GET', url: OPERATION_HANDOVER_PAGE.outputApiUrl, params, timeout: 90000,
      meta: { module: 'MES', readOnly: true } }),OPERATION_HANDOVER_PAGE.outputApiUrl)
  },
  execute(action, data) {
    if (action?.httpMethod !== 'POST' || !allowed.test(action.apiPath || '')) {
      throw new Error('正式工序交接动作接口未通过登记校验。')
    }
    return request({ method: 'POST', url: action.apiPath, data, timeout: 90000,
      meta: { module: 'MES', explicitBusinessAction: true, actionCode: action.actionCode } })
  },
})
