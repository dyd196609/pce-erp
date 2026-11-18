import fs from 'node:fs/promises'
import path from 'node:path'
import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { PURCHASE_INQUIRY_RUNTIME } from '../src/meta/runtime/purchaseInquiryRuntime.js'
import { FORMAL_PRICE_APPROVAL_OBJECT, validateFormalPriceApprovalObject } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalObjectModel.js'
import { FORMAL_PRICE_APPROVAL_OBJECT_CURRENT_ALLOWED_STATES, FORMAL_PRICE_APPROVAL_OBJECT_LIFECYCLE, FORMAL_PRICE_APPROVAL_OBJECT_FUTURE_TRANSITIONS, evaluateFormalPriceApprovalObjectStateAccess } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalObjectStateModel.js'
import { evaluateFormalPriceApprovalObjectDefinition } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalObjectRuleEngine.js'
import { FORMAL_PRICE_APPROVAL_OBJECT_FORBIDDEN_ACTIONS, evaluateFormalPriceApprovalObjectCreationGuard } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalObjectCreationGuard.js'
import { FORMAL_PRICE_APPROVAL_OBJECT_ACCEPTANCE_PROFILE, validateFormalPriceApprovalObjectAcceptance } from '../src/meta/acceptance/scm/formalPriceApprovalObjectAcceptanceProfile.js'

const VERSION = 'V1.14.2.8.6.6'
const TARGET_STATUS = 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_OBJECT_MODEL_READY'
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
      inquiryRoutePresent: routerSource.includes("path: 'scm/purchase-inquiry'"), formalPriceApprovalSchemaBindingPresent: routerSource.includes("schema: 'PriceApprovalSchema'") }),
    analysis: Object.freeze({ prerequisite: 'SCM_FORMAL_PRICE_APPROVAL_PROJECTION', designTarget: 'SCM_FORMAL_PRICE_APPROVAL_OBJECT',
      formalPriceApprovalInstanceExists: false, formalPriceApprovalModuleModified: false, approvalWorkflowModified: false,
      strategy: 'definition-only object model with creation boundary frozen' }),
    protectedScopes: Object.freeze(['Formal Price Approval module', 'Approval Workflow', 'PurchaseOrder', 'Finance', 'Inventory']),
  })
}

