import { buildPurchaseInquiryRuntimeView } from '../runtime/purchaseInquiryRuntime.js'
import { purchaseInquiryRuntimeStore } from '../runtime/purchaseInquiryRuntimeStore.js'
import { resolvePurchaseInquiryBusinessState } from '../process/scm/purchaseInquiry/purchaseInquiryBusinessStateMapping.js'
import { createPurchaseInquiryFromRequest, getScmStandardPageFacts } from '@/api/scmStandardPageFacts.js'
import { getPurchaseInquiryCanaryRuntime } from '@/api/purchaseCanary.js'
import { resolveEnterpriseListCanaryQuery } from '../runtime/enterpriseListCanaryMode.js'
import { mapPurchaseInquiryServerFact } from '../schema/scm/purchaseInquiryRuntimeMapping.js'

export const PURCHASE_INQUIRY_PROVIDER_VERSION = 'V1.14.2.8.4.21'

export function createPurchaseInquiryProvider({ runtimeStore = purchaseInquiryRuntimeStore } = {}) {
  return Object.freeze({
    providerCode: 'SCM_PURCHASE_INQUIRY_PROVIDER', version: PURCHASE_INQUIRY_PROVIDER_VERSION,
    factSource: 'server_facts+purchase_inquiry_runtime_store',
    load({ serverFacts = {} } = {}) {
      const runtimeView = buildPurchaseInquiryRuntimeView(serverFacts)
      const persisted = runtimeStore.reload()
      const persistedNos = new Set(persisted.map(item => item.inquiryNo))
      const existingInquiryList = Object.freeze([...persisted,
        ...runtimeView.inquiries.filter(item => !persistedNos.has(item.inquiryNo))]
        .map(item => Object.freeze({ ...item, ...resolvePurchaseInquiryBusinessState(item) })))
      return Object.freeze({ providerCode: this.providerCode, version: this.version,
        factSource: this.factSource, runtimeView, persistedInquiryCount: persisted.length,
        serverInquiryCount: runtimeView.inquiries.length, existingInquiryList,
        recordCount: existingInquiryList.length })
    },
    async loadRuntime({ query = {} } = {}) {
      const canary = resolveEnterpriseListCanaryQuery(query)
      const dataMode = canary.isCanaryMode ? 'canary_acceptance' : 'production'
      const response = canary.isCanaryMode
        ? await getPurchaseInquiryCanaryRuntime({
            canaryBatchId: canary.canaryBatchId,
            scenarioCode: canary.scenarioCode,
          })
        : await getScmStandardPageFacts('purchase-inquiry')
      if (!response?.success || !response.data) {
        throw new Error(response?.error?.message || '采购询价事实读取失败')
      }
      const objects = Object.freeze((response.data.objects || []).map(item => {
        const mapped = mapPurchaseInquiryServerFact(item)
        return Object.freeze({ ...mapped, ...resolvePurchaseInquiryBusinessState(mapped) })
      }))
      return Object.freeze({
        providerCode: canary.isCanaryMode ? 'PurchaseInquiryCanaryProvider' : 'PurchaseInquiryProductionProvider',
        version: this.version,
        factSource: 'server',
        dataMode,
        productionApiCallCount: canary.isCanaryMode ? 0 : 1,
        canaryApiCallCount: canary.isCanaryMode ? 1 : 0,
        existingInquiryList: objects,
        recordCount: objects.length,
        eligibleSourceRequests: Object.freeze(response.data.eligibleSourceRequests || []),
        eligibleSourceRequestCount: response.data.eligibleSourceRequestCount || 0,
        canaryBatchId: response.data.canaryBatchId || '',
        scenarioCode: response.data.scenarioCode || '',
        sourceMapping: response.data.sourceMapping || null,
        businessWriteCount: 0,
        purchaseOrderCreated: false,
        productionUserDataWritten: false,
      })
    },
    async createFromApprovedRequest(requestId) {
      const response = await createPurchaseInquiryFromRequest(requestId)
      if (!response?.success || !response.data) {
        throw new Error(response?.error?.message || '采购询价生成失败')
      }
      return Object.freeze(response.data)
    },
  })
}

export const purchaseInquiryProvider = createPurchaseInquiryProvider()
