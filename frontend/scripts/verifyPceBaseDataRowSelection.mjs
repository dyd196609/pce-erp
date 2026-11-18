import fs from 'node:fs'
import path from 'node:path'
import {
  applyHeaderSelection,
  applySingleRowSelection,
} from '../src/meta/runtime/baseDataRowSelectionContract.js'

const root = path.resolve(import.meta.dirname, '..')
const table = fs.readFileSync(path.join(root, 'src/meta/components/PceEnterpriseListTable.vue'), 'utf8')
const failures = []
for (const marker of ['@select="handleSingleRowSelection"', '@select-all="handleHeaderSelection"', '已选择 {{ selectedCount }} 条']) {
  if (!table.includes(marker)) failures.push(`shared table binding missing: ${marker}`)
}
for (const marker of [':row-key="resolveRowIdentity"', 'props.primaryField']) {
  if (!table.includes(marker)) failures.push(`shared row identity fallback missing: ${marker}`)
}
const rows = [{ id: 1 }, { id: 2 }, { id: 3 }]
let selected = applySingleRowSelection([], rows[0], true)
if (selected.length !== 1 || selected[0].id !== 1) failures.push('single row select must equal 1')
selected = applySingleRowSelection(selected, rows[1], true)
if (selected.length !== 2) failures.push('second row select must equal 2')
selected = applySingleRowSelection(selected, rows[0], false)
if (selected.length !== 1 || selected[0].id !== 2) failures.push('single row deselect changed another row')
selected = applyHeaderSelection(selected, rows, true)
if (selected.length !== 3) failures.push('header select-all did not select visible scope')
selected = applyHeaderSelection(selected, rows, false)
if (selected.length !== 0) failures.push('header clear-all did not clear visible scope')
const outside = { id: 9 }
selected = applyHeaderSelection([outside], rows.slice(0, 2), true)
if (selected.length !== 3 || !selected.some(row => row.id === 9)) failures.push('filtered selection scope was not preserved')
const suppliersWithoutId = [{ code: 'SUP001' }, { code: 'SUP002' }]
const supplierIdentity = row => `code:${row.code}`
let supplierSelection = applySingleRowSelection([], suppliersWithoutId[0], true, supplierIdentity)
supplierSelection = applySingleRowSelection(supplierSelection, suppliersWithoutId[1], true, supplierIdentity)
if (supplierSelection.length !== 2) failures.push('primary-field fallback must keep supplier rows distinct when id is absent')

if (failures.length) {
  console.error(JSON.stringify({ gate: 'verify:pce-base-data-row-selection', status: 'FAIL', failures }, null, 2))
  process.exit(1)
}
console.log(JSON.stringify({
  gate: 'verify:pce-base-data-row-selection', status: 'PASS',
  singleRowSelect: 1, secondRowSelect: 2, singleRowDeselect: 1,
  headerSelectAll: 3, headerClearAll: 0, filteredSelectionScope: 'PASS',
  missingIdPrimaryIdentity: 'PASS',
  businessWrites: 0,
}, null, 2))
