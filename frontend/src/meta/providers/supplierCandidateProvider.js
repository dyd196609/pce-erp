import { getSuppliers } from '../manufacturing/manufacturingFoundationStore.js'

export const SUPPLIER_CANDIDATE_PROVIDER_VERSION = 'V1.14.2.8.18.7'

export function createSupplierCandidateProvider({ supplierMasterLoader = getSuppliers } = {}) {
  const records = () => supplierMasterLoader().filter(item => item.enabled !== false
    && item.supplierStatus !== 'inactive' && item.status !== 'disabled').map(item => Object.freeze({
      supplierId: String(item.id || item.supplierId || item.supplierCode || ''),
      supplierCode: String(item.supplierCode || item.code || item.supplierId || item.id || ''),
      supplierName: String(item.supplierName || item.name || ''),
      supplierStatus: String(item.supplierStatus || item.status || item.businessStatus || 'active'),
      supplierCategory: String(item.supplierCategory || item.category || item.supplierType || 'unclassified'),
      label: `${item.supplierCode || item.code || item.supplierId || item.id || ''} ${item.supplierName || item.name || ''}`.trim(),
      value: String(item.id || item.supplierId || item.supplierCode || ''), source: 'Supplier Master',
    }))
  return Object.freeze({
    providerCode: 'SupplierCandidateProvider', source: 'Supplier Master', allowFreeText: false,
    load({ query = '' } = {}) {
      const keyword = String(query || '').trim().toLowerCase()
      const options = records().filter(item => !keyword
        || [item.supplierCode, item.supplierName, item.label].some(value => value.toLowerCase().includes(keyword)))
      return Object.freeze({ providerCode: this.providerCode, source: this.source,
        searchable: true, selectable: true, canAddCandidate: true, allowFreeText: false,
        recordCount: options.length, options: Object.freeze(options) })
    },
    resolveSelection(ids = []) {
      const selected = new Set(ids.map(String))
      return Object.freeze(records().filter(item => selected.has(item.value)).map(item => Object.freeze({
        supplierId: item.supplierId, supplierCode: item.supplierCode,
        supplierName: item.supplierName, supplierStatus: item.supplierStatus,
        supplierCategory: item.supplierCategory, source: item.source,
      })))
    },
  })
}

export const supplierCandidateProvider = createSupplierCandidateProvider()
