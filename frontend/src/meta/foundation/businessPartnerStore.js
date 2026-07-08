import { addOperationLog } from '../manufacturing/manufacturingFoundationStore.js'
import { getFoundationState } from '../manufacturing/manufacturingFoundationStore.js'
import { getScmState } from '../scm/scmStore.js'
import { getPurchaseReceiveState } from '../wms/purchaseReceiveStore.js'
import { getWmsState } from '../wms/wmsStore.js'
import { getQmsState } from '../qms/qmsStore.js'
import { getPayablePrepareState } from '../finance/payablePrepareStore.js'
import { getPayableCheckState } from '../finance/payableCheckStore.js'
import { getInvoicePrepareState } from '../finance/invoicePrepareStore.js'
import { getAccountPayableDraftState } from '../finance/accountPayableDraftStore.js'
import { getSupplierPaymentDraftState } from '../finance/supplierPaymentDraftStore.js'

const STORAGE_KEY = 'business-partner-state-v1'

function clone(value) {
  return JSON.parse(JSON.stringify(value))
}

function nowText() {
  return new Date().toISOString()
}

function createId(prefix) {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`
}

function defaultSuppliers() {
  return [
    supplierRecord({
      supplierCode: 'SUP-0001',
      supplierName: '精工铝材供应商',
      supplierShortName: '精工铝材',
      bankName: '中国建设银行东莞制造业支行',
      bankAccountName: '精工铝材供应商',
      bankAccount: '6217000000008888999',
      defaultPaymentMethod: 'bankTransfer',
      remark: '默认供应商档案，仅用于本地流程验证。',
    }),
    supplierRecord({
      supplierCode: 'SUP-0007',
      supplierName: '设备维护供应商7',
      supplierShortName: '设备维护7',
      supplierType: 'service',
      bankName: '中国农业银行深圳制造业支行',
      bankAccountName: '设备维护供应商7',
      bankAccount: '6228480000007777666',
      defaultPaymentMethod: 'bankTransfer',
      remark: '默认供应商档案，仅用于本地流程验证。',
    }),
  ]
}

function defaultDealers() {
  return [
    dealerRecord({
      dealerCode: 'CUS-0001',
      dealerName: '华东经销商',
      dealerShortName: '华东经销',
      bankName: '招商银行上海分行',
      bankAccountName: '华东经销商',
      bankAccount: '6214830000001234567',
      salesRegion: '华东',
      remark: '默认经销商档案，为后续销售、应收、收款模块预留。',
    }),
    dealerRecord({
      dealerCode: 'CUS-0002',
      dealerName: '华南项目客户',
      dealerShortName: '华南项目',
      dealerType: 'projectCustomer',
      bankName: '中国银行广州分行',
      bankAccountName: '华南项目客户',
      bankAccount: '6216600000009876543',
      salesRegion: '华南',
      remark: '默认经销商档案，为后续销售、应收、收款模块预留。',
    }),
  ]
}

function defaultCompanyBankAccounts() {
  return [
    companyBankAccountRecord({
      accountCode: 'BANK-001',
      accountName: '广东智造科技有限公司',
      bankName: '中国工商银行深圳科技园支行',
      bankAccount: '6222020200008888666',
      currency: 'CNY',
      accountType: 'basic',
      isDefault: true,
    }),
    companyBankAccountRecord({
      accountCode: 'BANK-002',
      accountName: '广东智造科技有限公司',
      bankName: '中国建设银行深圳制造业支行',
      bankAccount: '6217000000009999888',
      currency: 'CNY',
      accountType: 'general',
      isDefault: false,
    }),
  ]
}

function defaultState() {
  return {
    suppliers: defaultSuppliers(),
    dealers: defaultDealers(),
    companyBankAccounts: defaultCompanyBankAccounts(),
    operationLogs: [],
  }
}

function supplierRecord(payload = {}) {
  const stamp = nowText()
  return {
    id: payload.id || createId('sup'),
    supplierCode: payload.supplierCode || '',
    supplierName: payload.supplierName || '',
    supplierShortName: payload.supplierShortName || '',
    supplierType: payload.supplierType || 'material',
    supplierLevel: payload.supplierLevel || 'A',
    supplierStatus: payload.supplierStatus || 'active',
    contactPerson: payload.contactPerson || '',
    contactPhone: payload.contactPhone || '',
    contactEmail: payload.contactEmail || '',
    address: payload.address || '',
    taxNo: payload.taxNo || '',
    invoiceTitle: payload.invoiceTitle || payload.supplierName || '',
    bankName: payload.bankName || '',
    bankAccount: payload.bankAccount || '',
    bankAccountName: payload.bankAccountName || payload.supplierName || '',
    defaultPaymentMethod: payload.defaultPaymentMethod || 'bankTransfer',
    sourceType: payload.sourceType || 'manual',
    sourceText: payload.sourceText || '',
    sourceSupplierIds: payload.sourceSupplierIds || [],
    importedSources: payload.importedSources || [],
    linkedMaterialSupplierRelationCount: Number(payload.linkedMaterialSupplierRelationCount || 0),
    linkedSupplierMaterialPriceCount: Number(payload.linkedSupplierMaterialPriceCount || 0),
    bankInfoMocked: payload.bankInfoMocked ?? false,
    bankInfoMockedAt: payload.bankInfoMockedAt || '',
    bankInfoMockRemark: payload.bankInfoMockRemark || '',
    paymentTerm: payload.paymentTerm || '月结30天',
    settlementCurrency: payload.settlementCurrency || 'CNY',
    qualityLevel: payload.qualityLevel || '合格',
    deliveryLevel: payload.deliveryLevel || '合格',
    priceLevel: payload.priceLevel || '标准',
    enabled: payload.enabled ?? true,
    remark: payload.remark || '',
    createdAt: payload.createdAt || stamp,
    updatedAt: payload.updatedAt || stamp,
  }
}

function dealerRecord(payload = {}) {
  const stamp = nowText()
  return {
    id: payload.id || createId('dealer'),
    dealerCode: payload.dealerCode || '',
    dealerName: payload.dealerName || '',
    dealerShortName: payload.dealerShortName || '',
    dealerType: payload.dealerType || 'distributor',
    dealerLevel: payload.dealerLevel || 'A',
    dealerStatus: payload.dealerStatus || 'active',
    contactPerson: payload.contactPerson || '',
    contactPhone: payload.contactPhone || '',
    contactEmail: payload.contactEmail || '',
    address: payload.address || '',
    taxNo: payload.taxNo || '',
    invoiceTitle: payload.invoiceTitle || payload.dealerName || '',
    bankName: payload.bankName || '',
    bankAccount: payload.bankAccount || '',
    bankAccountName: payload.bankAccountName || payload.dealerName || '',
    defaultReceiveMethod: payload.defaultReceiveMethod || 'bankTransfer',
    creditLimit: Number(payload.creditLimit || 0),
    settlementCurrency: payload.settlementCurrency || 'CNY',
    salesRegion: payload.salesRegion || '',
    salesPerson: payload.salesPerson || '',
    customerLevel: payload.customerLevel || '标准',
    enabled: payload.enabled ?? true,
    remark: payload.remark || '',
    createdAt: payload.createdAt || stamp,
    updatedAt: payload.updatedAt || stamp,
  }
}

function companyBankAccountRecord(payload = {}) {
  const stamp = nowText()
  return {
    id: payload.id || createId('bank'),
    accountCode: payload.accountCode || '',
    accountName: payload.accountName || '',
    bankName: payload.bankName || '',
    bankAccount: payload.bankAccount || '',
    currency: payload.currency || 'CNY',
    accountType: payload.accountType || 'general',
    enabled: payload.enabled ?? true,
    isDefault: payload.isDefault ?? false,
    remark: payload.remark || '',
    createdAt: payload.createdAt || stamp,
    updatedAt: payload.updatedAt || stamp,
  }
}

function normalizeState(raw = {}) {
  return {
    suppliers: (raw.suppliers || []).map(supplierRecord),
    dealers: (raw.dealers || []).map(dealerRecord),
    companyBankAccounts: (raw.companyBankAccounts || []).map(companyBankAccountRecord),
    operationLogs: raw.operationLogs || [],
  }
}

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return defaultState()
    const parsed = normalizeState(JSON.parse(raw))
    if (!parsed.suppliers.length && !parsed.dealers.length && !parsed.companyBankAccounts.length) return defaultState()
    return parsed
  } catch (error) {
    console.warn('[BUSINESS PARTNER STORE] fallback to defaults', error)
    return defaultState()
  }
}

let state = loadState()

function persist() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
}

function upsert(collection, record, matcher) {
  const index = collection.findIndex(matcher)
  if (index >= 0) collection[index] = record
  else collection.unshift(record)
}

function findBy(collection, key, value) {
  return (collection || []).find((item) => String(item[key] || '').toLowerCase() === String(value || '').toLowerCase()) || null
}

export function normalizeSupplierName(name) {
  return String(name || '').trim().replace(/\s+/g, '')
}

function textValue(value) {
  return String(value || '').trim()
}

function supplierHash(text = '') {
  let hash = 0
  String(text || '').split('').forEach((char) => {
    hash = ((hash * 31) + char.charCodeAt(0)) % 100000000
  })
  return String(hash || 1).padStart(8, '0')
}

export function buildSupplierCodeFromName(name) {
  return `SUP-H${supplierHash(name).slice(-6)}`
}

function mockBankAccount(seed = '') {
  return `6217${supplierHash(seed).padStart(12, '0').slice(-12)}`
}

function readStorageState(key, fallback = {}) {
  try {
    const raw = localStorage.getItem(key)
    return raw ? JSON.parse(raw) : fallback
  } catch (error) {
    console.warn('[BUSINESS PARTNER STORE] skip legacy storage source', key, error)
    return fallback
  }
}

function pushUnique(list, value) {
  const text = textValue(value)
  if (text && !list.includes(text)) list.push(text)
}

function sourceLabel(type = '') {
  return {
    foundationSupplier: '基础资料供应商',
    materialSupplierRelation: '物料供应商关系',
    supplierMaterialPrice: '供应商物料价格',
    scm: 'SCM采购链路',
    wms: 'WMS收货库存链路',
    qms: 'QMS来料检验链路',
    finance: '应付付款链路',
  }[type] || type || '历史业务归集'
}

function collectFromValue(value, sourceType, candidates, supplierLookup, seen = new WeakSet()) {
  if (!value || typeof value !== 'object') return
  if (seen.has(value)) return
  seen.add(value)

  if (Array.isArray(value)) {
    value.forEach((item) => collectFromValue(item, sourceType, candidates, supplierLookup, seen))
    return
  }

  const supplierId = textValue(value.supplierId || value.vendorId)
  const supplierCode = textValue(value.supplierCode || value.vendorCode)
  const supplierName = textValue(value.supplierName || value.vendorName || value.suggestedSupplierName || supplierLookup.get(supplierId)?.name)
  if (supplierId || supplierCode || supplierName) {
    candidates.push({
      supplierId,
      supplierCode: supplierCode || supplierLookup.get(supplierId)?.code || '',
      supplierName: supplierName || supplierLookup.get(supplierId)?.name || '',
      materialId: value.materialId || '',
      materialCode: value.materialCode || '',
      materialName: value.materialName || '',
      price: value.price || value.approvedPrice || value.quotedPrice || '',
      sourceType,
      sourceText: sourceLabel(sourceType),
    })
  }

  if (Array.isArray(value.candidateSuppliers)) {
    value.candidateSuppliers.forEach((item) => {
      if (typeof item === 'string') candidates.push({ supplierName: item, sourceType, sourceText: sourceLabel(sourceType) })
      else collectFromValue(item, sourceType, candidates, supplierLookup, seen)
    })
  }

  Object.values(value).forEach((child) => {
    if (child && typeof child === 'object') collectFromValue(child, sourceType, candidates, supplierLookup, seen)
  })
}

function foundationSupplierLookup(foundationState = getFoundationState()) {
  const lookup = new Map()
  ;(foundationState.suppliers || []).forEach((supplier) => {
    const id = textValue(supplier.id)
    if (!id) return
    lookup.set(id, {
      id,
      code: supplier.code || supplier.supplierCode || id,
      name: supplier.name || supplier.supplierName || supplier.shortName || id,
      raw: supplier,
    })
  })
  return lookup
}

export function collectSuppliersFromExistingData() {
  const candidates = []
  const foundationState = getFoundationState()
  const supplierLookup = foundationSupplierLookup(foundationState)

  collectFromValue(foundationState.suppliers || [], 'foundationSupplier', candidates, supplierLookup)
  collectFromValue(foundationState.materialSupplierRelations || [], 'materialSupplierRelation', candidates, supplierLookup)
  collectFromValue(foundationState.supplierMaterialPrices || [], 'supplierMaterialPrice', candidates, supplierLookup)
  collectFromValue(getScmState(), 'scm', candidates, supplierLookup)
  collectFromValue(getPurchaseReceiveState(), 'wms', candidates, supplierLookup)
  collectFromValue(getWmsState(), 'wms', candidates, supplierLookup)
  collectFromValue(getQmsState(), 'qms', candidates, supplierLookup)
  collectFromValue(getPayablePrepareState(), 'finance', candidates, supplierLookup)
  collectFromValue(getPayableCheckState(), 'finance', candidates, supplierLookup)
  collectFromValue(getInvoicePrepareState(), 'finance', candidates, supplierLookup)
  collectFromValue(getAccountPayableDraftState(), 'finance', candidates, supplierLookup)
  collectFromValue(getSupplierPaymentDraftState(), 'finance', candidates, supplierLookup)
  collectFromValue(readStorageState('payment-order-prepare-state-v1'), 'finance', candidates, supplierLookup)
  collectFromValue(readStorageState('payment-order-draft-state-v1'), 'finance', candidates, supplierLookup)

  const unique = new Map()
  candidates.forEach((candidate) => {
    const name = textValue(candidate.supplierName || supplierLookup.get(candidate.supplierId)?.name)
    const code = textValue(candidate.supplierCode || supplierLookup.get(candidate.supplierId)?.code)
    if (!name && !code && !candidate.supplierId) return
    const key = candidate.supplierId ? `id:${candidate.supplierId}` : `name:${normalizeSupplierName(name)}`
    const current = unique.get(key) || { ...candidate, supplierName: name, supplierCode: code, sources: [] }
    current.supplierName = current.supplierName || name
    current.supplierCode = current.supplierCode || code
    pushUnique(current.sources, candidate.sourceText || sourceLabel(candidate.sourceType))
    current.hasMaterialSupplierRelation = current.hasMaterialSupplierRelation || candidate.sourceType === 'materialSupplierRelation'
    current.hasSupplierMaterialPrice = current.hasSupplierMaterialPrice || candidate.sourceType === 'supplierMaterialPrice'
    unique.set(key, current)
  })

  writeBusinessPartnerLog('归集历史供应商', { targetType: 'supplierCollect', targetId: 'preview', detail: `发现供应商 ${unique.size} 个` })
  return Array.from(unique.values())
}

function findSupplierProfile(candidate = {}) {
  const byId = textValue(candidate.supplierId)
  const byCode = textValue(candidate.supplierCode)
  const byName = normalizeSupplierName(candidate.supplierName)
  return state.suppliers.find((supplier) => (
    (byId && (String(supplier.id) === byId || (supplier.sourceSupplierIds || []).map(String).includes(byId)))
    || (byCode && String(supplier.supplierCode || '').toLowerCase() === byCode.toLowerCase())
    || (byName && normalizeSupplierName(supplier.supplierName) === byName)
  )) || null
}

function fillMissing(target, key, value) {
  if (target[key] || value === undefined || value === null || value === '') return false
  target[key] = value
  return true
}

export function enrichSupplierBankInfo(supplier = {}) {
  const next = { ...supplier }
  const before = JSON.stringify([next.bankName, next.bankAccount, next.bankAccountName, next.defaultPaymentMethod])
  fillMissing(next, 'bankName', '中国建设银行东莞制造业支行')
  fillMissing(next, 'bankAccount', mockBankAccount(next.supplierCode || next.supplierName || next.id))
  fillMissing(next, 'bankAccountName', next.supplierName)
  fillMissing(next, 'defaultPaymentMethod', 'bankTransfer')
  const changed = before !== JSON.stringify([next.bankName, next.bankAccount, next.bankAccountName, next.defaultPaymentMethod])
  if (changed) {
    next.bankInfoMocked = true
    next.bankInfoMockedAt = nowText()
    next.bankInfoMockRemark = '历史供应商银行信息自动补齐，仅用于本地流程验证'
  }
  return { supplier: next, changed }
}

export function getSupplierProfileCompleteness(supplier = {}) {
  const missingBank = !supplier.bankName || !supplier.bankAccount || !supplier.bankAccountName || !supplier.defaultPaymentMethod
  if (!supplier.enabled) return { status: 'disabled', statusText: '停用', bankStatusText: missingBank ? '银行信息缺失' : '银行信息完整' }
  if (missingBank) return { status: 'missingBank', statusText: '银行信息缺失', bankStatusText: '银行信息缺失' }
  if (supplier.bankInfoMocked) return { status: 'mocked', statusText: '已自动补齐', bankStatusText: '模拟银行信息' }
  return { status: 'complete', statusText: '完整', bankStatusText: '银行信息完整' }
}

export function syncLegacySuppliersToSupplierProfiles(options = {}) {
  const candidates = collectSuppliersFromExistingData()
  const summary = { found: candidates.length, created: 0, updated: 0, enriched: 0, skipped: 0 }
  candidates.forEach((candidate) => {
    const existed = findSupplierProfile(candidate)
    if (existed) {
      const patch = { ...existed }
      let changed = false
      changed = fillMissing(patch, 'supplierCode', candidate.supplierCode || buildSupplierCodeFromName(candidate.supplierName)) || changed
      changed = fillMissing(patch, 'supplierName', candidate.supplierName) || changed
      changed = fillMissing(patch, 'sourceType', 'legacyImported') || changed
      changed = fillMissing(patch, 'sourceText', '来源：历史业务归集') || changed
      const ids = [...(patch.sourceSupplierIds || [])]
      if (candidate.supplierId && !ids.includes(candidate.supplierId)) { ids.push(candidate.supplierId); changed = true }
      patch.sourceSupplierIds = ids
      patch.importedSources = Array.from(new Set([...(patch.importedSources || []), ...(candidate.sources || []), candidate.sourceText].filter(Boolean)))
      if (candidate.hasMaterialSupplierRelation && !Number(patch.linkedMaterialSupplierRelationCount || 0)) {
        patch.linkedMaterialSupplierRelationCount = 1
        changed = true
      }
      if (candidate.hasSupplierMaterialPrice && !Number(patch.linkedSupplierMaterialPriceCount || 0)) {
        patch.linkedSupplierMaterialPriceCount = 1
        changed = true
      }
      if (options.enrichBank) {
        const enriched = enrichSupplierBankInfo(patch)
        Object.assign(patch, enriched.supplier)
        if (enriched.changed) { summary.enriched += 1; changed = true }
      }
      if (changed) {
        upsert(state.suppliers, supplierRecord({ ...patch, id: existed.id, createdAt: existed.createdAt, updatedAt: nowText() }), (item) => item.id === existed.id)
        summary.updated += 1
        writeBusinessPartnerLog('更新历史供应商档案', { targetType: 'supplier', targetId: existed.id, targetNo: patch.supplierCode, detail: patch.supplierName })
      } else {
        summary.skipped += 1
        writeBusinessPartnerLog('跳过重复供应商', { targetType: 'supplier', targetId: existed.id, targetNo: existed.supplierCode, detail: existed.supplierName })
      }
      return
    }

    const record = supplierRecord({
      supplierCode: candidate.supplierCode || buildSupplierCodeFromName(candidate.supplierName),
      supplierName: candidate.supplierName || candidate.supplierCode || candidate.supplierId,
      supplierShortName: candidate.supplierName || '',
      sourceType: 'legacyImported',
      sourceText: '来源：历史业务归集',
      sourceSupplierIds: candidate.supplierId ? [candidate.supplierId] : [],
      importedSources: candidate.sources || [candidate.sourceText || '历史业务归集'],
      linkedMaterialSupplierRelationCount: candidate.hasMaterialSupplierRelation ? 1 : 0,
      linkedSupplierMaterialPriceCount: candidate.hasSupplierMaterialPrice ? 1 : 0,
      remark: '由历史业务数据自动归集生成，请后续维护为真实供应商档案。',
    })
    const finalRecord = options.enrichBank ? enrichSupplierBankInfo(record).supplier : record
    if (finalRecord.bankInfoMocked) summary.enriched += 1
    state.suppliers.unshift(finalRecord)
    summary.created += 1
    writeBusinessPartnerLog('新增历史供应商档案', { targetType: 'supplier', targetId: finalRecord.id, targetNo: finalRecord.supplierCode, detail: finalRecord.supplierName })
  })
  persist()
  writeBusinessPartnerLog(options.enrichBank ? '归集并补齐历史供应商' : '归集历史供应商', { targetType: 'supplierCollect', targetId: 'run', detail: JSON.stringify(summary) })
  return { ...summary, suppliers: listSuppliers() }
}

export function enrichMissingSupplierBankInfo() {
  const summary = { found: state.suppliers.length, created: 0, updated: 0, enriched: 0, skipped: 0 }
  state.suppliers = state.suppliers.map((supplier) => {
    const enriched = enrichSupplierBankInfo(supplier)
    if (!enriched.changed) {
      summary.skipped += 1
      return supplier
    }
    summary.updated += 1
    summary.enriched += 1
    writeBusinessPartnerLog('补齐供应商银行信息', { targetType: 'supplier', targetId: supplier.id, targetNo: supplier.supplierCode, detail: supplier.supplierName })
    return supplierRecord({ ...enriched.supplier, id: supplier.id, createdAt: supplier.createdAt, updatedAt: nowText() })
  })
  persist()
  return { ...summary, suppliers: listSuppliers() }
}

export function writeBusinessPartnerLog(action, payload = {}) {
  const log = {
    id: createId('bplog'),
    module: '业务伙伴档案',
    action,
    targetType: payload.targetType || '',
    targetId: payload.targetId || '',
    targetNo: payload.targetNo || '',
    detail: payload.detail || '',
    createdAt: nowText(),
  }
  state.operationLogs.unshift(log)
  state.operationLogs = state.operationLogs.slice(0, 200)
  persist()
  addOperationLog({
    module: '业务伙伴档案',
    action,
    targetType: payload.targetType || '',
    targetId: payload.targetId || '',
    targetNo: payload.targetNo || '',
    detail: payload.detail || '',
  })
}

export function getBusinessPartnerState() { return clone(state) }
export function saveBusinessPartnerState(nextState) { state = normalizeState(nextState); persist(); return getBusinessPartnerState() }
export function resetBusinessPartnerState() { state = defaultState(); persist(); writeBusinessPartnerLog('恢复业务伙伴默认数据', { targetType: 'state' }); return getBusinessPartnerState() }

export function listSuppliers() { return clone(state.suppliers) }
export function getSupplierById(id) { return clone(findBy(state.suppliers, 'id', id)) }
export function getSupplierByName(name) { return clone(state.suppliers.find((item) => item.enabled && normalizeSupplierName(item.supplierName) === normalizeSupplierName(name)) || null) }
export function getSupplierByCode(code) { return clone(findBy(state.suppliers, 'supplierCode', code)) }
export function normalizePaymentMethod(value) {
  const text = String(value || '').trim()
  const lower = text.toLowerCase()
  if (['banktransfer', 'bank_transfer', 'transfer', 'wire', '银行转账', '銀行轉帳'].includes(lower) || text === '银行转账') return 'bankTransfer'
  if (['cash', '现金'].includes(lower) || text === '现金') return 'cash'
  if (['cheque', 'check', '支票'].includes(lower) || text === '支票') return 'cheque'
  if (['acceptance', '承兑'].includes(lower) || text === '承兑') return 'acceptance'
  if (['other', '其他'].includes(lower) || text === '其他') return 'other'
  return text || 'bankTransfer'
}
export function buildPaymentPrepareSupplierBankFields(supplier = {}) {
  return {
    supplierBankName: supplier.bankName || '',
    supplierBankAccount: supplier.bankAccount || '',
    supplierBankAccountName: supplier.bankAccountName || supplier.supplierName || '',
    paymentMethod: normalizePaymentMethod(supplier.defaultPaymentMethod || 'bankTransfer'),
  }
}
export function getSupplierProfileByIdentity({ supplierId = '', supplierCode = '', supplierName = '' } = {}) {
  const id = textValue(supplierId)
  const code = textValue(supplierCode)
  const name = normalizeSupplierName(supplierName)
  return clone(state.suppliers.find((supplier) => (
    supplier.enabled
    && (
      (id && (String(supplier.id) === id || (supplier.sourceSupplierIds || []).map(String).includes(id)))
      || (code && String(supplier.supplierCode || '').toLowerCase() === code.toLowerCase())
      || (name && normalizeSupplierName(supplier.supplierName) === name)
      || (name && normalizeSupplierName(supplier.supplierShortName) === name)
      || (name && (supplier.aliases || supplier.sourceNames || []).some((item) => normalizeSupplierName(item) === name))
    )
  )) || null)
}
export function findSupplierProfileForPayment(paymentPrepare = {}) {
  return getSupplierProfileByIdentity({
    supplierId: paymentPrepare.supplierId,
    supplierCode: paymentPrepare.supplierCode,
    supplierName: paymentPrepare.supplierName,
  })
}
export function createSupplier(payload) {
  const record = supplierRecord(payload)
  state.suppliers.unshift(record)
  persist()
  writeBusinessPartnerLog('新增供应商', { targetType: 'supplier', targetId: record.id, targetNo: record.supplierCode, detail: record.supplierName })
  return clone(record)
}
export function updateSupplier(id, patch = {}) {
  const current = findBy(state.suppliers, 'id', id)
  if (!current) return { success: false, error: '未找到供应商档案。' }
  const next = supplierRecord({ ...current, ...patch, id: current.id, createdAt: current.createdAt, updatedAt: nowText() })
  upsert(state.suppliers, next, (item) => item.id === id)
  persist()
  writeBusinessPartnerLog('编辑供应商', { targetType: 'supplier', targetId: next.id, targetNo: next.supplierCode, detail: next.supplierName })
  return { success: true, supplier: clone(next) }
}
export function disableSupplier(id) {
  const outcome = updateSupplier(id, { enabled: false, supplierStatus: 'inactive' })
  if (outcome.success) writeBusinessPartnerLog('停用供应商', { targetType: 'supplier', targetId: id, targetNo: outcome.supplier.supplierCode, detail: outcome.supplier.supplierName })
  return outcome
}
export function enableSupplier(id) {
  const outcome = updateSupplier(id, { enabled: true, supplierStatus: 'active' })
  if (outcome.success) writeBusinessPartnerLog('启用供应商', { targetType: 'supplier', targetId: id, targetNo: outcome.supplier.supplierCode, detail: outcome.supplier.supplierName })
  return outcome
}
export function seedDefaultSuppliers() { defaultSuppliers().forEach((item) => { if (!getSupplierByCode(item.supplierCode)) state.suppliers.push(item) }); persist(); return listSuppliers() }

export function listDealers() { return clone(state.dealers) }
export function getDealerById(id) { return clone(findBy(state.dealers, 'id', id)) }
export function getDealerByName(name) { return clone(state.dealers.find((item) => item.enabled && item.dealerName === name) || null) }
export function getDealerByCode(code) { return clone(findBy(state.dealers, 'dealerCode', code)) }
export function createDealer(payload) {
  const record = dealerRecord(payload)
  state.dealers.unshift(record)
  persist()
  writeBusinessPartnerLog('新增经销商', { targetType: 'dealer', targetId: record.id, targetNo: record.dealerCode, detail: record.dealerName })
  return clone(record)
}
export function updateDealer(id, patch = {}) {
  const current = findBy(state.dealers, 'id', id)
  if (!current) return { success: false, error: '未找到经销商档案。' }
  const next = dealerRecord({ ...current, ...patch, id: current.id, createdAt: current.createdAt, updatedAt: nowText() })
  upsert(state.dealers, next, (item) => item.id === id)
  persist()
  writeBusinessPartnerLog('编辑经销商', { targetType: 'dealer', targetId: next.id, targetNo: next.dealerCode, detail: next.dealerName })
  return { success: true, dealer: clone(next) }
}
export function disableDealer(id) {
  const outcome = updateDealer(id, { enabled: false, dealerStatus: 'inactive' })
  if (outcome.success) writeBusinessPartnerLog('停用经销商', { targetType: 'dealer', targetId: id, targetNo: outcome.dealer.dealerCode, detail: outcome.dealer.dealerName })
  return outcome
}
export function enableDealer(id) {
  const outcome = updateDealer(id, { enabled: true, dealerStatus: 'active' })
  if (outcome.success) writeBusinessPartnerLog('启用经销商', { targetType: 'dealer', targetId: id, targetNo: outcome.dealer.dealerCode, detail: outcome.dealer.dealerName })
  return outcome
}
export function seedDefaultDealers() { defaultDealers().forEach((item) => { if (!getDealerByCode(item.dealerCode)) state.dealers.push(item) }); persist(); return listDealers() }

export function listCompanyBankAccounts() { return clone(state.companyBankAccounts) }
export function getCompanyBankAccountById(id) { return clone(findBy(state.companyBankAccounts, 'id', id)) }
export function getDefaultCompanyBankAccount() { return clone(state.companyBankAccounts.find((item) => item.enabled && item.isDefault) || state.companyBankAccounts.find((item) => item.enabled) || null) }
export function createCompanyBankAccount(payload) {
  const record = companyBankAccountRecord(payload)
  if (record.isDefault) state.companyBankAccounts.forEach((item) => { item.isDefault = false })
  state.companyBankAccounts.unshift(record)
  persist()
  writeBusinessPartnerLog('新增企业银行账户', { targetType: 'companyBankAccount', targetId: record.id, targetNo: record.accountCode, detail: record.bankName })
  return clone(record)
}
export function updateCompanyBankAccount(id, patch = {}) {
  const current = findBy(state.companyBankAccounts, 'id', id)
  if (!current) return { success: false, error: '未找到企业银行账户。' }
  if (patch.isDefault) state.companyBankAccounts.forEach((item) => { item.isDefault = false })
  const next = companyBankAccountRecord({ ...current, ...patch, id: current.id, createdAt: current.createdAt, updatedAt: nowText() })
  upsert(state.companyBankAccounts, next, (item) => item.id === id)
  persist()
  writeBusinessPartnerLog(patch.isDefault ? '设置默认企业银行账户' : '编辑企业银行账户', { targetType: 'companyBankAccount', targetId: next.id, targetNo: next.accountCode, detail: next.bankName })
  return { success: true, companyBankAccount: clone(next) }
}
export function disableCompanyBankAccount(id) {
  const outcome = updateCompanyBankAccount(id, { enabled: false, isDefault: false })
  if (outcome.success) writeBusinessPartnerLog('停用企业银行账户', { targetType: 'companyBankAccount', targetId: id, targetNo: outcome.companyBankAccount.accountCode, detail: outcome.companyBankAccount.bankName })
  return outcome
}
export function enableCompanyBankAccount(id) {
  const outcome = updateCompanyBankAccount(id, { enabled: true })
  if (outcome.success) writeBusinessPartnerLog('启用企业银行账户', { targetType: 'companyBankAccount', targetId: id, targetNo: outcome.companyBankAccount.accountCode, detail: outcome.companyBankAccount.bankName })
  return outcome
}
export function seedDefaultCompanyBankAccounts() { defaultCompanyBankAccounts().forEach((item) => { if (!findBy(state.companyBankAccounts, 'accountCode', item.accountCode)) state.companyBankAccounts.push(item) }); persist(); return listCompanyBankAccounts() }
