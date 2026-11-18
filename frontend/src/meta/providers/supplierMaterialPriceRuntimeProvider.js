import { enterpriseMasterDataApi } from '@/api/enterpriseMasterData'
import { buildSupplierMaterialPriceRuntime } from '@/meta/runtime/supplierMaterialPriceRuntime'

let runtime = null
let loadPromise = null

function payloadOf(response) {
  return response?.data || response || {}
}

export async function loadSupplierMaterialPriceRuntime({ force = false } = {}) {
  if (!force && runtime) return runtime
  if (!force && loadPromise) return loadPromise
  loadPromise = enterpriseMasterDataApi.supplierMaterialPrices()
    .then((response) => {
      runtime = buildSupplierMaterialPriceRuntime(payloadOf(response))
      return runtime
    })
    .finally(() => {
      loadPromise = null
    })
  return loadPromise
}

export function getSupplierMaterialPriceRuntime() {
  return runtime
}

// Read-only Batch2.2 contract: returns every formal version for the exact
// supplier/material context. It does not choose a price or create an order.
export async function loadSupplierMaterialPriceBatches({ supplierCode, materialCode, currency = '' }) {
  if (!supplierCode || !materialCode) {
    throw new Error('供应商和物料是价格批次查询的必填条件')
  }
  const response = await enterpriseMasterDataApi.supplierMaterialPrices({
    supplierCode, materialCode, ...(currency ? { currency } : {}),
  })
  return buildSupplierMaterialPriceRuntime(payloadOf(response))
}

// R2 governed purchase-object source: all persisted price versions for one
// supplier. Consumers must explicitly select CURRENT rows; no material-first lookup.
export async function loadSupplierMaterialPrices({ supplierCode, currency = '' }) {
  if (!supplierCode) throw new Error('供应商是正式采购价格查询的必填条件')
  const response = await enterpriseMasterDataApi.supplierMaterialPrices({
    supplierCode, ...(currency ? { currency } : {}),
  })
  return buildSupplierMaterialPriceRuntime(payloadOf(response))
}

export async function confirmSupplierQuotationPrice(payload) {
  const response = await enterpriseMasterDataApi.confirmSupplierQuotationPrice(payload)
  runtime = buildSupplierMaterialPriceRuntime(payloadOf(response))
  return runtime
}

export async function recordPriceApprovalResult(payload) {
  const response = await enterpriseMasterDataApi.recordPriceApprovalResult(payload)
  runtime = buildSupplierMaterialPriceRuntime(payloadOf(response))
  return runtime
}

export async function batchArchiveSupplierMaterialPrices(resultIds) {
  const response = await enterpriseMasterDataApi.batchArchiveSupplierMaterialPrices(resultIds)
  runtime = buildSupplierMaterialPriceRuntime(payloadOf(response))
  return runtime
}

export async function updateSupplierMaterialPrice(priceNo, payload) {
  await enterpriseMasterDataApi.updateSupplierMaterialPrice(priceNo, payload)
  const response = await enterpriseMasterDataApi.supplierMaterialPrices()
  runtime = buildSupplierMaterialPriceRuntime(payloadOf(response))
  return runtime
}
