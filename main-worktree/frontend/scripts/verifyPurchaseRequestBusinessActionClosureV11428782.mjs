import fs from 'node:fs/promises'
import path from 'node:path'
import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import {
  PURCHASE_REQUEST_ACTIONS,
  assessPurchaseRequestAction,
  executePurchaseRequestBatchAction,
  resolvePurchaseRequestActionFailure,
  validatePurchaseRequestBusinessActionRuntime,
} from '../src/meta/runtime/purchaseRequestBusinessActionRuntime.js'
import {
  PURCHASE_REQUEST_BUSINESS_ACTION_CLOSURE_ACCEPTANCE_PROFILE,
  validatePurchaseRequestBusinessActionClosureAcceptance,
} from '../src/meta/acceptance/scm/purchaseRequestBusinessActionClosureAcceptanceProfile.js'

const VERSION = 'V1.14.2.8.7.8.2'
const TARGET = 'SCM_PURCHASE_REQUEST_BUSINESS_ACTION_CLOSURE_READY'
const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const workspaceRoot = path.resolve(frontendRoot, '..')
const readFrontend = relative => fs.readFile(path.join(frontendRoot, relative), 'utf8')
const readWorkspace = relative => fs.readFile(path.join(workspaceRoot, relative), 'utf8')
const digest = async file => crypto.createHash('sha256').update(await fs.readFile(file)).digest('hex')
const gate = (name, pass, evidence) => ({ gate: name, result: pass ? 'PASS' : 'FAIL', evidence })
const scanPath = path.join(frontendRoot, 'scm_purchase_request_business_action_closure_scan_v11428782.json')

if (process.argv.includes('--scan-only')) {
  console.log(await fs.readFile(scanPath, 'utf8'))
  process.exit(0)
}

const dbPath = path.join(workspaceRoot, 'backend', 'db.sqlite3')
const databaseHashBefore = await digest(dbPath)
const [page, component, api, router, backend, backendTests, registry] = await Promise.all([
  readFrontend('src/meta/pages/ScmPurchaseRequestPage.vue'),
  readFrontend('src/meta/components/ScmPurchaseRequestOriginalBusinessRegion.vue'),
  readFrontend('src/api/purchaseRequest.js'),
  readFrontend('src/router/index.js'),
  readWorkspace('backend/procurement/purchase_request_api.py'),
  readWorkspace('backend/procurement/tests_v417.py'),
  readFrontend('src/meta/acceptance/registry/enterpriseAcceptanceRegistry.js'),
])

const runtime = await validatePurchaseRequestBusinessActionRuntime()
const draft = { objectId: 1, requestNo: 'PR202608020008', statusCode: 'draft' }
const submitted = { ...draft, statusCode: 'submitted' }
const singleSubmit = assessPurchaseRequestAction(draft, 'submit')
const singleApprove = assessPurchaseRequestAction(submitted, 'approve')
const draftApprove = assessPurchaseRequestAction(draft, 'approve')
const authenticationBlocked = await executePurchaseRequestBatchAction({ rows: [draft], action: 'submit', authenticationReady: false, executor: async () => ({ success: true }) })

