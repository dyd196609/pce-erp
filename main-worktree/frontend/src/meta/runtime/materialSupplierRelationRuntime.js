import {
  currentResultRemoteSelectOptionsProvider,
  materialMasterRemoteSelectOptionsProvider,
  supplierMasterRemoteSelectOptionsProvider,
} from '@/meta/runtime/remoteSelectOptionsProvider.js'

export const MATERIAL_SUPPLIER_RELATION_RUNTIME_FIELDS = Object.freeze([
  Object.freeze({ key: 'relationCode', label: '关系编号', filterType: 'remote-select', optionsSource: 'CurrentResultDropdownRuntime', optionsProvider: currentResultRemoteSelectOptionsProvider }),
  Object.freeze({ key: 'materialDisplay', label: '物料', filterType: 'remote-select', sourceKey: 'materialCode', optionsSource: 'MaterialMasterRuntimeAdapter', optionsProvider: materialMasterRemoteSelectOptionsProvider }),
  Object.freeze({ key: 'supplierDisplay', label: '供应商', filterType: 'remote-select', sourceKey: 'supplierCode', optionsSource: 'SupplierMasterRuntimeAdapter', optionsProvider: supplierMasterRemoteSelectOptionsProvider }),
  Object.freeze({ key: 'isMainSupplierLabel', label: '主供应商', type: 'select', filterType: 'select', options: Object.freeze([{ value: '是', label: '是' }, { value: '否', label: '否' }]) }),
  Object.freeze({ key: 'priority', label: '优先级', type: 'number', filterType: 'number' }),
  Object.freeze({ key: 'deliveryPeriod', label: '交货周期（天）', type: 'number', filterType: 'number' }),
  Object.freeze({ key: 'qualityLevel', label: '质量等级' }),
  Object.freeze({ key: 'onTimeRateLabel', label: '准时率' }),
  Object.freeze({ key: 'statusLabel', label: '状态', type: 'select', filterType: 'select', options: Object.freeze([{ value: '启用', label: '启用' }]) }),
])

export const MATERIAL_SUPPLIER_RELATION_LIST_METADATA = Object.freeze({
  entityCode: 'material-suppliers',
  metadataCode: 'PCE-MD-MATERIAL-SUPPLIER-RELATION-LIST',
  metadataVersion: 'V1.14.2.8.4.27.2.32',
  metadataSource: 'MaterialSupplierRelationRuntime',
  pageCode: 'foundation-material-suppliers',
  route: '/foundation/erp/material-suppliers',
  collection: 'materialSupplierRelations',
  title: '物料供应商关系',
  pageKind: 'config',
  actionPolicy: Object.freeze(['view', 'edit']),
  primaryField: 'relationCode',
  primaryLabel: '关系编号',
  fields: MATERIAL_SUPPLIER_RELATION_RUNTIME_FIELDS,
  columns: Object.freeze(MATERIAL_SUPPLIER_RELATION_RUNTIME_FIELDS.slice(1)),
  searchFields: Object.freeze(MATERIAL_SUPPLIER_RELATION_RUNTIME_FIELDS.map(item => item.key)),
  filterSchema: Object.freeze(MATERIAL_SUPPLIER_RELATION_RUNTIME_FIELDS.map(item => Object.freeze({
    field: item.key,
    label: item.label,
    filterType: item.type === 'number' ? 'numberRange' : (item.filterType || 'text'),
    options: item.options || Object.freeze([]),
    optionsSource: item.optionsSource || (item.options?.length ? 'MaterialSupplierRelationRuntime' : 'none'),
    optionsProvider: item.optionsProvider || (item.options?.length ? 'MaterialSupplierRelationRuntime' : 'none'),
    sourceKey: item.sourceKey || item.key,
  }))),
})

const REQUIRED_FIELDS = Object.freeze([
  'relationCode', 'materialCode', 'materialName', 'materialDisplay',
  'supplierCode', 'supplierName', 'supplierDisplay', 'isMainSupplier',
  'isMainSupplierLabel', 'priority', 'qualityLevel', 'onTimeRateLabel',
  'status', 'statusLabel', 'sourceReference', 'sourceModules',
  'businessUsageCount', 'quoteCount', 'recommendationCount',
  'purchaseOrderReferenceCount', 'source',
])

function normalizeRow(row = {}) {
  for (const field of REQUIRED_FIELDS) {
    if (row[field] === undefined || row[field] === null || row[field] === '') {
      throw new Error(`MaterialSupplierRelation Runtime field unavailable: ${field}`)
    }
  }
  if (row.source !== 'MaterialSupplierRelationRuntime') {
    throw new Error('MaterialSupplierRelation Runtime source mismatch')
  }
  return Object.freeze({
    ...row,
    sourceModules: Object.freeze([...row.sourceModules]),
  })
}

export function buildMaterialSupplierRelationRuntime(payload = {}) {
  if (payload?.factLoadFacts?.factLoadStatus !== 'success'
    || payload?.runtimeCode !== 'MaterialSupplierRelationRuntime'
    || !Array.isArray(payload?.rows)) {
    throw new Error('MaterialSupplierRelation Runtime facts unavailable')
  }
  const rows = Object.freeze(payload.rows.map(normalizeRow))
  if (rows.length !== payload.relationCount) {
    throw new Error('MaterialSupplierRelation Runtime count mismatch')
  }
  return Object.freeze({
    rows,
    usageMatrix: Object.freeze([...(payload.usageMatrix || [])]),
    unresolvedMappings: Object.freeze([...(payload.unresolvedMappings || [])]),
    sourceSummary: Object.freeze({ ...(payload.sourceSummary || {}) }),
    relationCount: payload.relationCount,
    duplicateRelationCount: payload.duplicateRelationCount,
    runtimeCode: payload.runtimeCode,
    runtimeVersion: payload.pageVersion,
    businessProgressWriteCount: Number(payload.businessProgressWriteCount),
  })
}
