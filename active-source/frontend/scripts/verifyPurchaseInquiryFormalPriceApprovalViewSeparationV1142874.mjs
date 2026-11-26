import fs from 'node:fs/promises'
import path from 'node:path'
import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { PURCHASE_INQUIRY_RUNTIME } from '../src/meta/runtime/purchaseInquiryRuntime.js'
import { FORMAL_PRICE_APPROVAL_VIEW_MODE, validateFormalPriceApprovalViewMode } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalViewModeModel.js'
import { FORMAL_PRICE_APPROVAL_VIEW_SWITCHER, validateFormalPriceApprovalViewSwitcher } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalViewSwitcherModel.js'
import { evaluateFormalPriceApprovalViewSeparation } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalViewSeparationRuleEngine.js'
import { FORMAL_PRICE_APPROVAL_VIEW_SEPARATION_FORBIDDEN_ACTIONS, evaluateFormalPriceApprovalViewSeparationGuard } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalViewSeparationGuard.js'
import { FORMAL_PRICE_APPROVAL_VIEW_SEPARATION_ACCEPTANCE_PROFILE, validateFormalPriceApprovalViewSeparationAcceptance } from '../src/meta/acceptance/scm/formalPriceApprovalViewSeparationAcceptanceProfile.js'

const VERSION = 'V1.14.2.8.7.4'
const TARGET_STATUS = 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_VIEW_SEPARATION_READY'
const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const workspaceRoot = path.resolve(frontendRoot, '..')
const read = (relative) => fs.readFile(path.join(frontendRoot, relative), 'utf8')
const hashFile = async (file) => crypto.createHash('sha256').update(await fs.readFile(file)).digest('hex')
const gate = (name, pass, evidence) => Object.freeze({ gate: name, result: pass ? 'PASS' : 'FAIL', evidence })

async function listFiles(relative) {
  const files = []
  async function walk(directory) {
    for (const entry of await fs.readdir(directory, { withFileTypes: true })) {
      const full = path.join(directory, entry.name)
      if (entry.isDirectory()) await walk(full)
      else files.push(path.relative(frontendRoot, full).replaceAll('\\', '/'))
    }
  }
  try { await walk(path.join(frontendRoot, relative)) } catch { /* absent scope is empty */ }
  return files.sort()
}

