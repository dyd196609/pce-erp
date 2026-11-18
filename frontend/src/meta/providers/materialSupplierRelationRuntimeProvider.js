import { enterpriseMasterDataApi } from '@/api/enterpriseMasterData'
import { buildMaterialSupplierRelationRuntime } from '@/meta/runtime/materialSupplierRelationRuntime'

let runtime = null
let loadPromise = null

function payloadOf(response) {
  return response?.data || response || {}
}

export async function loadMaterialSupplierRelationRuntime({ force = false } = {}) {
  if (!force && runtime) return runtime
  if (!force && loadPromise) return loadPromise
  loadPromise = enterpriseMasterDataApi.materialSupplierRelations()
    .then((response) => {
      runtime = buildMaterialSupplierRelationRuntime(payloadOf(response))
      return runtime
    })
    .finally(() => {
      loadPromise = null
    })
  return loadPromise
}

export function getMaterialSupplierRelationRuntime() {
  return runtime
}

export async function updateMaterialSupplierDeliveryPeriod(relationCode, deliveryPeriod) {
  const response = await enterpriseMasterDataApi.updateMaterialSupplierDeliveryPeriod(relationCode, deliveryPeriod)
  runtime = buildMaterialSupplierRelationRuntime(payloadOf(response))
  return runtime
}