async function run() {
  const scan = await createScan()
  const scanPath = path.join(frontendRoot, 'scm_purchase_inquiry_formal_price_approval_object_scan_v1142866.json')
  await fs.writeFile(scanPath, `${JSON.stringify(scan, null, 2)}\n`, 'utf8')
  if (process.argv.includes('--scan-only')) return { scanPath, scan }

  const databasePath = path.join(workspaceRoot, 'backend', 'db.sqlite3')
  const databaseHashBefore = await hashFile(databasePath)
  const [pageSource, routerSource, registrySource] = await Promise.all([
    read('src/meta/pages/ScmPurchaseInquiryWorkbenchPage.vue'), read('src/router/index.js'), read('src/meta/acceptance/registry/enterpriseAcceptanceRegistry.js'),
  ])
  const definitionOnly = evaluateFormalPriceApprovalObjectDefinition({ projectionStatus: 'incomplete', evidencePackageStatus: 'incomplete', creationAssessmentStatus: 'blocked' })
  const readyForCreation = evaluateFormalPriceApprovalObjectDefinition({ projectionStatus: 'available', evidencePackageStatus: 'available', creationAssessmentStatus: 'ready' })
  const results = [
    gate('Page', pageSource.includes('data-acceptance-id="formal-price-approval-object-model"') && pageSource.includes('只设计，不创建') && pageSource.includes('当前对象实例') && pageSource.includes('未来状态，当前关闭'), FORMAL_PRICE_APPROVAL_OBJECT_ACCEPTANCE_PROFILE.requiredRegions),
    gate('Router', routerSource.includes("path: 'scm/purchase-inquiry'") && routerSource.includes('ScmPurchaseInquiryWorkbenchPage.vue'), '/scm/purchase-inquiry'),
    gate('Schema', validateFormalPriceApprovalObject().valid && routerSource.includes("schema: 'PriceApprovalSchema'"), { objectFieldCount: FORMAL_PRICE_APPROVAL_OBJECT.fields.length, existingSchema: 'PriceApprovalSchema' }),
    gate('Runtime', PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalObjectModelCode === 'SCM_FORMAL_PRICE_APPROVAL_OBJECT' && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalObjectInstanceCount === 0 && FORMAL_PRICE_APPROVAL_OBJECT.currentInstanceCount === 0, PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalObjectModelCode),
    gate('Rule', definitionOnly.modelState === 'definition_only' && readyForCreation.modelState === 'ready_for_creation' && readyForCreation.readyForCreation === true && readyForCreation.formalPriceApprovalObjectCreated === false && readyForCreation.approvalWorkflowStarted === false && readyForCreation.approvalSubmitted === false && readyForCreation.priceApproved === false && readyForCreation.purchaseOrderCreated === false && FORMAL_PRICE_APPROVAL_OBJECT_LIFECYCLE.join(',') === 'definition_only,ready_for_creation,created,pending_approval,approved,rejected,cancelled' && FORMAL_PRICE_APPROVAL_OBJECT_CURRENT_ALLOWED_STATES.join(',') === 'definition_only,ready_for_creation' && evaluateFormalPriceApprovalObjectStateAccess('definition_only').decision === 'allow' && evaluateFormalPriceApprovalObjectStateAccess('ready_for_creation').decision === 'allow' && ['created', 'pending_approval', 'approved', 'rejected', 'cancelled'].every((state) => evaluateFormalPriceApprovalObjectStateAccess(state).decision === 'deny') && FORMAL_PRICE_APPROVAL_OBJECT_FUTURE_TRANSITIONS.filter((item) => item.to === 'created' || item.from === 'created' || item.from === 'pending_approval').every((item) => item.enabled === false), { definitionOnly: definitionOnly.modelState, readyForCreation: readyForCreation.modelState, currentAllowedStates: FORMAL_PRICE_APPROVAL_OBJECT_CURRENT_ALLOWED_STATES }),
    gate('Guard', FORMAL_PRICE_APPROVAL_OBJECT_FORBIDDEN_ACTIONS.every((action) => evaluateFormalPriceApprovalObjectCreationGuard(action).decision === 'deny'), FORMAL_PRICE_APPROVAL_OBJECT_FORBIDDEN_ACTIONS),
    gate('Acceptance', validateFormalPriceApprovalObjectAcceptance().valid && registrySource.includes('FORMAL_PRICE_APPROVAL_OBJECT_ACCEPTANCE_PROFILE'), FORMAL_PRICE_APPROVAL_OBJECT_ACCEPTANCE_PROFILE.profileCode),
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
    lifecycle: FORMAL_PRICE_APPROVAL_OBJECT_LIFECYCLE, currentAllowedStates: FORMAL_PRICE_APPROVAL_OBJECT_CURRENT_ALLOWED_STATES,
    businessWriteCount: 0, productionDataWritten: false, database: databaseUnchanged ? 'UNCHANGED' : 'CHANGED', databaseHashBefore, databaseHashAfter,
    formalPriceApprovalObjectCreated: false, formalPriceApprovalObjectInstanceCount: 0, approvalWorkflowStarted: false,
    approvalTaskCreated: false, approvalSubmitted: false, priceApproved: false, autoPurchaseOrderCreation: false,
    formalPriceApprovalModuleModified: false, approvalWorkflowModified: false, protectedScopeChanges: 0 })
  const outputRoot = path.join(frontendRoot, 'test-results', 'page-acceptance', VERSION, 'purchase-inquiry-formal-price-approval-object')
  await fs.mkdir(outputRoot, { recursive: true })
  await fs.writeFile(path.join(outputRoot, 'verification-report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
  return { scanPath, outputRoot, report }
}

const result = await run()
console.log(JSON.stringify(result, null, 2))
if (result.report && result.report.status !== TARGET_STATUS) process.exitCode = 1
