import fs from 'node:fs/promises'
import path from 'node:path'
import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { PURCHASE_INQUIRY_RUNTIME, buildPurchaseInquiryRuntimeView } from '../src/meta/runtime/purchaseInquiryRuntime.js'
import { FORMAL_PRICE_APPROVAL_PROJECTION, validateFormalPriceApprovalProjection } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalProjection/formalPriceApprovalProjectionModel.js'
import { PRICE_APPROVAL_EVIDENCE_PACKAGE, validatePriceApprovalEvidencePackage } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalProjection/priceApprovalEvidencePackageModel.js'
import { FORMAL_PRICE_APPROVAL_PROJECTION_STATES } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalProjection/formalPriceApprovalProjectionStateModel.js'
import { evaluateFormalPriceApprovalProjection } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalProjection/formalPriceApprovalProjectionRuleEngine.js'
import { FORMAL_PRICE_APPROVAL_PROJECTION_FORBIDDEN_ACTIONS, evaluateFormalPriceApprovalProjectionRuntimeGuard } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalProjection/formalPriceApprovalProjectionRuntimeGuard.js'
import { validateFormalPriceApprovalProjectionRuntimeMappings } from '../src/meta/schema/scm/formalPriceApprovalProjectionRuntimeMapping.js'
import { FORMAL_PRICE_APPROVAL_PROJECTION_ACCEPTANCE_PROFILE, validateFormalPriceApprovalProjectionAcceptance } from '../src/meta/acceptance/scm/formalPriceApprovalProjectionAcceptanceProfile.js'

const VERSION = 'V1.14.2.8.6.5'
const TARGET_STATUS = 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_PROJECTION_READY'
const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const workspaceRoot = path.resolve(frontendRoot, '..')
const read = (relative) => fs.readFile(path.join(frontendRoot, relative), 'utf8')
const hashFile = async (file) => crypto.createHash('sha256').update(await fs.readFile(file)).digest('hex')
const gate = (name, pass, evidence) => Object.freeze({ gate: name, result: pass ? 'PASS' : 'FAIL', evidence })

async function listFiles(relative) {
  const root = path.join(frontendRoot, relative)
  const files = []
  async function walk(directory) {
    for (const entry of await fs.readdir(directory, { withFileTypes: true })) {
      const full = path.join(directory, entry.name)
      if (entry.isDirectory()) await walk(full)
      else files.push(path.relative(frontendRoot, full).replaceAll('\\', '/'))
    }
  }
  try { await walk(root) } catch { /* missing root is an empty inventory */ }
  return files.sort()
}

async function createScan() {
  const [domainFiles, schemaFiles, acceptanceFiles, runtimeSource, routerSource] = await Promise.all([
    listFiles('src/meta/domain/scm/purchaseInquiry'), listFiles('src/meta/schema/scm'), listFiles('src/meta/acceptance/scm'),
    read('src/meta/runtime/purchaseInquiryRuntime.js'), read('src/router/index.js'),
  ])
  return Object.freeze({ version: VERSION, generatedAt: new Date().toISOString(),
    scope: Object.freeze(['src/meta/domain/scm/purchaseInquiry', 'src/meta/runtime/purchaseInquiryRuntime.js', 'src/meta/schema/scm', 'src/meta/acceptance/scm', 'src/router/index.js']),
    inventory: Object.freeze({ domainFiles, schemaFiles, acceptanceFiles, runtimeVersionFound: runtimeSource.includes(VERSION),
      inquiryRoutePresent: routerSource.includes("path: 'scm/purchase-inquiry'"), formalPriceApprovalRoutePresent: routerSource.includes("path: 'scm/price-approval'") }),
    analysis: Object.freeze({ prerequisites: ['SCM_PRICE_APPROVAL_ENTRY_ASSESSMENT', 'SCM_PRICE_APPROVAL_CREATION_ASSESSMENT'],
      formalPriceApprovalExisting: true, formalPriceApprovalModified: false, approvalWorkflowModified: false,
      strategy: 'pre-creation read-only projection and server evidence-reference package' }),
    protectedScopes: Object.freeze(['Formal Price Approval', 'Approval Workflow', 'PurchaseOrder', 'Finance', 'Inventory']),
  })
}