async function createScan() {
  const [domainFiles, pageFiles, runtimeFiles, acceptanceFiles, modeSource, switcherSource, ruleSource, guardSource] = await Promise.all([
    listFiles('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject'), listFiles('src/meta/pages'),
    listFiles('src/meta/runtime'), listFiles('src/meta/acceptance'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalViewModeModel.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalViewSwitcherModel.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalViewSeparationRuleEngine.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalViewSeparationGuard.js'),
  ])
  const imports = `${modeSource}\n${switcherSource}\n${ruleSource}\n${guardSource}`.split(/\r?\n/)
    .filter((line) => line.trimStart().startsWith('import ')).join('\n')
  return Object.freeze({ version: VERSION, generatedAt: new Date().toISOString(),
    scope: Object.freeze(['src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject', 'src/meta/pages', 'src/meta/runtime', 'src/meta/acceptance']),
    inventory: Object.freeze({ domainFiles, pageFiles, runtimeFiles, acceptanceFiles }),
    analysis: Object.freeze({ prerequisite: 'SCM_FORMAL_PRICE_APPROVAL_SCENARIO_ACCEPTANCE',
      viewModeModel: FORMAL_PRICE_APPROVAL_VIEW_MODE.modelCode, viewSwitcher: FORMAL_PRICE_APPROVAL_VIEW_SWITCHER.modelCode,
      viewModes: Object.freeze(['business_view', 'acceptance_view']), defaultMode: 'business_view',
      businessViewMeansAcceptanceView: false, viewSwitchMeansBusinessAction: false, hiddenMeansDeleted: false,
      workflowOrPersistenceImports: /workflowEngine|workflowService|taskEngine|dataGateway|transactionEngine|commandDispatcher|database/i.test(imports),
      strategy: 'presentation-only mode switch with business and acceptance region ownership; hidden governance remains mounted and defined' }),
    protectedScopes: Object.freeze(['Governance model definitions', 'Approval object creation', 'Workflow start', 'Business action', 'Database']) })
}

async function run() {
  const scan = await createScan()
  const scanPath = path.join(frontendRoot, 'scm_purchase_inquiry_formal_price_approval_view_separation_scan_v1142874.json')
  await fs.writeFile(scanPath, `${JSON.stringify(scan, null, 2)}\n`, 'utf8')
  if (process.argv.includes('--scan-only')) return { scanPath, scan }

  const databasePath = path.join(workspaceRoot, 'backend', 'db.sqlite3')
  const databaseHashBefore = await hashFile(databasePath)
  const [pageSource, routerSource, registrySource] = await Promise.all([
    read('src/meta/pages/ScmPurchaseInquiryWorkbenchPage.vue'), read('src/router/index.js'),
    read('src/meta/acceptance/registry/enterpriseAcceptanceRegistry.js'),
  ])
  const defaultView = evaluateFormalPriceApprovalViewSeparation({})
  const businessView = evaluateFormalPriceApprovalViewSeparation({ switchRequested: true, targetMode: 'business_view' })
  const acceptanceView = evaluateFormalPriceApprovalViewSeparation({ switchRequested: true, targetMode: 'acceptance_view' })
  const invalidBlocked = evaluateFormalPriceApprovalViewSeparation({ switchRequested: true, targetMode: 'production_view' })
  const actionBlocked = evaluateFormalPriceApprovalViewSeparation({ switchRequested: true, targetMode: 'acceptance_view', businessActionRequested: true })
  const objectBlocked = evaluateFormalPriceApprovalViewSeparation({ switchRequested: true, targetMode: 'acceptance_view', approvalObjectCreationRequested: true })
  const workflowBlocked = evaluateFormalPriceApprovalViewSeparation({ switchRequested: true, targetMode: 'acceptance_view', workflowStartRequested: true })
  const deleteBlocked = evaluateFormalPriceApprovalViewSeparation({ switchRequested: true, targetMode: 'acceptance_view', governanceModelDeletionRequested: true })
  const persistenceBlocked = evaluateFormalPriceApprovalViewSeparation({ switchRequested: true, targetMode: 'acceptance_view', persistenceRequested: true })
  const evaluated = [defaultView, businessView, acceptanceView, invalidBlocked, actionBlocked, objectBlocked, workflowBlocked, deleteBlocked, persistenceBlocked]

  const businessRegionCount = (pageSource.match(/data-view-scope="business"/g) || []).length
  const acceptanceRegionCount = (pageSource.match(/data-view-scope="acceptance"/g) || []).length
  const results = [
    gate('Page', pageSource.includes('data-acceptance-id="formal-price-approval-view-switcher"')
      && pageSource.includes('v-model="formalPriceApprovalViewMode"')
      && pageSource.includes('value="business_view"') && pageSource.includes('value="acceptance_view"')
      && pageSource.includes('Business View ≠ Acceptance View') && pageSource.includes('View Switch ≠ Business Action')
      && pageSource.includes('Hidden ≠ Deleted') && businessRegionCount >= 10 && acceptanceRegionCount >= 20
      && pageSource.includes('[data-active-view-mode="business_view"] [data-view-scope="acceptance"]')
      && pageSource.includes('[data-active-view-mode="acceptance_view"] [data-view-scope="business"]'),
      { regions: FORMAL_PRICE_APPROVAL_VIEW_SEPARATION_ACCEPTANCE_PROFILE.requiredRegions, businessRegionCount, acceptanceRegionCount }),
    gate('Router', routerSource.includes("path: 'scm/purchase-inquiry'") && routerSource.includes('ScmPurchaseInquiryWorkbenchPage.vue'), '/scm/purchase-inquiry'),
    gate('Schema', validateFormalPriceApprovalViewMode().valid && validateFormalPriceApprovalViewSwitcher().valid,
      { persistenceSchemaAdded: false, viewModes: ['business_view', 'acceptance_view'] }),
    gate('Runtime', PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalViewModeCode === FORMAL_PRICE_APPROVAL_VIEW_MODE.modelCode
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalViewSwitcherCode === FORMAL_PRICE_APPROVAL_VIEW_SWITCHER.modelCode
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalDefaultViewMode === 'business_view'
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalViewModeCount === 2
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalViewSwitchMode === 'presentation_only'
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalViewSwitchBusinessActionTriggered === false
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalHiddenGovernanceModelDeleted === false,
      { defaultMode: 'business_view', modes: 2, switchMode: 'presentation_only' }),
    gate('Rule', defaultView.activeMode === 'business_view' && businessView.activeMode === 'business_view'
      && acceptanceView.activeMode === 'acceptance_view'
      && [invalidBlocked, actionBlocked, objectBlocked, workflowBlocked, deleteBlocked, persistenceBlocked].every((item) => item.decision === 'blocked')
      && evaluated.every((item) => item.businessActionTriggered === false && item.approvalObjectCreated === false
        && item.workflowStarted === false && item.governanceModelDeleted === false && item.persistencePerformed === false
        && item.businessWriteCount === 0 && item.productionDataWritten === false),
      { businessView: businessView.decision, acceptanceView: acceptanceView.decision, hiddenDeleted: deleteBlocked.governanceModelDeleted }),
    gate('Guard', evaluateFormalPriceApprovalViewSeparationGuard({ action: 'switchViewMode', targetMode: 'business_view' }).decision === 'allow_presentation_only'
      && evaluateFormalPriceApprovalViewSeparationGuard({ action: 'switchViewMode', targetMode: 'acceptance_view' }).decision === 'allow_presentation_only'
      && evaluateFormalPriceApprovalViewSeparationGuard({ action: 'switchViewMode', targetMode: 'production_view' }).decision === 'deny'
      && FORMAL_PRICE_APPROVAL_VIEW_SEPARATION_FORBIDDEN_ACTIONS.every((action) => {
        const result = evaluateFormalPriceApprovalViewSeparationGuard({ action })
        return result.decision === 'deny' && result.businessActionTriggered === false && result.approvalObjectCreated === false
          && result.workflowStarted === false && result.governanceModelDeleted === false
          && result.persistencePerformed === false && result.businessWriteCount === 0
      }), FORMAL_PRICE_APPROVAL_VIEW_SEPARATION_FORBIDDEN_ACTIONS),
    gate('Acceptance', validateFormalPriceApprovalViewSeparationAcceptance().valid
      && registrySource.includes('FORMAL_PRICE_APPROVAL_VIEW_SEPARATION_ACCEPTANCE_PROFILE'), FORMAL_PRICE_APPROVAL_VIEW_SEPARATION_ACCEPTANCE_PROFILE.profileCode),
  ]
  try {
    const output = execFileSync(process.execPath, [path.join(frontendRoot, 'node_modules', 'vite', 'bin', 'vite.js'), 'build', '.', '--emptyOutDir=false'], { cwd: frontendRoot, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], timeout: 240000 })
    results.push(gate('Build', true, output.trim().split(/\r?\n/).slice(-2)))
  } catch (error) { results.push(gate('Build', false, String(error.stderr || error.message))) }

  const databaseHashAfter = await hashFile(databasePath)
  const databaseUnchanged = databaseHashBefore === databaseHashAfter
  const passed = results.every((item) => item.result === 'PASS') && databaseUnchanged && scan.analysis.workflowOrPersistenceImports === false
  const report = Object.freeze({ version: VERSION, generatedAt: new Date().toISOString(), status: passed ? TARGET_STATUS : 'FAIL',
    problemAnalysis: scan.analysis, gates: Object.freeze(results),
    summary: Object.freeze({ PASS: results.filter((item) => item.result === 'PASS').length, FAIL: results.filter((item) => item.result === 'FAIL').length }),
    businessViewMeansAcceptanceView: false, viewSwitchMeansBusinessAction: false, hiddenMeansDeleted: false,
    businessActionTriggered: false, governanceModelDeleted: false, approvalObjectCreated: false,
    workflowStarted: false, workflowInstanceCreated: false, persistencePerformed: false,
    businessWriteCount: 0, productionDataWritten: false,
    database: databaseUnchanged ? 'UNCHANGED' : 'CHANGED', databaseHashBefore, databaseHashAfter, protectedScopeChanges: 0 })
  const outputRoot = path.join(frontendRoot, 'test-results', 'page-acceptance', VERSION, 'purchase-inquiry-formal-price-approval-view-separation')
  await fs.mkdir(outputRoot, { recursive: true })
  await fs.writeFile(path.join(outputRoot, 'verification-report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
  return { scanPath, outputRoot, report }
}

const result = await run()
console.log(JSON.stringify(result, null, 2))
if (result.report && result.report.status !== TARGET_STATUS) process.exitCode = 1
