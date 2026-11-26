import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { nextTick, ref } from 'vue'
import { listPageAcceptanceContracts } from '../src/meta/runtime/pcePageAcceptanceRegistry.js'
import { usePceEnterpriseListRuntime } from '../src/meta/runtime/pceEnterpriseListContract.js'
import { SCM_7_GATE_LIST_CONTRACTS } from '../src/meta/schema/scm/scm7GateListContracts.js'

const cases = [
  {
    pageCode: 'purchase-inquiry', quick: 'INQ-002', filter: ['buyerName', '李采购'],
    rows: [
      { inquiryNo: 'INQ-001', sourceRequestNo: 'PR-001', buyerName: '王采购', inquiryDate: '2026-09-01', statusCode: 'draft', statusLabel: '草稿' },
      { inquiryNo: 'INQ-002', sourceRequestNo: 'PR-002', buyerName: '李采购', inquiryDate: '2026-09-02', statusCode: 'prepared', statusLabel: '已准备' },
    ],
  },
  {
    pageCode: 'purchase-inquiry-acceptance', quick: '华东供应商', filter: ['sourceRequestNo', 'PR-002'],
    rows: [
      { rowKey: '1', inquiryNo: 'INQ-001', sourceRequestNo: 'PR-001', supplierName: '华北供应商', materialCode: 'MAT-01', preparationStatus: 'ready' },
      { rowKey: '2', inquiryNo: 'INQ-002', sourceRequestNo: 'PR-002', supplierName: '华东供应商', materialCode: 'MAT-02', preparationStatus: 'pending' },
    ],
  },
  {
    pageCode: 'supplier-performance', quick: 'SUP-002', filter: ['supplierName', '供应商乙'],
    rows: [
      { supplierId: 'SUP-001', supplierName: '供应商甲', period: '2026-08' },
      { supplierId: 'SUP-002', supplierName: '供应商乙', period: '2026-09' },
    ],
  },
  {
    pageCode: 'buyer-performance', quick: 'BUY-002', filter: ['buyerName', '采购员乙'],
    rows: [
      { buyerId: 'BUY-001', buyerName: '采购员甲', period: '2026-08' },
      { buyerId: 'BUY-002', buyerName: '采购员乙', period: '2026-09' },
    ],
  },
  {
    pageCode: 'buyer-exception-analysis', quick: 'BUY-002', filter: ['buyerName', '采购员乙'],
    rows: [
      { buyerId: 'BUY-001', buyerName: '采购员甲', period: '2026-08' },
      { buyerId: 'BUY-002', buyerName: '采购员乙', period: '2026-09' },
    ],
  },
]

const evidence = []
for (const scenario of cases) {
  const contract = SCM_7_GATE_LIST_CONTRACTS[scenario.pageCode]
  assert.ok(contract.searchFields.length > 0, `${scenario.pageCode}: quick search fields`)
  assert.ok(contract.filterSchema.length >= 3, `${scenario.pageCode}: advanced filter fields`)
  const rows = ref([...scenario.rows])
  const runtime = usePceEnterpriseListRuntime({
    rows, filterSchema: contract.filterSchema, searchFields: contract.searchFields, pageCode: scenario.pageCode,
  })

  runtime.quickSearch.value = scenario.quick
  runtime.applySearch()
  await nextTick()
  assert.equal(runtime.filteredRows.value.length, 1, `${scenario.pageCode}: quick search affects results`)
  runtime.quickSearch.value = '__NO_RESULT__'
  runtime.applySearch()
  await nextTick()
  assert.equal(runtime.filteredRows.value.length, 0, `${scenario.pageCode}: quick search no-result state`)
  runtime.clearFilters()
  await nextTick()
  assert.equal(runtime.filteredRows.value.length, 2, `${scenario.pageCode}: quick search clear restores results`)

  runtime.updateFilter(...scenario.filter)
  await nextTick()
  assert.equal(runtime.filteredRows.value.length, 1, `${scenario.pageCode}: advanced filter affects results`)
  const retainedFilter = runtime.filters[scenario.filter[0]]
  rows.value = [...scenario.rows]
  await nextTick()
  assert.equal(runtime.filters[scenario.filter[0]], retainedFilter, `${scenario.pageCode}: refresh preserves filter state`)
  runtime.updateFilter(scenario.filter[0], '__NO_RESULT__')
  await nextTick()
  assert.equal(runtime.filteredRows.value.length, 0, `${scenario.pageCode}: advanced filter no-result state`)
  runtime.clearFilters()
  await nextTick()
  assert.equal(runtime.filteredRows.value.length, 2, `${scenario.pageCode}: advanced filter reset restores results`)

  evidence.push({
    pageCode: scenario.pageCode,
    quickSearch: 'PASS',
    advancedFilter: 'PASS',
    noResult: 'PASS',
    clearReset: 'PASS',
    refreshState: 'PASS',
    apiFilterParams: runtime.apiFilterParams.value,
  })
}

const registered = listPageAcceptanceContracts()
for (const scenario of cases) {
  const page = registered.find(item => item.pageCode === scenario.pageCode && (
    scenario.pageCode !== 'purchase-inquiry' || item.route === '/scm/purchase-inquiry'
  ))
  assert.ok(page, `${scenario.pageCode}: canonical page registered`)
  assert.ok(page.listContracts.some(list => list.quickSearchFields.length > 0 && list.advancedFilterSchema.length >= 3),
    `${scenario.pageCode}: acceptance contract bound`)
}

const output = path.resolve(import.meta.dirname, '..', 'test-results', 'scm-7-gate-remediation', 'functional-report.json')
fs.mkdirSync(path.dirname(output), { recursive: true })
fs.writeFileSync(output, `${JSON.stringify({ result: 'PASS', gateCount: 7, pages: evidence }, null, 2)}\n`, 'utf8')
console.log(JSON.stringify({ result: 'PASS', gateCount: 7, pageCount: evidence.length, report: output }, null, 2))
