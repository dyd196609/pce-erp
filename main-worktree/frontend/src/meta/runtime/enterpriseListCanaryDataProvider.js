import { getPurchaseCanaryContext } from '@/api/purchaseCanary.js'
import { resolveEnterpriseListCanaryQuery } from './enterpriseListCanaryMode.js'

export { resolveEnterpriseListCanaryQuery } from './enterpriseListCanaryMode.js'

const STATUS_LABELS = Object.freeze({
  completed: '已完成',
  matched: '已匹配',
  draft: '草稿',
  blocked: '已阻断',
})

const CANARY_FACT_CACHE = new Map()

function toEnterpriseListRow(context, pageCode) {
  const current = context.current || {}
  const objectNo = pageCode === 'purchase-request'
    ? (context.businessNo || current.objectNo || '')
    : (current.objectNo || '')
  const statusCode = current.status || ''
  const common = {
    id: `canary:${context.batchId}:${context.scenario?.code}:${pageCode}:${objectNo}`,
    objectId: objectNo,
    objectNo,
    businessNo: objectNo,
    objectType: 'PurchaseCanaryModuleObject',
    statusCode,
    statusLabel: STATUS_LABELS[statusCode] || '金丝雀状态',
    quantity: 0,
    amount: '0.00',
    sourceObject: current.upstreamObjectNo
      ? { objectNo: current.upstreamObjectNo, objectType: 'CanaryUpstreamObject' }
      : null,
    targetObject: current.downstreamObjectNo
      ? { objectNo: current.downstreamObjectNo, objectType: 'CanaryDownstreamObject' }
      : null,
    dataType: context.dataType,
    dataMode: context.dataType,
    canaryBatchId: context.batchId,
    scenarioCode: context.scenario?.code || '',
    cleanupPolicy: context.retentionPolicy?.cleanupPolicy || '',
    evidenceHash: current.evidenceHash || '',
    currentNode: current.moduleName || '',
    nextNode: context.next?.moduleName || '流程终点',
    sourceObjectNo: current.upstreamObjectNo || '',
    targetObjectNo: current.downstreamObjectNo || '',
    readOnly: true,
  }
  if (pageCode !== 'purchase-request') return common
  return {
    ...common,
    requestNo: objectNo,
    requestDate: '—',
    requestType: 'canary_acceptance',
    requestTypeLabel: '金丝雀验收',
    projectName: context.scenario?.name || '',
    usageDepartment: '验收隔离域',
    department: '验收隔离域',
    requester: '只读验收',
    purchaseDepartment: '不适用',
    costCenterName: '不适用',
    materialSummary: `${current.upstreamObjectNo || '流程起点'} → ${current.downstreamObjectNo || '流程终点'}`,
    totalQuantity: 0,
    requiredDate: '—',
  }
}

export async function loadEnterpriseListCanaryFacts(pageCode, query = {}) {
  const mode = resolveEnterpriseListCanaryQuery(query)
  if (!mode.isCanaryMode) return null
  const cacheKey = `${mode.canaryBatchId}:${mode.scenarioCode}:${pageCode}`
  if (CANARY_FACT_CACHE.has(cacheKey)) return CANARY_FACT_CACHE.get(cacheKey)
  const loading = (async () => {
    const response = await getPurchaseCanaryContext({
      batchId: mode.canaryBatchId,
      scenarioCode: mode.scenarioCode,
      moduleCode: pageCode,
    })
    if (!response?.success || !response.data) {
      throw new Error(response?.error?.message || '金丝雀验收数据读取失败')
    }
    const context = response.data
    const row = toEnterpriseListRow(context, pageCode)
    return Object.freeze({
    factSource: 'server',
    apiUrl: '/api/pce/purchase-canary/context',
    status: 'loaded',
    recordCount: 1,
    canaryObjectCount: context.canaryObjectCount || context.scenarios?.length || 1,
    objects: Object.freeze([Object.freeze(row)]),
    isCanaryMode: true,
    dataMode: context.dataType,
    dataType: context.dataType,
    canaryBatchId: context.batchId,
    scenarioCode: context.scenario?.code || '',
    cleanupPolicy: context.retentionPolicy?.cleanupPolicy || '',
    retentionPolicy: Object.freeze({ ...(context.retentionPolicy || {}) }),
    canaryContext: Object.freeze(context),
    currentStateSource: 'server',
    productionUserDataWritten: false,
    })
  })()
  CANARY_FACT_CACHE.set(cacheKey, loading)
  try {
    const facts = await loading
    CANARY_FACT_CACHE.set(cacheKey, Promise.resolve(facts))
    return facts
  } catch (error) {
    CANARY_FACT_CACHE.delete(cacheKey)
    throw error
  }
}
