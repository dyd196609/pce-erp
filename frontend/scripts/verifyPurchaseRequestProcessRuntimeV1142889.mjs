import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

import { createInquiryPreparation } from '../src/meta/runtime/inquiryPreparationRuntime.js'
import {
  runPurchaseRequestEndToEndBusinessWalkthrough,
  validatePurchaseRequestProcessAcceptance,
} from '../src/meta/process/scm/purchaseRequest/purchaseRequestProcessAcceptanceProfile.js'
import { validatePurchaseRequestInquiryHandoff } from '../src/meta/process/scm/purchaseRequest/purchaseRequestInquiryHandoffContract.js'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const workspaceRoot = path.resolve(frontendRoot, '..')
const read = relative => fs.readFileSync(path.join(frontendRoot, relative), 'utf8')
const databasePath = path.join(workspaceRoot, 'backend', 'db.sqlite3')
const hashDatabase = () => crypto.createHash('sha256').update(fs.readFileSync(databasePath)).digest('hex')
const databaseHashBefore = hashDatabase()

const requestFixture = Object.freeze({
  requestNo: 'PR-PROCESS-006-V1142889',
  requestDate: '2026-08-04',
  requester: 'PROCESS-006验收用户',
  department: '需求部门',
  purchaseDepartment: '采购部门',
  items: Object.freeze([Object.freeze({
    lineNo: 1,
    materialCode: 'MAT-PROCESS-006',
    materialName: '流程验收物料',
    quantity: 1,
    requiredDate: '2026-08-20',
  })]),
})

const walkthrough = await runPurchaseRequestEndToEndBusinessWalkthrough({
  async createPurchaseRequest() {
    return { ...requestFixture }
  },
  async savePurchaseRequest(request) {
    return { ...request, objectId: 'PR-PROCESS-006-OBJECT', statusCode: 'draft', approvalStatus: 'not_submitted' }
  },
  async submitPurchaseRequest(request) {
    return { ...request, statusCode: 'submitted', approvalStatus: 'pending' }
  },
  async approvePurchaseRequest(request) {
    return {
      ...request,
      statusCode: 'approved',
      approvalStatus: 'completed',
      inquiryEligibility: { eligible: true, items: request.items },
    }
  },
  async generateInquiryPreparation(request) {
    const result = createInquiryPreparation(request)
    if (result.result !== 'PASS') throw new Error('INQUIRY_PREPARATION_CREATION_FAILED')
    return result.object
  },
  async enterPurchaseInquiry(preparation) {
    return { route: '/scm/purchase-inquiry', inquiryPreparationNo: preparation.inquiryPreparationNo }
  },
})

const acceptance = validatePurchaseRequestProcessAcceptance(walkthrough)
const requestPage = read('src/meta/pages/ScmPurchaseRequestPage.vue')
const businessRegion = read('src/meta/components/ScmPurchaseRequestOriginalBusinessRegion.vue')
const requestApi = read('src/api/purchaseRequest.js')
const pageBound = requestPage.includes('ScmPurchaseRequestOriginalBusinessRegion')
  && requestPage.includes('data-process-node="scm-purchase-request"')
  && requestPage.includes(':data-process-action="purchaseRequestActionCodes.submit"')
  && requestPage.includes(':data-process-action="purchaseRequestActionCodes.approve"')
  && requestPage.includes(':data-process-action="purchaseRequestActionCodes.convert"')
  && requestPage.includes("runAction('submit'")
  && requestPage.includes("runAction('approve'")
  && requestPage.includes("runAction('convert'")
  && businessRegion.includes('saveCurrent')
  && businessRegion.includes('resolvePurchaseRequestActionContract')
  && businessRegion.includes('data-process-handoff="PURCHASE_REQUEST_TO_INQUIRY_PREPARATION"')
  && businessRegion.includes('createInquiryPreparation')
  && requestApi.includes('/submit/')
  && requestApi.includes('/approve/')

const backendRoot = path.join(workspaceRoot, 'backend')
const pythonCandidates = [
  process.env.PCE_PYTHON_EXECUTABLE,
  path.join(backendRoot, 'venv', 'Scripts', 'python.exe'),
  process.env.USERPROFILE && path.join(process.env.USERPROFILE, '.cache', 'codex-runtimes', 'codex-primary-runtime', 'dependencies', 'python', 'python.exe'),
].filter(candidate => candidate && fs.existsSync(candidate))
const backendArguments = [
  'manage.py',
  'test',
  'procurement.tests_v417.PurchaseRequestOrganizationRelationshipV417Tests.test_v11428782_target_request_completes_submit_and_approve_closure',
  '--settings=pce_backend.test_settings',
  '--verbosity',
  '1',
]
let backendTest = { status: 1, stdout: '', stderr: 'No usable Python runtime found' }
for (const python of pythonCandidates) {
  backendTest = spawnSync(python, backendArguments, {
    cwd: backendRoot,
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'pipe'],
    env: {
      ...process.env,
      PYTHONPATH: path.join(backendRoot, 'venv', 'Lib', 'site-packages'),
    },
  })
  if (backendTest.status === 0) break
}

const vite = path.join(frontendRoot, 'node_modules', 'vite', 'bin', 'vite.js')
const build = spawnSync(process.execPath, [vite, 'build', '.'], {
  cwd: frontendRoot,
  encoding: 'utf8',
  stdio: ['ignore', 'pipe', 'pipe'],
})
const databaseUnchanged = databaseHashBefore === hashDatabase()
const handoff = validatePurchaseRequestInquiryHandoff({
  modelCode: 'SCM_INQUIRY_PREPARATION_OBJECT',
  inquiryPreparationNo: walkthrough.inquiryPreparationNo,
  sourceRequestNo: walkthrough.requestNo,
  status: 'prepared',
  inquiryLines: requestFixture.items,
})

const results = Object.freeze([
  ['Page', pageBound && acceptance.report.sections.page.result === 'PASS'],
  ['Runtime', backendTest.status === 0 && acceptance.report.sections.runtime.result === 'PASS'],
  ['Action', acceptance.report.sections.action.result === 'PASS'],
  ['State', acceptance.report.sections.state.result === 'PASS' && acceptance.stateSeparation.result === 'PASS'],
  ['Handoff', acceptance.report.sections.handoff.result === 'PASS' && handoff.result === 'PASS'],
  ['Regression', acceptance.report.sections.regression.result === 'PASS' && databaseUnchanged],
  ['PROCESS-006', acceptance.report.sections.process006.result === 'PASS' && acceptance.walkthroughPathValid],
])

if (backendTest.status !== 0) {
  process.stderr.write(backendTest.stdout || '')
  process.stderr.write(backendTest.stderr || '')
}
if (build.status !== 0) {
  process.stderr.write(build.stdout || '')
  process.stderr.write(build.stderr || '')
}

for (const [label, passed] of results) console.log(`${label} ${passed ? 'PASS' : 'FAIL'}`)
console.log(`Build ${build.status === 0 ? 'PASS' : 'FAIL'}`)

const passed = results.every(([, result]) => result) && build.status === 0
console.log(passed ? 'SCM_PURCHASE_REQUEST_RUNTIME_READY' : 'SCM_PURCHASE_REQUEST_RUNTIME_FAILED')
if (!passed) process.exitCode = 1
