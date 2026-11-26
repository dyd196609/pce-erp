const COUNT_SOURCE_CONTRACT = Object.freeze({
  materialCount: 'MaterialMasterRuntimeAdapter',
  supplierCount: 'SupplierMasterRuntimeAdapter',
  supplierMaterialRelationCount: 'MaterialSupplierRelationRuntime',
  supplierPriceCount: 'SupplierMaterialPriceRuntime',
})

function runtimeCount(payload, field) {
  const value = payload?.[field]
  if (!Number.isInteger(value) || value < 0) {
    throw new Error(`MasterDataStatisticsRuntime ${field} unavailable`)
  }
  if (payload?.countSources?.[field] !== COUNT_SOURCE_CONTRACT[field]) {
    throw new Error(`MasterDataStatisticsRuntime ${field} source mismatch`)
  }
  return value
}

export function buildMasterDataStatisticsRuntime(payload = {}) {
  if (payload?.factLoadFacts?.factLoadStatus !== 'success'
    || payload?.runtimeCode !== 'MasterDataStatisticsRuntime') {
    throw new Error('MasterDataStatisticsRuntime facts unavailable')
  }
  return Object.freeze({
    materialCount: runtimeCount(payload, 'materialCount'),
    supplierCount: runtimeCount(payload, 'supplierCount'),
    supplierMaterialRelationCount: runtimeCount(payload, 'supplierMaterialRelationCount'),
    supplierPriceCount: runtimeCount(payload, 'supplierPriceCount'),
    countSources: Object.freeze({ ...payload.countSources }),
    runtimeCode: payload.runtimeCode,
    runtimeVersion: payload.runtimeVersion,
    factSource: 'MasterDataStatisticsRuntime',
    businessProgressWriteCount: Number(payload.businessProgressWriteCount),
  })
}

export { COUNT_SOURCE_CONTRACT }
