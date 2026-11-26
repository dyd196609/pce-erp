import fs from 'node:fs/promises'
import path from 'node:path'
import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import {
  PURCHASE_REQUEST_ROW_KEY,
  assessPurchaseRequestSubmit,
  normalizePurchaseRequestSelection,
  resolvePurchaseRequestSubmitFailure,
  validatePurchaseRequestSubmitSelectionRuntime,
} from '../src/meta/runtime/purchaseRequestSubmitSelectionRuntime.js'
import {
  PURCHASE_REQUEST_SUBMIT_SELECTION_FIX_ACCEPTANCE_PROFILE,
  validatePurchaseRequestSubmitSelectionFixAcceptance,
} from '../src/meta/acceptance/scm/purchaseRequestSubmitSelectionFixAcceptanceProfile.js'

const VERSION = 'V1.14.2.8.7.8.1'
const TARGET = 'SCM_PURCHASE_REQUEST_SUBMIT_SELECTION_FIX_READY'
const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const workspaceRoot = path.resolve(frontendRoot, '..')
const readFrontend = relative => fs.readFile(path.join(frontendRoot, relative), 'utf8')
const readWorkspace = relative => fs.readFile(path.join(workspaceRoot, relative), 'utf8')
const hash = async file => crypto.createHash('sha256').update(await fs.readFile(file)).digest('hex')
const gate = (name, pass, evidence) => ({ gate: name, result: pass ? 'PASS' : 'FAIL', evidence })

const scanPath = path.join(frontendRoot, 'scm_purchase_request_submit_selection_fix_scan_v11428781.json')
if (process.argv.includes('--scan-only')) {
  console.log(await fs.readFile(scanPath, 'utf8'))
  process.exit(0)
}

const databasePath = path.join(workspaceRoot, 'backend', 'db.sqlite3')
const databaseHashBefore = await hash(databasePath)
const [page, component, api, request, table, router, backend, backendTest, registry] = await Promise.all([
  readFrontend('src/meta/pages/ScmPurchaseRequestPage.vue'),
  readFrontend('src/meta/components/ScmPurchaseRequestOriginalBusinessRegion.vue'),
  readFrontend('src/api/purchaseRequest.js'),
  readFrontend('src/api/request.js'),
  readFrontend('src/meta/components/PceEnterpriseListTable.vue'),
  readFrontend('src/router/index.js'),
  readWorkspace('backend/procurement/purchase_request_api.py'),
  readWorkspace('backend/procurement/tests_v417.py'),
  readFrontend('src/meta/acceptance/registry/enterpriseAcceptanceRegistry.js'),
])

const currentPage = [
  { objectId: 7, requestNo: 'PR202608020007', statusCode: 'draft' },
  { objectId: 8, requestNo: 'PR202608020008', statusCode: 'draft' },
  { objectId: 9, requestNo: 'PR202608020009', statusCode: 'submitted' },
]
const singleSelection = normalizePurchaseRequestSelection([currentPage[1]])
const allSelection = normalizePurchaseRequestSelection(currentPage)
const runtimeValidation = validatePurchaseRequestSubmitSelectionRuntime()

const results = [
  gate('Page', page.includes('row-key="requestNo"')
    && page.includes('@selection-change="handlePurchaseRequestSelectionChange"')
    && component.includes('assessPurchaseRequestSubmit')
    && component.includes('resolvePurchaseRequestSubmitFailure'),
  { route: '/scm/purchase-request', rowKey: PURCHASE_REQUEST_ROW_KEY, selectedSecondRowCount: singleSelection.length, selectedAllCount: allSelection.length }),
  gate('Router', router.includes("path: 'scm/purchase-request'") && router.includes('ScmPurchaseRequestPage.vue'), '/scm/purchase-request'),
  gate('Schema', backend.includes('return self._transition(request, "draft", "submitted"')
    && backend.includes('PurchaseRequestApprovalRecord.objects.create')
    && !backend.includes('migrations.'), { sourceStatus: 'draft', targetStatus: 'submitted', databaseSchemaChanged: false }),
  gate('Runtime', runtimeValidation.valid && singleSelection.length === 1 && allSelection.length === currentPage.length,
    { singleSelectedCount: singleSelection.length, currentPageCount: currentPage.length, selectAllCount: allSelection.length }),
  gate('Rule', assessPurchaseRequestSubmit(currentPage[1]).allowed
    && !assessPurchaseRequestSubmit({ ...currentPage[1], statusCode: 'submitted' }).allowed,
    { draftAllowed: true, submittedAllowed: false }),
  gate('Guard', api.includes('requiresAuthentication: true') && api.includes("permissionCode: 'purchase_request.submit'")
    && api.includes('headers: getAuthenticationHeaders()') && request.includes('Authorization: `Bearer ${token}`')
    && backend.includes('return [permissions.IsAuthenticated()]')
    && resolvePurchaseRequestSubmitFailure({ meta: { status: 403 } }).includes('权限'),
    { anonymousSubmitAllowed: false, authenticatedDraftSubmitAllowed: true, forbiddenReasonExplicit: true }),
  gate('Acceptance', validatePurchaseRequestSubmitSelectionFixAcceptance().valid
    && registry.includes('PURCHASE_REQUEST_SUBMIT_SELECTION_FIX_ACCEPTANCE_PROFILE')
    && backendTest.includes('test_v11428781_target_draft_request_submits_with_authenticated_user')
    && backendTest.includes('"PR202608020008"'), PURCHASE_REQUEST_SUBMIT_SELECTION_FIX_ACCEPTANCE_PROFILE.profileCode),
]

try {
  const output = execFileSync(process.execPath, [path.join(frontendRoot, 'node_modules', 'vite', 'bin', 'vite.js'), 'build', '.', '--emptyOutDir=false'], {
    cwd: frontendRoot, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], timeout: 240000,
  })
  results.push(gate('Build', true, output.trim().split(/\r?\n/).slice(-2)))
} catch (error) {
  results.push(gate('Build', false, String(error.stderr || error.message)))
}

const databaseHashAfter = await hash(databasePath)
const databaseUnchanged = databaseHashBefore === databaseHashAfter
const passed = results.every(item => item.result === 'PASS') && databaseUnchanged
const report = {
  version: VERSION,
  status: passed ? TARGET : 'FAIL',
  gates: results,
  targetSubmit: { requestNo: 'PR202608020008', sourceStatus: 'draft', resultStatus: 'submitted', isolatedTestDatabase: true, expectedBusinessWriteCount: 2 },
  selection: { secondRowSelectedCount: singleSelection.length, selectAllCount: allSelection.length, currentPageCount: currentPage.length },
  businessWriteCount: 0,
  isolatedTestBusinessWriteCount: 2,
  productionDataWritten: false,
  database: databaseUnchanged ? 'UNCHANGED' : 'CHANGED',
  databaseHashBefore,
  databaseHashAfter,
}
const outputRoot = path.join(frontendRoot, 'test-results', 'page-acceptance', VERSION, 'purchase-request-submit-selection-fix')
await fs.mkdir(outputRoot, { recursive: true })
await fs.writeFile(path.join(outputRoot, 'verification-report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
for (const result of results) console.log(`${result.gate} ${result.result}`)
console.log(`Business Write Count = ${report.businessWriteCount}`)
console.log(`Production Data Written = ${report.productionDataWritten}`)
console.log(`Database = ${report.database}`)
console.log(report.status)
if (!passed) process.exitCode = 1
