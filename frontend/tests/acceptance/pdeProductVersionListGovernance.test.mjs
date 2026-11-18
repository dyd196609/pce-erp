import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { computed, ref } from 'vue'
import { usePceEnterpriseListRuntime } from '../../src/meta/runtime/pceEnterpriseListContract.js'

const here = path.dirname(fileURLToPath(import.meta.url))
const pagePath = path.resolve(here, '../../src/meta/pages/PdeProductVersionManagementPage.vue')
const pageSource = fs.readFileSync(pagePath, 'utf8')

for (const tableId of ['pde-product-version-history-table', 'pde-product-version-current-table']) {
  assert.match(pageSource, new RegExp(`table-id="${tableId}"`), `${tableId} must use the governed table runtime`)
}
assert.equal((pageSource.match(/<PceEnterpriseListTable/g) || []).length, 2, 'the two lists must use two runtime instances')
assert.match(pageSource, /保存时确认条件/)
assert.match(pageSource, /当前确认条件/)
assert.match(pageSource, /筛选结果 \{\{ historyFilteredRows\.length \}\} 项 \/ 本版共/)
assert.match(pageSource, /筛选结果 \{\{ currentFilteredRows\.length \}\} 项 \/ 当前整版共/)
assert.match(pageSource, /position="sticky"|data-pce-fixed-header|PceEnterpriseListTable/, 'fixed header must be inherited from the governed table')
assert.doesNotMatch(pageSource, /searchText=ref|historySearch=ref|reasonFilter=ref/, 'legacy page-local list controls must not remain')

const rows = ref([
  { id: 1, itemNo: 'A', designRevisionSortKey: 'R10', confirmationCode: 'CONFIRMABLE' },
  { id: 2, itemNo: 'B', designRevisionSortKey: 'R2', confirmationCode: 'BLOCKED' },
  { id: 3, itemNo: 'C', designRevisionSortKey: 'ZZZZZZ未记录', confirmationCode: 'BLOCKED' },
])
const runtime = usePceEnterpriseListRuntime({
  rows: computed(() => rows.value),
  filterSchema: [{
    field: 'confirmationCode', label: '确认条件', filterType: 'select',
    options: [{ value: 'CONFIRMABLE', label: '可确认' }, { value: 'BLOCKED', label: '阻断' }],
  }],
  searchFields: ['itemNo'],
})
runtime.handleSort({ prop: 'designRevisionSortKey', order: 'ascending' })
assert.deepEqual(runtime.filteredRows.value.map(row => row.designRevisionSortKey), ['R2', 'R10', 'ZZZZZZ未记录'], 'revision ordering must be numeric and missing must not impersonate R0')
runtime.updateFilter('confirmationCode', 'BLOCKED')
assert.deepEqual(runtime.filteredRows.value.map(row => row.itemNo), ['B', 'C'], 'filtering must apply before pagination')
runtime.clearFilters()
runtime.clearSort()
assert.deepEqual(runtime.filteredRows.value.map(row => row.itemNo), ['A', 'B', 'C'], 'reset must restore the complete default business order')

console.log('PDE product-version two-list governance: PASS')
