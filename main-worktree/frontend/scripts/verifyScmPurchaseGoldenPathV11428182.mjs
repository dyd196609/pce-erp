import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

import { executeScmPurchaseGoldenPathV1 } from '../src/meta/acceptance/scmPurchaseGoldenPathV1.js'
import { validateScmPurchaseProcessGovernance } from '../src/meta/acceptance/scmPurchaseProcessGovernanceV11428181.js'
import { validatePurchaseRequestStateContract } from '../src/meta/process/scm/purchaseRequest/state/purchaseRequestStateContract.js'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const golden = executeScmPurchaseGoldenPathV1()
const governance = validateScmPurchaseProcessGovernance()
const page = fs.readFileSync(path.join(frontendRoot, 'src/meta/pages/ScmPurchaseRequestPage.vue'), 'utf8')
const component = fs.readFileSync(path.join(frontendRoot, 'src/meta/components/ScmPurchaseRequestOriginalBusinessRegion.vue'), 'utf8')
const ruleSource = fs.readFileSync(path.join(frontendRoot, 'src/meta/domain/scm/inquiryPreparation/inquiryPreparationRuleEngine.js'), 'utf8')
const guardSource = fs.readFileSync(path.join(frontendRoot, 'src/meta/domain/scm/inquiryPreparation/inquiryPreparationCreationGuard.js'), 'utf8')
const pageValid = page.includes('row.approvalStatus') && page.includes('row.businessLifecycleStatus')
  && component.includes('readPurchaseRequestState') && page.includes("runBatchAction('convert')")
const actionValid = page.includes('purchaseRequestActionCodes.convert')
  && component.includes('resolvePurchaseRequestActionContract')
const guardValid = guardSource.includes('evaluatePurchaseRequestActionGuard')
  && ruleSource.includes("evaluatePurchaseRequestActionGuard(request, 'CREATE_INQUIRY_PREPARATION')")
  && !ruleSource.includes('approvalCompleted')
const providerValid = golden.providerConsistent && golden.firstLoad.factSnapshotId === golden.refreshLoad.factSnapshotId
const regression = golden.chain.handoffs.valid
  && golden.chain.authorization.supplierApiCalled === false
  && golden.chain.authorization.purchaseOrderIssued === false
  && golden.chain.authorization.goodsReceived === false
  && golden.chain.authorization.inventoryPosted === false
  && golden.chain.authorization.invoiceCreated === false
  && golden.chain.authorization.paymentCreated === false
  && golden.chain.authorization.productionDataWritten === false

const checks = [
  ['Page Runtime', pageValid],
  ['Action Contract', actionValid && governance.actionContract.result === 'PASS'],
  ['State Contract', validatePurchaseRequestStateContract().result === 'PASS'],
  ['Guard', guardValid],
  ['Handoff', golden.handoff.result === 'PASS' && governance.handoff.result === 'PASS'],
  ['Provider', providerValid && governance.provider.result === 'PASS'],
  ['PROCESS-006-A', governance.process006A.result === 'PASS'],
  ['PROCESS-006-B', governance.process006B.result === 'PASS'],
  ['PROCESS-006-C', governance.process006C.result === 'PASS'],
  ['PROCESS-006-D', governance.process006D.result === 'PASS'],
  ['PROCESS-008', golden.process008.result === 'PASS'],
  ['Regression', regression],
]

const vite = path.join(frontendRoot, 'node_modules/vite/bin/vite.js')
const build = spawnSync(process.execPath, [vite, 'build', '.'], {
  cwd: frontendRoot, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'],
})
if (build.status !== 0) { process.stderr.write(build.stdout || ''); process.stderr.write(build.stderr || '') }
for (const [label, passed] of checks) console.log(`${label} ${passed ? 'PASS' : 'FAIL'}`)
console.log(`Build ${build.status === 0 ? 'PASS' : 'FAIL'}`)
const passed = checks.every(([, value]) => value) && build.status === 0
console.log(passed ? 'SCM_PURCHASE_PROCESS_REGRESSION_BASELINE_READY' : 'SCM_PURCHASE_PROCESS_REGRESSION_BASELINE_FAILED')
if (!passed) process.exitCode = 1

