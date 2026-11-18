import { SCM_7_GATE_LIST_CONTRACTS } from '../schema/scm/scm7GateListContracts.js'

export const SUPPLIER_PERFORMANCE_VERSION = 'V1.14.2.8.4.8.1.2'

export const pageDefinitions = {
  reconciliation: {
    title: '供应商对账', moduleCode: 'SCM_SUPPLIER_RECONCILIATION',
    factKey: 'reconciliationFacts', factType: 'SupplierReconciliationFacts',
    filterSchema: [
      { field: 'reconciliationNo', key: 'reconciliationNo', label: '对账编号', filterType: 'text' },
      { field: 'supplierName', key: 'supplierName', label: '供应商', filterType: 'select', optionsProvider: 'currentResultDistinctValues' },
      { field: 'period', key: 'period', label: '对账期间', filterType: 'daterange', apiFrom: 'periodFrom', apiTo: 'periodTo' },
      { field: 'statusCode', key: 'statusCode', label: '对账状态', filterType: 'select', options: [
        { value: 'draft', label: '草稿' }, { value: 'internal_review', label: '内部审核中' },
        { value: 'supplier_confirming', label: '供应商确认中' }, { value: 'completed', label: '对账完成' },
      ] },
    ],
  },
  buyer: {
    title: '采购员绩效', moduleCode: 'SCM_BUYER_PERFORMANCE',
    factKey: 'performanceFacts', factType: 'BuyerPerformanceFacts',
    filterSchema: SCM_7_GATE_LIST_CONTRACTS['buyer-performance'].filterSchema,
  },
  supplier: {
    title: '供应商绩效', moduleCode: 'SCM_SUPPLIER_PERFORMANCE',
    factKey: 'performanceFacts', factType: 'SupplierPerformanceFacts',
    filterSchema: SCM_7_GATE_LIST_CONTRACTS['supplier-performance'].filterSchema,
  },
}

export function normalizeSupplierPerformanceFacts(payload, kind) {
  const data = payload?.success === true && Array.isArray(payload.data?.results)
    ? payload.data
    : payload?.data?.data || payload?.data || payload
  const definition = pageDefinitions[kind]
  const facts = data?.[definition.factKey]
  const rows = Array.isArray(data?.results) ? data.results : []
  if (!facts || facts.factSource !== 'server' || facts.factLoadStatus !== 'success') {
    throw new Error(`${definition.factType} missing`)
  }
  const counts = [rows.length, facts.recordCount, data.diagnosticFacts?.recordCount,
    data.strictFacts?.recordCount, data.acceptanceFacts?.recordCount]
  if (new Set(counts).size !== 1) throw new Error(`${definition.factType} five-surface mismatch`)
  if (data.acceptanceFacts?.acceptanceStatus !== 'PASS' || data.acceptanceFacts?.unknownReason !== '') {
    throw new Error(`${definition.factType} acceptance failed`)
  }
  if (facts.dangerActionCount || facts.businessProgressWriteCount || facts.paymentExecutionWriteCount
    || facts.bankSendWriteCount || facts.financialImpactWriteCount) throw new Error('business boundary violated')
  return { rows, facts, diagnosticFacts: data.diagnosticFacts, strictFacts: data.strictFacts, acceptanceFacts: data.acceptanceFacts }
}
