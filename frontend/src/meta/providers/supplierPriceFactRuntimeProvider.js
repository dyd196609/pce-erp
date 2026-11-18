import { enterpriseMasterDataApi } from '@/api/enterpriseMasterData'
import { buildSupplierPriceFactRuntime } from '@/meta/runtime/supplierPriceFactRuntime'

let runtime = null
let loadPromise = null

function payloadOf(response) {
  return response?.data || response || {}
}

export async function loadSupplierPriceFactRuntime({ force = false } = {}) {
  if (!force && runtime) return runtime
  if (!force && loadPromise) return loadPromise
  loadPromise = enterpriseMasterDataApi.supplierPriceFacts()
    .then((response) => {
      runtime = buildSupplierPriceFactRuntime(payloadOf(response))
      return runtime
    })
    .finally(() => {
      loadPromise = null
    })
  return loadPromise
}

export function getSupplierPriceFactRuntime() {
  return runtime
}

