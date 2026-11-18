import fs from 'node:fs'
import path from 'node:path'

const VERSION = 'V1.14.2.8.4.7.57.1'
const root = process.cwd()
const workspace = path.resolve(root, '..')
const read = file => fs.readFileSync(path.join(workspace, file), 'utf8')
const operationSource = read('backend/purchase_canary/operation_data.py')
const pageSource = read('frontend/src/meta/pages/PayableCheckPage.vue')
const checks = {
  contractImplemented: operationSource.includes('PCE-CANARY-OPERATION-DATA-V1.0'),
  exactPoolCapacity: [
    'pendingCheckCount', 'checkedCount', 'len(rows) == 16',
    'pending_count == 8', 'checked_count == 8',
  ].every(value => operationSource.includes(value)),
  isolatedCommandGuarded: [
    'PCE_V571_ISOLATED_ACCEPTANCE',
    'pce-canary-operation-data-v571-iab.sqlite3',
  ].every(value => read('backend/purchase_canary/management/commands/ensure_canary_operation_data_v571.py').includes(value)),
  apiUsesServerFacts: [
    'payable_check_operation_rows',
    'payable_check_operation_facts',
    '"currentStateSource": "server"',
  ].every(value => read('backend/purchase_canary/views.py').includes(value)),
  pageUsesServerPool: [
    'getCanaryOperationData',
    'canaryOperationEnabled',
    'payable-check-canary-operation-strict-facts',
    "strictFacts: canaryOperationEnabled.value",
  ].every(value => pageSource.includes(value)),
  diagnosticCarriesRequiredContract: [
    'moduleCode: row.moduleCode', 'scenarioCode: row.scenarioCode',
    'objectState: row.objectState', 'availableActions: row.availableActions',
    'expectedAction: row.expectedAction', 'preservePurpose: row.preservePurpose',
  ].every(value => pageSource.includes(value)),
  standardsUpdated: (
    read('docs/standards/PCE-CANARY-OPERATION-DATA-V1.0.md')
      .includes('PCE-CANARY-OPERATION-DATA-V1.0')
    && read('docs/standards/PCE-WEB-ACCEPTANCE-V1.1.md')
      .includes('所有用户操作验收页面必须具备服务端可操作金丝雀数据')
  ),
  migrationAdded: fs.readdirSync(path.join(workspace, 'backend', 'purchase_canary', 'migrations'))
    .some(name => name.includes('v571') || name.startsWith('0003_')),
}
const failed = Object.entries(checks)
  .filter(([key, passed]) => key === 'migrationAdded' ? passed : !passed)
  .map(([key]) => key)
const report = {
  result: failed.length ? 'blocked' : 'passed',
  version: VERSION,
  contractVersion: 'PCE-CANARY-OPERATION-DATA-V1.0',
  checks,
  failed,
  migrationExecuted: false,
  productionUserDataWritten: false,
}
const target = path.join(root, 'test-results', 'canary-operation-data-v571')
fs.mkdirSync(target, { recursive: true })
fs.writeFileSync(path.join(target, 'static-verification-report.json'), `${JSON.stringify(report, null, 2)}\n`)
console.log(JSON.stringify(report, null, 2))
if (failed.length) process.exit(1)