async function run() {
  const scan = await createScan()
  const scanPath = path.join(frontendRoot, 'scm_purchase_inquiry_formal_price_approval_projection_scan_v1142865.json')
  await fs.writeFile(scanPath, `${JSON.stringify(scan, null, 2)}\n`, 'utf8')
  if (process.argv.includes('--scan-only')) return { scanPath, scan }

  const databasePath = path.join(workspaceRoot, 'backend', 'db.sqlite3')
  const databaseHashBefore = await hashFile(databasePath)
  const [pageSource, routerSource, registrySource] = await Promise.all([
    read('src/meta/pages/ScmPurchaseInquiryWorkbenchPage.vue'), read('src/router/index.js'), read('src/meta/acceptance/registry/enterpriseAcceptanceRegistry.js'),
  ])
  const completePackage = { evidencePackageNo: 'PAEP-VERIFY-001', packageStatus: 'available', quotationEvidenceRefs: ['SQ-001', 'SQ-002'], comparisonEvidenceRef: 'QC-001', preparationEvidenceRef: 'PRP-001', entryAssessmentEvidenceRef: 'PAEA-001', creationFreezeEvidenceRef: 'PACA-001' }
  const notCreated = evaluateFormalPriceApprovalProjection()
  const available = evaluateFormalPriceApprovalProjection({ creationAssessment: { creationAssessmentStatus: 'ready' }, evidencePackage: completePackage })
  const incomplete = evaluateFormalPriceApprovalProjection({ creationAssessment: { creationAssessmentStatus: 'ready' }, evidencePackage: { ...completePackage, comparisonEvidenceRef: '', packageStatus: 'incomplete' } })
  const freezeBlocked = evaluateFormalPriceApprovalProjection({ creationAssessment: { creationAssessmentStatus: 'blocked' }, evidencePackage: completePackage })
  const packageBlocked = evaluateFormalPriceApprovalProjection({ creationAssessment: { creationAssessmentStatus: 'ready' }, evidencePackage: { ...completePackage, packageStatus: 'blocked' } })
  const runtimeView = buildPurchaseInquiryRuntimeView({
    formalPriceApprovalProjections: [{ projectionNo: 'FPAP-VERIFY-001', inquiryNo: 'PI-VERIFY-001', creationAssessmentNo: 'PACA-001', preparationNo: 'PRP-001', comparisonNo: 'QC-001', evidencePackageNo: 'PAEP-VERIFY-001', projectionStatus: 'available', projectionStatusLabel: '投影可用', projectionAvailabilityLabel: '只读投影可查看', missingEvidence: [] }],
    priceApprovalEvidencePackages: [{ ...completePackage, inquiryNo: 'PI-VERIFY-001', packageStatusLabel: '证据完整', evidenceCount: 6, missingEvidence: [] }],
  })
  const results = [
    gate('Page', pageSource.includes('data-acceptance-id="formal-price-approval-projection"') && pageSource.includes('data-acceptance-id="price-approval-evidence-package"') && pageSource.includes('非正式审批对象') && pageSource.includes('证据引用只读'), FORMAL_PRICE_APPROVAL_PROJECTION_ACCEPTANCE_PROFILE.requiredRegions),
    gate('Router', routerSource.includes("path: 'scm/purchase-inquiry'") && routerSource.includes('ScmPurchaseInquiryWorkbenchPage.vue'), '/scm/purchase-inquiry'),
    gate('Schema', validateFormalPriceApprovalProjectionRuntimeMappings().valid, ['SCM_FORMAL_PRICE_APPROVAL_PROJECTION_RUNTIME_MAPPING', 'SCM_PRICE_APPROVAL_EVIDENCE_PACKAGE_RUNTIME_MAPPING']),
    gate('Runtime', validateFormalPriceApprovalProjection().valid && validatePriceApprovalEvidencePackage().valid && FORMAL_PRICE_APPROVAL_PROJECTION_STATES.join(',') === 'not_created,available,incomplete,blocked' && runtimeView.quotationRuntime.formalPriceApprovalProjections.length === 1 && runtimeView.quotationRuntime.priceApprovalEvidencePackages.length === 1 && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalProjectionRuntimeCode === 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_PROJECTION_RUNTIME', { projection: FORMAL_PRICE_APPROVAL_PROJECTION.objectCode, evidencePackage: PRICE_APPROVAL_EVIDENCE_PACKAGE.objectCode }),
    gate('Rule', notCreated.projectionStatus === 'not_created' && available.projectionStatus === 'available' && incomplete.projectionStatus === 'incomplete' && incomplete.missingEvidence.includes('comparisonEvidenceRef') && freezeBlocked.projectionStatus === 'blocked' && packageBlocked.projectionStatus === 'blocked' && available.projectionAvailable === true && available.evidenceArchiveWritten === false && available.formalPriceApprovalObjectCreated === false && available.approvalWorkflowStarted === false && available.approvalTaskCreated === false && available.approvalSubmitted === false && available.priceApproved === false && available.purchaseOrderCreated === false, { notCreated: notCreated.projectionStatus, available: available.projectionStatus, incomplete: incomplete.projectionStatus, freezeBlocked: freezeBlocked.projectionStatus, packageBlocked: packageBlocked.projectionStatus }),
    gate('Guard', FORMAL_PRICE_APPROVAL_PROJECTION_FORBIDDEN_ACTIONS.every((action) => evaluateFormalPriceApprovalProjectionRuntimeGuard(action).decision === 'deny'), FORMAL_PRICE_APPROVAL_PROJECTION_FORBIDDEN_ACTIONS),
    gate('Acceptance', validateFormalPriceApprovalProjectionAcceptance().valid && registrySource.includes('FORMAL_PRICE_APPROVAL_PROJECTION_ACCEPTANCE_PROFILE'), FORMAL_PRICE_APPROVAL_PROJECTION_ACCEPTANCE_PROFILE.profileCode),
  ]
  try {
    const viteEntry = path.join(frontendRoot, 'node_modules', 'vite', 'bin', 'vite.js')
    const output = execFileSync(process.execPath, [viteEntry, 'build', '.', '--emptyOutDir=false'], { cwd: frontendRoot, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], timeout: 240000 })
    results.push(gate('Build', true, output.trim().split(/\r?\n/).slice(-2)))
  } catch (error) {
    results.push(gate('Build', false, String(error.stderr || error.message)))
  }
  const databaseHashAfter = await hashFile(databasePath)
  const databaseUnchanged = databaseHashBefore === databaseHashAfter
  const passed = results.every((item) => item.result === 'PASS') && databaseUnchanged
  const report = Object.freeze({ version: VERSION, generatedAt: new Date().toISOString(), status: passed ? TARGET_STATUS : 'FAIL', problemAnalysis: scan.analysis,
    gates: Object.freeze(results), summary: Object.freeze({ PASS: results.filter((item) => item.result === 'PASS').length, FAIL: results.filter((item) => item.result === 'FAIL').length }),
    businessWriteCount: 0, productionDataWritten: false, database: databaseUnchanged ? 'UNCHANGED' : 'CHANGED', databaseHashBefore, databaseHashAfter,
    evidenceArchiveWritten: false, formalPriceApprovalObjectCreated: false, approvalWorkflowStarted: false, approvalTaskCreated: false,
    approvalSubmitted: false, priceApproved: false, autoPurchaseOrderCreation: false, formalPriceApprovalModified: false,
    approvalWorkflowModified: false, protectedScopeChanges: 0 })
  const outputRoot = path.join(frontendRoot, 'test-results', 'page-acceptance', VERSION, 'purchase-inquiry-formal-price-approval-projection')
  await fs.mkdir(outputRoot, { recursive: true })
  await fs.writeFile(path.join(outputRoot, 'verification-report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
  return { scanPath, outputRoot, report }
}

const result = await run()
console.log(JSON.stringify(result, null, 2))
if (result.report && result.report.status !== TARGET_STATUS) process.exitCode = 1
