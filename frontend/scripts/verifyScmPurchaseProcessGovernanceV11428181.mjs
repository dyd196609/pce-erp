import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

import { validateScmPurchaseProcessGovernance } from '../src/meta/acceptance/scmPurchaseProcessGovernanceV11428181.js'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const result = validateScmPurchaseProcessGovernance()
const requestPage = fs.readFileSync(path.join(frontendRoot, 'src/meta/pages/ScmPurchaseRequestPage.vue'), 'utf8')
const inquiryPage = fs.readFileSync(path.join(frontendRoot, 'src/meta/pages/ScmPurchaseInquiryWorkbenchPage.vue'), 'utf8')
const pageSourcesGoverned = requestPage.includes('purchaseRequestLifecycleProvider.load(runtimeResult.facts)')
  && requestPage.includes('row.approvalStatus') && requestPage.includes('row.businessLifecycleStatus')
  && inquiryPage.includes('purchaseInquiryLifecycleProvider.loadForEntry')
  && inquiryPage.includes('PURCHASE_INQUIRY_ENTRY_CODES')
const actionButtonsGoverned = ['SUBMIT_APPROVAL', 'APPROVE', 'CREATE_INQUIRY_PREPARATION']
  .every(code => requestPage.includes('purchaseRequestActionCodes'))
  && ['START_PURCHASE_INQUIRY', 'EDIT_PURCHASE_INQUIRY', 'SAVE_PURCHASE_INQUIRY']
    .every(code => fs.readFileSync(path.join(frontendRoot, 'src/meta/process/scm/purchaseInquiry/purchaseInquiryActionContracts.js'), 'utf8').includes(code))
const regression = result.walkthrough.authorization.supplierApiCalled === false
  && result.walkthrough.authorization.purchaseOrderIssued === false
  && result.walkthrough.authorization.supplierSent === false
  && result.walkthrough.authorization.goodsReceived === false
  && result.walkthrough.authorization.inventoryPosted === false
  && result.walkthrough.authorization.invoiceCreated === false
  && result.walkthrough.authorization.paymentCreated === false
  && result.walkthrough.authorization.productionDataWritten === false

const checks = [
  ['Page Runtime', result.pageRuntime.result === 'PASS' && pageSourcesGoverned],
  ['Action Contract', result.actionContract.result === 'PASS' && actionButtonsGoverned],
  ['State Contract', result.stateContract.result === 'PASS'],
  ['Handoff', result.handoff.result === 'PASS' && result.handoff.auditCount === 10],
  ['Provider', result.provider.result === 'PASS'],
  ['Multi Entry', result.multiEntry.result === 'PASS'],
  ['PROCESS-006-A', result.process006A.result === 'PASS'],
  ['PROCESS-006-B', result.process006B.result === 'PASS'],
  ['PROCESS-006-C', result.process006C.result === 'PASS'],
  ['PROCESS-006-D', result.process006D.result === 'PASS'],
  ['Regression', regression],
]

const vite = path.join(frontendRoot, 'node_modules/vite/bin/vite.js')
const build = spawnSync(process.execPath, [vite, 'build', '.'], {
  cwd: frontendRoot, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'],
})
if (build.status !== 0) {
  process.stderr.write(build.stdout || '')
  process.stderr.write(build.stderr || '')
}

for (const [label, passed] of checks) console.log(`${label} ${passed ? 'PASS' : 'FAIL'}`)
console.log(`Build ${build.status === 0 ? 'PASS' : 'FAIL'}`)
const passed = checks.every(([, value]) => value) && build.status === 0
console.log(passed ? 'SCM_PURCHASE_PROCESS_GOVERNANCE_READY' : 'SCM_PURCHASE_PROCESS_GOVERNANCE_FAILED')
if (!passed) process.exitCode = 1

