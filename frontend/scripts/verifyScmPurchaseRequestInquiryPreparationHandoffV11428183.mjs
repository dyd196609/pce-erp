import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

import { createScmPurchaseRequestHandoffAcceptanceData, executeScmPurchaseGoldenPathV1 } from '../src/meta/acceptance/scmPurchaseGoldenPathV1.js'
import { validateScmPurchaseProcessGovernance } from '../src/meta/acceptance/scmPurchaseProcessGovernanceV11428181.js'
import { validateInquiryPreparationContext } from '../src/meta/process/scm/inquiryPreparation/inquiryPreparationContextContract.js'
import { validateInquiryPreparationStateContract } from '../src/meta/process/scm/inquiryPreparation/inquiryPreparationStateContract.js'
import { validatePurchaseRequestInquiryPreparationHandoff } from '../src/meta/process/scm/purchaseRequest/purchaseRequestInquiryPreparationHandoffContract.js'
import { findPurchaseInquiryByPreparation } from '../src/meta/runtime/purchaseInquiryRuntime.js'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const acceptanceData = createScmPurchaseRequestHandoffAcceptanceData()
const golden = executeScmPurchaseGoldenPathV1()
const governance = validateScmPurchaseProcessGovernance()
const context = acceptanceData.inquiryPreparation
const handoff = validatePurchaseRequestInquiryPreparationHandoff(acceptanceData.approved, context)
const pageSource = fs.readFileSync(path.join(frontendRoot, 'src/meta/pages/ScmPurchaseInquiryWorkbenchPage.vue'), 'utf8')
const runtimeSource = fs.readFileSync(path.join(frontendRoot, 'src/meta/runtime/inquiryPreparationRuntime.js'), 'utf8')
const forbiddenSources = ['supplierQuoteRuntime.js', 'quoteComparisonRuntime.js', 'supplierRecommendationRuntime.js',
  'purchaseOrderTransactionRuntime.js', 'purchaseOrderIssuePreparationRuntime.js', 'purchaseOrderIssueBoundaryRuntime.js']
const scan = runtimeSource.includes('createInquiryPreparationContext')
  && runtimeSource.includes('transitionInquiryPreparationState')
  && forbiddenSources.every(source => !runtimeSource.includes(source))
const fieldCompleteness = validateInquiryPreparationContext(context).valid && handoff.valid
const stateTransition = validateInquiryPreparationStateContract().valid
  && context.stateHistory.join('>') === 'created>prepared>ready_for_inquiry'
const pageRead = pageSource.includes('data-provider-code="SCM_INQUIRY_PREPARATION_PROVIDER"')
  && acceptanceData.providerFacts.recordCount > 0
  && acceptanceData.providerFacts.selected?.inquiryPreparationNo === context.inquiryPreparationNo
const boundaries = findPurchaseInquiryByPreparation(context.inquiryPreparationNo) === null
  && Object.values(acceptanceData.boundaries).every(value => value === false)

console.log(`SCM_PR_INQUIRY_PREPARATION_HANDOFF_SCAN ${scan ? 'PASS' : 'FAIL'}`)
const checks = [
  ['PurchaseRequest → InquiryPreparation', acceptanceData.result === 'PASS' && handoff.result === 'PASS'],
  ['Field Completeness', fieldCompleteness],
  ['State Transition', stateTransition],
  ['Page Read', pageRead],
  ['PROCESS-006', governance.process006A.result === 'PASS' && governance.process006B.result === 'PASS'
    && governance.process006C.result === 'PASS' && governance.process006D.result === 'PASS'],
  ['PROCESS-008', golden.process008.result === 'PASS'],
  ['Regression', boundaries && governance.handoff.result === 'PASS'],
]
const vite = path.join(frontendRoot, 'node_modules/vite/bin/vite.js')
const build = spawnSync(process.execPath, [vite, 'build', '.'], {
  cwd: frontendRoot, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'],
})
if (build.status !== 0) { process.stderr.write(build.stdout || ''); process.stderr.write(build.stderr || '') }
for (const [label, passed] of checks) console.log(`${label} ${passed ? 'PASS' : 'FAIL'}`)
console.log(`Build ${build.status === 0 ? 'PASS' : 'FAIL'}`)
const passed = scan && checks.every(([, value]) => value) && build.status === 0
console.log(passed ? 'SCM_PURCHASE_REQUEST_INQUIRY_PREPARATION_HANDOFF_READY'
  : 'SCM_PURCHASE_REQUEST_INQUIRY_PREPARATION_HANDOFF_FAILED')
if (!passed) process.exitCode = 1

