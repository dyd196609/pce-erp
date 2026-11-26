import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

import {
  createSupplierQuoteContext,
  markSupplierQuoteWaiting,
  receiveSupplierQuote,
  saveSupplierQuote,
} from '../src/meta/runtime/supplierQuoteRuntime.js'
import {
  runSupplierQuoteEndToEndBusinessWalkthrough,
  validateSupplierQuoteProcessAcceptance,
} from '../src/meta/process/scm/supplierQuote/supplierQuoteProcessAcceptanceProfile.js'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const workspaceRoot = path.resolve(frontendRoot, '..')
const databasePath = path.join(workspaceRoot, 'backend', 'db.sqlite3')
const hashDatabase = () => crypto.createHash('sha256').update(fs.readFileSync(databasePath)).digest('hex')
const databaseHashBefore = hashDatabase()
const artifacts = {}

const walkthrough = await runSupplierQuoteEndToEndBusinessWalkthrough({
  async loadPurchaseRequest() {
    artifacts.request = { requestNo: 'PR-SQ-PROCESS-006-V1142811' }
    return artifacts.request
  },
  async loadPurchaseInquiry(request) {
    artifacts.inquiry = {
      inquiryNo: 'PI-SQ-PROCESS-006-V1142811',
      sourceRequestNo: request.requestNo,
      statusCode: 'draft',
      responseDeadline: '2026-08-31',
      lines: [{ lineNo: 1, materialCode: 'MAT-SQ-006', materialName: '供应商报价闭环物料', quantity: 8, unit: '件' }],
      suppliers: [{ supplierId: 'SUP-SQ-006', supplierName: '报价候选供应商' }],
    }
    return artifacts.inquiry
  },
  async createSupplierQuoteContext(inquiry) {
    artifacts.context = createSupplierQuoteContext(inquiry)
    return artifacts.context
  },
  async receiveSupplierQuote(context) {
    artifacts.waitingContext = markSupplierQuoteWaiting(context)
    artifacts.quote = receiveSupplierQuote(artifacts.waitingContext, {
      supplierId: 'SUP-SQ-006',
      quoteDate: '2026-08-04',
      currency: 'CNY',
      validUntil: '2026-08-31',
      lines: context.materials.map(item => ({ ...item, unitPrice: 88, taxRate: 13, deliveryDate: '2026-08-25' })),
    })
    return artifacts.quote
  },
  async saveSupplierQuote(quote) {
    const result = saveSupplierQuote(quote)
    artifacts.quote = result.object
    return result
  },
})

const acceptance = validateSupplierQuoteProcessAcceptance(walkthrough, artifacts)
const page = fs.readFileSync(path.join(frontendRoot, 'src', 'meta', 'pages', 'ScmPurchaseInquiryWorkbenchPage.vue'), 'utf8')
const runtimeSource = fs.readFileSync(path.join(frontendRoot, 'src', 'meta', 'runtime', 'supplierQuoteRuntime.js'), 'utf8')
const pageBound = page.includes('data-process-node="SCM_SUPPLIER_QUOTE"')
  && page.includes('supplierQuoteActionCodes.createContext')
  && page.includes('supplierQuoteActionCodes.receiveQuote')
  && page.includes('supplierQuoteActionCodes.saveQuote')
const noSupplierApi = !runtimeSource.includes("@/api/") && !runtimeSource.includes("../api/")
  && !runtimeSource.includes('fetch(') && artifacts.quote.supplierApiCalled === false
const databaseUnchanged = databaseHashBefore === hashDatabase()

const vite = path.join(frontendRoot, 'node_modules', 'vite', 'bin', 'vite.js')
const build = spawnSync(process.execPath, [vite, 'build', '.'], {
  cwd: frontendRoot,
  encoding: 'utf8',
  stdio: ['ignore', 'pipe', 'pipe'],
})
if (build.status !== 0) {
  process.stderr.write(build.stdout || '')
  process.stderr.write(build.stderr || '')
}

const results = Object.freeze([
  ['Node Contract', pageBound && acceptance.report.contracts.node.result === 'PASS'],
  ['Action Contract', acceptance.report.sections.action.result === 'PASS'],
  ['State Contract', acceptance.report.sections.state.result === 'PASS' && acceptance.stateBoundaries.result === 'PASS'],
  ['Handoff', acceptance.report.sections.handoff.result === 'PASS' && acceptance.handoff.result === 'PASS'],
  ['Context', acceptance.report.contracts.context.result === 'PASS'],
  ['PROCESS-006', acceptance.report.sections.process006.result === 'PASS' && acceptance.walkthroughPathValid],
  ['Regression', acceptance.report.sections.regression.result === 'PASS' && acceptance.boundariesProtected && noSupplierApi && databaseUnchanged],
])

for (const [label, passed] of results) console.log(`${label} ${passed ? 'PASS' : 'FAIL'}`)
console.log(`Build ${build.status === 0 ? 'PASS' : 'FAIL'}`)
const passed = results.every(([, result]) => result) && build.status === 0
console.log(passed ? 'SCM_SUPPLIER_QUOTE_RUNTIME_READY' : 'SCM_SUPPLIER_QUOTE_RUNTIME_FAILED')
if (!passed) process.exitCode = 1