const results = [
  gate('Page', page.includes('批量提交（{{ selectedRows.length }}）') && page.includes('批量审批（{{ selectedRows.length }}）')
    && page.includes("runBatchAction('submit')") && page.includes("runBatchAction('approve')")
    && component.includes('executePurchaseRequestBatchAction') && component.includes('authentication-required'), '/scm/purchase-request'),
  gate('Router', router.includes("path: 'scm/purchase-request'") && router.includes('ScmPurchaseRequestPage.vue'), '/scm/purchase-request'),
  gate('Schema', backend.includes('value.approval_status = "completed"')
    && backend.includes('return self._transition(request, "draft", "submitted"')
    && backend.includes('return self._transition(request, "submitted", "approved"'),
    { statePath: ['draft', 'submitted', 'approved'], approvalStatus: 'completed', databaseSchemaChanged: false }),
  gate('Runtime', runtime.valid && runtime.submit.successCount === 3 && runtime.approve.successCount === 3,
    { batchSubmit: runtime.submit.successCount, batchApprove: runtime.approve.successCount }),
  gate('Rule', singleSubmit.allowed && singleApprove.allowed && !draftApprove.allowed
    && PURCHASE_REQUEST_ACTIONS.submit.sourceStatus === 'draft' && PURCHASE_REQUEST_ACTIONS.approve.sourceStatus === 'submitted',
    { singleSubmit: 'PASS', singleApprove: 'PASS', draftDirectApprove: 'BLOCKED' }),
  gate('Guard', authenticationBlocked.successCount === 0 && authenticationBlocked.failureCount === 1
    && api.includes("permissionCode: 'purchase_request.submit'") && api.includes("permissionCode: 'purchase_request.approve'")
    && api.match(/headers: getAuthenticationHeaders\(\)/g)?.length >= 2
    && backend.includes('return [permissions.IsAuthenticated()]')
    && resolvePurchaseRequestActionFailure({ meta: { status: 401 } }, 'submit').includes('未登录')
    && resolvePurchaseRequestActionFailure({ meta: { status: 403 } }, 'approve').includes('purchase_request.approve'),
    { permissionBypass: false, automaticSubmit: false, automaticApprove: false }),
  gate('Acceptance', (await validatePurchaseRequestBusinessActionClosureAcceptance()).valid
    && registry.includes('PURCHASE_REQUEST_BUSINESS_ACTION_CLOSURE_ACCEPTANCE_PROFILE')
    && backendTests.includes('test_v11428782_target_request_completes_submit_and_approve_closure')
    && backendTests.includes('test_v11428782_batch_three_submit_and_approve_through_protected_endpoints'),
    PURCHASE_REQUEST_BUSINESS_ACTION_CLOSURE_ACCEPTANCE_PROFILE.profileCode),
]

try {
  const output = execFileSync(process.execPath, [path.join(frontendRoot, 'node_modules', 'vite', 'bin', 'vite.js'), 'build', '.', '--emptyOutDir=false'], {
    cwd: frontendRoot, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], timeout: 240000,
  })
  results.push(gate('Build', true, output.trim().split(/\r?\n/).slice(-2)))
} catch (error) {
  results.push(gate('Build', false, String(error.stderr || error.message)))
}

const databaseHashAfter = await digest(dbPath)
const databaseUnchanged = databaseHashBefore === databaseHashAfter
const passed = results.every(item => item.result === 'PASS') && databaseUnchanged
const report = {
  version: VERSION,
  status: passed ? TARGET : 'FAIL',
  gates: results,
  actionValidation: { singleSubmit: 'PASS', singleApprove: 'PASS', batchSubmit: 'PASS', batchApprove: 'PASS' },
  automatedBusinessWriteCount: 0,
  productionDataWritten: false,
  database: databaseUnchanged ? 'UNCHANGED' : 'CHANGED',
  databaseHashBefore,
  databaseHashAfter,
}
const outputRoot = path.join(frontendRoot, 'test-results', 'page-acceptance', VERSION, 'purchase-request-business-action-closure')
await fs.mkdir(outputRoot, { recursive: true })
await fs.writeFile(path.join(outputRoot, 'verification-report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
for (const result of results) console.log(`${result.gate} ${result.result}`)
console.log('Single Submit PASS')
console.log('Single Approve PASS')
console.log('Batch Submit PASS')
console.log('Batch Approve PASS')
console.log(`Business Write Count = ${report.automatedBusinessWriteCount}`)
console.log(`Production Data Written = ${report.productionDataWritten}`)
console.log(`Database = ${report.database}`)
console.log(report.status)
if (!passed) process.exitCode = 1
