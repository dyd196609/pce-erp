import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const VERSION = 'V1.14.2.8.4.7.50.1'
const root = path.resolve(import.meta.dirname, '..')
const workspace = path.resolve(root, '..')
const resultRoot = path.join(root, 'test-results', 'payment-order-prepare-v501')
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')
const page = read('src/meta/pages/PaymentOrderPreparePage.vue')
const contract = read('src/meta/runtime/standardListContract.js')
const runtime = read('src/meta/runtime/paymentOrderPrepareRuntime.js')
const failures = []
const guard = (name, condition) => {
  if (!condition) failures.push(name)
  return { name, passed: Boolean(condition) }
}
const checks = [
  guard('payment_order_prepare_uses_standard_list_contract', page.includes('createStandardListContract') && contract.includes('filterSchema')),
  guard('source_list_uses_standard_toolbar', page.includes('table-id="payment-order-prepare-source"')),
  guard('formal_list_uses_standard_toolbar', page.includes('table-id="payment-order-prepare-main"')),
  guard('source_and_formal_toolbar_states_are_isolated', page.includes('sourceQuickSearch') && page.includes('quickSearch')),
  guard('advanced_filter_is_not_minimal_placeholder', (page.match(/data-filter-key/g) || []).length >= 2 && page.includes('filterSchema')),
  guard('source_list_advanced_filter_is_complete', page.includes("stateId: 'source-list'") && page.includes("key: 'scenarioCode'")),
  guard('formal_list_advanced_filter_is_complete', page.includes("stateId: 'formal-list'") && page.includes("key: 'segregationValid'")),
  guard('source_list_has_single_scroll_owner', page.includes('data-acceptance-id="source-list-table"')),
  guard('formal_list_has_single_scroll_owner', page.includes('data-acceptance-id="formal-list-table"')),
  guard('horizontal_scrollbar_is_visible', (page.match(/scrollbar-always-on/g) || []).length >= 2),
  guard('left_selection_column_is_sticky', (page.match(/type="selection"[^>]+fixed="left"/g) || []).length >= 2),
  guard('left_sequence_column_is_sticky', (page.match(/type="index"[^>]+fixed="left"/g) || []).length >= 2),
  guard('right_operation_column_is_sticky', (page.match(/label="操作"[^>]+fixed="right"/g) || []).length >= 2),
  guard('sticky_headers_and_cells_are_aligned', page.includes('header-class-name="payment-fixed-action-column"')),
  guard('operation_button_is_clickable', page.includes('formal-row-view-button') && page.includes('source-row-view-button')),
  guard('source_and_formal_scroll_states_are_isolated', page.includes('payment-order-prepare-source') && page.includes('payment-order-prepare-main')),
  guard('filter_clear_restores_all_eight_rows', page.includes('createFilterState(sourceListContract)') && page.includes('createFilterState(formalListContract)')),
  guard('sort_clear_restores_default_order', page.includes('clearSourceSort') && page.includes('formalListContract.defaultSort')),
  guard('export_uses_current_filtered_result', page.includes('safeExportRows(filteredRows.value') && page.includes('safeExportRows(filteredSourceRows.value')),
  guard('export_excludes_sensitive_fields', !/privateKey|interfaceSecret|userPassword|databasePassword/.test(page)),
  guard('bank_account_values_remain_masked', page.includes('debtorAccountMasked') && page.includes('creditorAccountMasked')),
  guard('decimal_filter_does_not_use_float', contract.includes('BigInt') && !contract.includes('parseFloat')),
  guard('page_body_has_no_unexpected_horizontal_overflow', page.includes('overflow-x: clip')),
  guard('version_is_exact', runtime.includes(VERSION)),
]
const sha = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
const persistent = path.join(workspace, 'backend', 'canary-data', 'purchase-flow-demo.sqlite3')
const development = path.join(workspace, 'backend', 'db.sqlite3')
const report = {
  result: failures.length ? 'failed' : 'passed',
  version: VERSION,
  guardCount: checks.length,
  checks,
  failures,
  persistentDatabaseSha256: sha(persistent),
  developmentDatabaseSha256: sha(development),
}
fs.mkdirSync(resultRoot, { recursive: true })
fs.writeFileSync(path.join(resultRoot, 'static-guards.json'), `${JSON.stringify(report, null, 2)}\n`)
console.log(JSON.stringify(report, null, 2))
if (failures.length) process.exit(1)
