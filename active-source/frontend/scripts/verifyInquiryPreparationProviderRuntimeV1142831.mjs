import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

import { createInquiryPreparation, readInquiryPreparationContextSnapshot } from '../src/meta/runtime/inquiryPreparationRuntime.js'
import { buildInquiryPreparationProviderDiagnostic } from '../src/meta/runtime/inquiryPreparationProviderDiagnostic.js'
import { inquiryPreparationProvider } from '../src/meta/providers/inquiryPreparationProvider.js'
import { executeScmPurchaseGoldenPathV1 } from '../src/meta/acceptance/scmPurchaseGoldenPathV1.js'
import { validateScmPurchaseProcessGovernance } from '../src/meta/acceptance/scmPurchaseProcessGovernanceV11428181.js'
import { validatePurchaseRequestInquiryPreparationHandoff } from '../src/meta/process/scm/purchaseRequest/purchaseRequestInquiryPreparationHandoffContract.js'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const request = Object.freeze({ objectType: 'PurchaseRequest', objectId: 'PR_TEST_PROVIDER_001',
  requestNo: 'PR_TEST_PROVIDER_001', requestDate: '2026-08-04', requester: 'provider-acceptance-user',
  department: 'Provider验收需求部门', purchaseDepartment: 'Provider验收采购部',
  statusCode: 'approved', approvalStatus: 'approved', businessLifecycleState: 'approved',
  inquiryEligibility: Object.freeze({ eligible: true }), items: Object.freeze([Object.freeze({
    materialCode: 'MAT_PROVIDER_001', materialName: 'Provider验收物料', specification: 'SPEC-PROVIDER-001',
    unit: 'EA', quantity: 1, requiredDate: '2026-09-01', suggestedSupplierId: 'SUP_PROVIDER_001',
    suggestedSupplierName: 'Provider验收供应商' })]) })
const creation = createInquiryPreparation(request)
const contextSnapshot = readInquiryPreparationContextSnapshot()
const firstLoad = inquiryPreparationProvider.load({ sourceRequestNo: request.requestNo })
const refreshLoad = inquiryPreparationProvider.load({ sourceRequestNo: request.requestNo })
const pageRows = firstLoad.objects
const diagnostic = buildInquiryPreparationProviderDiagnostic({ contextSnapshot, providerFacts: firstLoad, pageRows })
const pageSource = fs.readFileSync(path.join(frontendRoot, 'src/meta/pages/ScmPurchaseInquiryWorkbenchPage.vue'), 'utf8')
const providerSource = fs.readFileSync(path.join(frontendRoot, 'src/meta/providers/inquiryPreparationProvider.js'), 'utf8')
const providerPure = providerSource.includes('readInquiryPreparationContextSnapshot')
  && !providerSource.includes('purchaseInquiryRuntime') && !providerSource.includes('route.query')
const pageRead = pageSource.includes('const pendingInquiryPreparations = computed(() => inquiryPreparationFacts.value.objects)')
  && pageSource.includes('data-provider-code="SCM_INQUIRY_PREPARATION_PROVIDER"')
const sourceTrace = firstLoad.selected?.sourceTrace?.sourceRequestNo === 'PR_TEST_PROVIDER_001'
const handoff = validatePurchaseRequestInquiryPreparationHandoff(request, creation.object)

console.log('INQUIRY_PREPARATION_PROVIDER_TRACE_REPORT')
console.log(`Creation: ${diagnostic.trace.creationLocation}`)
console.log(`Storage: ${diagnostic.trace.storageLocation}`)
console.log(`Provider: ${diagnostic.trace.providerReadLocation}`)
console.log(`Page: ${diagnostic.trace.pageConsumeLocation}`)

const golden = executeScmPurchaseGoldenPathV1()
const governance = validateScmPurchaseProcessGovernance()
const regression = creation.object?.formalInquiryCreated === false
  && creation.object?.quotationTaskCreated === false && creation.object?.supplierSent === false
  && creation.object?.quotationCreated === false && creation.object?.purchaseOrderCreated === false
  && creation.object?.productionDataWritten === false
const checks = [
  ['Context', creation.result === 'PASS' && contextSnapshot.recordCount > 0
    && contextSnapshot.objects.every(item => item.objectType === 'InquiryPreparationContext')],
  ['Provider', providerPure && firstLoad.recordCount === contextSnapshot.recordCount],
  ['Page Read', pageRead && diagnostic.pageConsumedCount === diagnostic.providerRecordCount],
  ['First Load', firstLoad.selected?.sourceRequestNo === 'PR_TEST_PROVIDER_001'],
  ['Refresh', firstLoad.recordCount === refreshLoad.recordCount && firstLoad.snapshotId === refreshLoad.snapshotId],
  ['Source Trace', sourceTrace],
  ['PROCESS-006-B', handoff.result === 'PASS' && governance.process006B.result === 'PASS'],
  ['PROCESS-008', golden.process008.result === 'PASS'],
  ['Regression', regression && diagnostic.result === 'PASS'],
]

const vite = path.join(frontendRoot, 'node_modules/vite/bin/vite.js')
const build = spawnSync(process.execPath, [vite, 'build', '.'], {
  cwd: frontendRoot, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'],
})
if (build.status !== 0) { process.stderr.write(build.stdout || ''); process.stderr.write(build.stderr || '') }
for (const [label, passed] of checks) console.log(`${label} ${passed ? 'PASS' : 'FAIL'}`)
console.log(`Build ${build.status === 0 ? 'PASS' : 'FAIL'}`)
const passed = checks.every(([, value]) => value) && build.status === 0
console.log(passed ? 'SCM_INQUIRY_PREPARATION_PROVIDER_RUNTIME_READY'
  : 'SCM_INQUIRY_PREPARATION_PROVIDER_RUNTIME_FAILED')
if (!passed) process.exitCode = 1

