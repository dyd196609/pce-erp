export const PURCHASE_INQUIRY_RUNTIME_STORE_VERSION = 'V1.14.2.8.18.7'
export const PURCHASE_INQUIRY_RUNTIME_STORE_KEY = 'pce.scm.purchase-inquiry.runtime-store.v11428187'
export const PURCHASE_INQUIRY_LEGACY_SESSION_KEY = 'pce.scm.purchase-inquiries.v11428711'

const clone = value => JSON.parse(JSON.stringify(value))
const memoryRecords = []
const browserLocalStorage = () => typeof window !== 'undefined' ? window.localStorage : null
const browserSessionStorage = () => typeof window !== 'undefined' ? window.sessionStorage : null

function normalizeInquiry(inquiry = {}) {
  const statusCode = inquiry.statusCode || inquiry.status || 'draft'
  const runtimeState = inquiry.runtimeState || 'inquiry_draft'
  return {
    ...clone(inquiry), inquiryNo: String(inquiry.inquiryNo || ''),
    sourcePreparationNo: String(inquiry.sourcePreparationNo || ''),
    sourceRequestNo: String(inquiry.sourceRequestNo || ''),
    buyer: String(inquiry.buyer || inquiry.buyerName || ''),
    buyerName: String(inquiry.buyerName || inquiry.buyer || ''),
    lines: clone(inquiry.lines || inquiry.materialLines || []),
    suppliers: clone(inquiry.suppliers || inquiry.supplierCandidates || []),
    status: statusCode, statusCode,
    statusLabel: inquiry.statusLabel || (statusCode === 'draft' ? '草稿' : statusCode),
    businessStatusCode: statusCode,
    businessStatusLabel: inquiry.businessStatusLabel || inquiry.statusLabel || (statusCode === 'draft' ? '草稿' : statusCode),
    runtimeState,
    processStatusCode: runtimeState,
    processStatusLabel: inquiry.processStatusLabel || (runtimeState === 'quote_preparation_ready'
      ? '已进入供应商报价准备' : '询价编辑中'),
    persistenceMode: 'browser_runtime_store', productionDataWritten: false,
  }
}

export function createPurchaseInquiryRuntimeStore({ storage = browserLocalStorage(),
  legacyStorage = browserSessionStorage(), storageKey = PURCHASE_INQUIRY_RUNTIME_STORE_KEY } = {}) {
  const read = () => {
    if (!storage) return clone(memoryRecords)
    try {
      const persisted = JSON.parse(storage.getItem(storageKey) || '[]')
      if (persisted.length) return persisted.map(normalizeInquiry)
      const legacy = JSON.parse(legacyStorage?.getItem(PURCHASE_INQUIRY_LEGACY_SESSION_KEY) || '[]')
      if (legacy.length) {
        const migrated = legacy.map(normalizeInquiry)
        storage.setItem(storageKey, JSON.stringify(migrated))
        return migrated
      }
      return []
    } catch { return clone(memoryRecords) }
  }
  const write = records => {
    const normalized = records.map(normalizeInquiry)
    memoryRecords.splice(0, memoryRecords.length, ...normalized)
    if (storage) storage.setItem(storageKey, JSON.stringify(normalized))
    return clone(normalized)
  }
  return Object.freeze({
    storeCode: 'SCM_PURCHASE_INQUIRY_RUNTIME_STORE', version: PURCHASE_INQUIRY_RUNTIME_STORE_VERSION,
    storageMode: storage ? 'localStorage' : 'memory', storageKey,
    create(inquiry = {}) {
      const record = normalizeInquiry(inquiry)
      if (!record.inquiryNo) throw new Error('PURCHASE_INQUIRY_NO_REQUIRED')
      const records = read()
      if (records.some(item => item.inquiryNo === record.inquiryNo)) return this.save(record)
      write([...records, record])
      return Object.freeze(record)
    },
    save(inquiry = {}) {
      const record = normalizeInquiry(inquiry)
      if (!record.inquiryNo) throw new Error('PURCHASE_INQUIRY_NO_REQUIRED')
      const records = read()
      const index = records.findIndex(item => item.inquiryNo === record.inquiryNo)
      if (index < 0) records.push(record)
      else records.splice(index, 1, record)
      write(records)
      return Object.freeze(record)
    },
    replace(records = []) { return Object.freeze(write(records).map(Object.freeze)) },
    reload() { return Object.freeze(read().map(item => Object.freeze(normalizeInquiry(item)))) },
    find(inquiryNo = '') { return this.reload().find(item => item.inquiryNo === inquiryNo) || null },
  })
}

export const purchaseInquiryRuntimeStore = createPurchaseInquiryRuntimeStore()
