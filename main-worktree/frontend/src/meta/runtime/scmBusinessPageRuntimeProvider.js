import { getScmStandardPageFacts } from '@/api/scmStandardPageFacts.js'
import {
  loadEnterpriseListCanaryFacts,
  resolveEnterpriseListCanaryQuery,
} from './enterpriseListCanaryDataProvider.js'

export function resolveScmBusinessRuntimeMode(query = {}) {
  return resolveEnterpriseListCanaryQuery(query).isCanaryMode
    ? 'canary_acceptance'
    : 'production'
}

export async function loadScmBusinessPageRuntimeFacts({ pageCode, query = {} }) {
  const dataMode = resolveScmBusinessRuntimeMode(query)
  if (dataMode === 'canary_acceptance') {
    const facts = await loadEnterpriseListCanaryFacts(pageCode, query)
    return Object.freeze({
      dataMode,
      providerCode: 'CanaryReadModelProvider',
      productionApiCallCount: 0,
      canaryApiCallCount: 1,
      facts,
    })
  }
  const response = await getScmStandardPageFacts(pageCode)
  if (!response?.success) {
    throw new Error(response?.error?.message || `${pageCode}正式事实读取失败`)
  }
  return Object.freeze({
    dataMode,
    providerCode: 'ProductionBusinessProvider',
    productionApiCallCount: 1,
    canaryApiCallCount: 0,
    facts: Object.freeze({ ...response.data, isCanaryMode: false, dataMode }),
  })
}
