import { enterpriseMasterDataApi } from '@/api/enterpriseMasterData'
import { buildMasterDataStatisticsRuntime } from '@/meta/runtime/masterDataStatisticsRuntime'

let runtime = null
let loadPromise = null

function payloadOf(response) {
  return response?.data || response || {}
}

export async function loadMasterDataStatisticsRuntime({ force = false } = {}) {
  if (!force && runtime) return runtime
  if (!force && loadPromise) return loadPromise
  loadPromise = enterpriseMasterDataApi.statistics()
    .then((response) => {
      runtime = buildMasterDataStatisticsRuntime(payloadOf(response))
      return runtime
    })
    .finally(() => {
      loadPromise = null
    })
  return loadPromise
}

export function getMasterDataStatisticsRuntime() {
  return runtime
}
