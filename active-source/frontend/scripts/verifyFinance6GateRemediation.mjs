import fs from 'node:fs'
import path from 'node:path'
import { ref } from 'vue'

import { financeProcessPageRegistry } from '../src/meta/process/financeProcessPageRegistry.js'
import { findPceBusinessModuleById } from '../src/meta/runtime/pceBusinessModuleRegistry.js'
import { usePceEnterpriseListRuntime } from '../src/meta/runtime/pceEnterpriseListContract.js'

const PAGE_CODES = Object.freeze([
  'payable-check',
  'payment-instruction-prepare',
  'payment-order-draft',
  'formal-payment-order',
  'bank-send-preparation',
  'bank-send-task',
])

const frontendRoot = path.resolve(import.meta.dirname, '..')
const resultRoot = path.join(frontendRoot, 'test-results', 'finance-6-gate-remediation')
const failures = []
const pages = []

function assert(condition, message) {
  if (!condition) failures.push(message)
}

for (const pageCode of PAGE_CODES) {
  const page = financeProcessPageRegistry.find(item => item.pageStepId === pageCode)
  const moduleRecord = findPceBusinessModuleById(pageCode)
  assert(page, `${pageCode}: canonical page missing`)
  assert(moduleRecord, `${pageCode}: business module missing`)
  if (!page || !moduleRecord) continue

  const source = fs.readFileSync(path.join(frontendRoot, page.pageComponent), 'utf8')
  const sourceChecks = {
    quickSearchEntry: /quickSearch/.test(source),
    advancedFilterEntry: /data-pce-filter-for=/.test(source) || /PceEnterpriseListTable/.test(source),
    clearResetEntry: /clearFilters/.test(source),
    actualResultBinding: /filteredRows/.test(source),
  }
  for (const [name, passed] of Object.entries(sourceChecks)) {
    assert(passed, `${pageCode}: ${name} missing from actual page`)
  }

  const dateFields = moduleRecord.advancedFilterSchema.filter(field => field.filterType === 'daterange')
  assert(dateFields.length > 0, `${pageCode}: real date filter missing`)
  assert(dateFields.every(field => field.type === 'dateRange'), `${pageCode}: semantic dateRange type missing`)
  assert(dateFields.every(field => field.queryType), `${pageCode}: date operator missing`)

  const searchField = moduleRecord.searchableFields[0]
  const rows = ref([
    { id: 1, [searchField]: 'ALPHA-001', __date: '2026-01-15' },
    { id: 2, [searchField]: 'BRAVO-002', __date: '2026-02-15' },
    { id: 3, [searchField]: 'CHARLIE-003', __date: '2026-03-15' },
  ])
  const runtime = usePceEnterpriseListRuntime({
    rows,
    filterSchema: moduleRecord.advancedFilterSchema,
    searchFields: moduleRecord.searchableFields,
    filterValueResolver: (row, field) => (
      field.filterType === 'daterange' ? row.__date : row[field.sourceKey || field.field]
    ),
  })

  assert(runtime.filteredRows.value.length === 3, `${pageCode}: initial result mismatch`)
  runtime.quickSearch.value = 'alpha'
  runtime.applySearch()
  assert(runtime.filteredRows.value.length === 1, `${pageCode}: quick search does not change results`)
  runtime.quickSearch.value = 'not-present'
  runtime.applySearch()
  assert(runtime.filteredRows.value.length === 0, `${pageCode}: no-result state is incorrect`)
  runtime.clearFilters()
  assert(runtime.filteredRows.value.length === 3, `${pageCode}: quick-search clear does not restore results`)

  const dateField = dateFields[0]
  const filterValue = dateField.field.endsWith('From')
    ? '2026-02-01'
    : dateField.field.endsWith('To')
      ? '2026-02-28'
      : ['2026-02-01', '2026-02-28']
  runtime.updateFilter(dateField.field, filterValue)
  const advancedCount = runtime.filteredRows.value.length
  assert(advancedCount > 0 && advancedCount < 3, `${pageCode}: advanced filter does not change results`)
  const refreshDate = dateField.field.endsWith('From') ? '2025-12-15' : '2026-04-15'
  rows.value = [...rows.value, { id: 4, [searchField]: 'DELTA-004', __date: refreshDate }]
  assert(runtime.filteredRows.value.length === advancedCount, `${pageCode}: refresh does not preserve filter state`)
  runtime.clearFilters()
  assert(runtime.filteredRows.value.length === 4, `${pageCode}: advanced reset does not restore refreshed rows`)

  pages.push({
    pageCode,
    canonicalRoute: page.routePath,
    sourceChecks,
    quickSearch: 'PASS',
    advancedFilter: 'PASS',
    operator: 'PASS',
    noResult: 'PASS',
    clearReset: 'PASS',
    refreshState: 'PASS',
    dateFields: dateFields.map(field => ({
      field: field.field,
      filterType: field.filterType,
      type: field.type,
      queryType: field.queryType,
    })),
  })
}

const report = {
  result: failures.length ? 'FAIL' : 'PASS',
  contractVersion: 'PCE-FINANCE-6-GATE-REAL-FUNCTION-V1',
  gateCount: PAGE_CODES.length,
  passedGateCount: pages.length - new Set(failures.map(item => item.split(':')[0])).size,
  pages,
  failures,
  productionBusinessFactCreate: 0,
}

fs.mkdirSync(resultRoot, { recursive: true })
fs.writeFileSync(
  path.join(resultRoot, 'functional-report.json'),
  `${JSON.stringify(report, null, 2)}\n`,
  'utf8',
)
console.log(JSON.stringify(report, null, 2))
if (failures.length) process.exit(1)
