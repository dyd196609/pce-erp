import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

import { createInquiryPreparation } from '../src/meta/runtime/inquiryPreparationRuntime.js'
import {
  activatePurchaseInquiryFromPreparation,
  beginPurchaseInquiryDraftEdit,
  savePurchaseInquiryDraft,
} from '../src/meta/runtime/purchaseInquiryRuntime.js'
import {
  runPurchaseInquiryEndToEndBusinessWalkthrough,
  validatePurchaseInquiryProcessAcceptance,
} from '../src/meta/process/scm/purchaseInquiry/purchaseInquiryProcessAcceptanceProfile.js'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const workspaceRoot = path.resolve(frontendRoot, '..')
const databasePath = path.join(workspaceRoot, 'backend', 'db.sqlite3')
const hashDatabase = () => crypto.createHash('sha256').update(fs.readFileSync(databasePath)).digest('hex')
const databaseHashBefore = hashDatabase()
const artifacts = {}

const walkthrough = await runPurchaseInquiryEndToEndBusinessWalkthrough({
  async loadPurchaseRequest() {
    artifacts.request = {
      requestNo: 'PR-PI-PROCESS-006-V1142810',
      requestDate: '2026-08-04',
      requester: 'PROCESS-006询价验收用户',
      department: '需求部门',
      purchaseDepartment: '采购部门',
      statusCode: 'approved',
      approvalStatus: 'completed',
      inquiryEligibility: { eligible: true, items: [{ materialCode: 'MAT-PI-006', materialName: '询价闭环物料', quantity: 1, requiredDate: '2026-08-20' }] },
      items: [{ materialCode: 'MAT-PI-006', materialName: '询价闭环物料', quantity: 1, requiredDate: '2026-08-20' }],
    }
    return artifacts.request
  },
  async createInquiryPreparation(request) {
    const result = createInquiryPreparation(request)
    if (result.result !== 'PASS') throw new Error('INQUIRY_PREPARATION_FAILED')
    artifacts.preparation = result.object
    return artifacts.preparation
  },
  async enterPurchaseInquiryPage(preparation) {
    return { route: '/scm/purchase-inquiry', inquiryPreparationNo: preparation.inquiryPreparationNo }
  },
  async startPurchaseInquiry(preparation) {
    const result = activatePurchaseInquiryFromPreparation(preparation)
    if (result.result !== 'PASS') throw new Error('PURCHASE_INQUIRY_ACTIVATION_FAILED')
    artifacts.inquiry = result.object
    return artifacts.inquiry
  },
  async editPurchaseInquiry(inquiry) {
    return { ...beginPurchaseInquiryDraftEdit(inquiry), inquiryTitle: `${inquiry.inquiryTitle}（PROCESS-006）` }
  },
  async savePurchaseInquiry(editDraft) {
    const result = savePurchaseInquiryDraft(editDraft)
    artifacts.inquiry = result.object
    return result
  },
  async confirmFormalPurchaseInquiry(inquiry) {
    return inquiry
  },
})

const acceptance = validatePurchaseInquiryProcessAcceptance(walkthrough, artifacts)
const page = fs.readFileSync(path.join(frontendRoot, 'src', 'meta', 'pages', 'ScmPurchaseInquiryWorkbenchPage.vue'), 'utf8')
const pageBound = page.includes('data-process-node="SCM_PURCHASE_INQUIRY"')
  && page.includes('purchaseInquiryActionCodes.startInquiry')
  && page.includes('purchaseInquiryActionCodes.editInquiry')
  && page.includes('purchaseInquiryActionCodes.saveInquiry')
  && page.includes('savePurchaseInquiryDraft')
const forbiddenActionsAbsent = !page.includes('>发送供应商<')
  && !page.includes('>创建供应商报价<')
  && !page.includes('>生成采购订单<')
  && !page.includes('>创建付款<')
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
  ['State Contract', acceptance.report.sections.state.result === 'PASS' && acceptance.stateBoundary.result === 'PASS'],
  ['Handoff', acceptance.report.sections.handoff.result === 'PASS' && acceptance.handoff.result === 'PASS'],
  ['Context', acceptance.report.contracts.context.result === 'PASS'],
  ['PROCESS-006', acceptance.report.sections.process006.result === 'PASS' && acceptance.walkthroughPathValid],
  ['Regression', acceptance.report.sections.regression.result === 'PASS' && forbiddenActionsAbsent && databaseUnchanged],
])

for (const [label, passed] of results) console.log(`${label} ${passed ? 'PASS' : 'FAIL'}`)
console.log(`Build ${build.status === 0 ? 'PASS' : 'FAIL'}`)
const passed = results.every(([, result]) => result) && build.status === 0
console.log(passed ? 'SCM_PURCHASE_INQUIRY_RUNTIME_READY' : 'SCM_PURCHASE_INQUIRY_RUNTIME_FAILED')
if (!passed) process.exitCode = 1

