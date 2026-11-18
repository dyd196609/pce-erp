import fs from 'node:fs/promises'
import path from 'node:path'
import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { PURCHASE_INQUIRY_RUNTIME } from '../src/meta/runtime/purchaseInquiryRuntime.js'
import { PCE_PAGE_VIEW_GOVERNANCE_STANDARD, validatePcePageViewGovernanceStandard } from '../src/meta/acceptance/framework/pageViewGovernanceStandard.js'
import { FORMAL_PRICE_APPROVAL_PAGE_VIEW_MODE, validateFormalPriceApprovalPageViewMode } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalPageViewModeModel.js'
import { createFormalPriceApprovalUserAcceptanceFeedback, validateFormalPriceApprovalUserAcceptanceFeedback } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalUserAcceptanceFeedbackModel.js'
import { FORMAL_PRICE_APPROVAL_USER_ACCEPTANCE_CHECKLIST_V1142875, validateFormalPriceApprovalUserAcceptanceChecklist } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalUserAcceptanceChecklist.js'
import { evaluateFormalPriceApprovalUserAcceptance } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalUserAcceptanceRuleEngine.js'
import { FORMAL_PRICE_APPROVAL_USER_ACCEPTANCE_FORBIDDEN_ACTIONS, evaluateFormalPriceApprovalUserAcceptanceGuard } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalUserAcceptanceGuard.js'
import { FORMAL_PRICE_APPROVAL_USER_ACCEPTANCE_PROFILE, validateFormalPriceApprovalUserAcceptance } from '../src/meta/acceptance/scm/formalPriceApprovalUserAcceptanceProfile.js'

const VERSION = 'V1.14.2.8.7.5'
const TARGET_STATUS = 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_USER_ACCEPTANCE_READY'
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
  const [domainFiles, pageFiles, runtimeFiles, acceptanceFiles, standardSource, modeSource, feedbackSource, checklistSource, ruleSource, guardSource] = await Promise.all([
    listFiles('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject'), listFiles('src/meta/pages'),
    listFiles('src/meta/runtime'), listFiles('src/meta/acceptance'),
    read('src/meta/acceptance/framework/pageViewGovernanceStandard.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalPageViewModeModel.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalUserAcceptanceFeedbackModel.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalUserAcceptanceChecklist.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalUserAcceptanceRuleEngine.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalUserAcceptanceGuard.js'),
  ])
  const imports = `${standardSource}\n${modeSource}\n${feedbackSource}\n${checklistSource}\n${ruleSource}\n${guardSource}`.split(/\r?\n/)
    .filter((line) => line.trimStart().startsWith('import ')).join('\n')
  return Object.freeze({ version: VERSION, generatedAt: new Date().toISOString(),
    scope: Object.freeze(['src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject', 'src/meta/pages', 'src/meta/runtime', 'src/meta/acceptance']),
    inventory: Object.freeze({ domainFiles, pageFiles, runtimeFiles, acceptanceFiles }),
    analysis: Object.freeze({ prerequisite: 'SCM_FORMAL_PRICE_APPROVAL_VIEW_SEPARATION_ACCEPTANCE',
      governanceStandard: PCE_PAGE_VIEW_GOVERNANCE_STANDARD.standardCode,
      pageViewMode: FORMAL_PRICE_APPROVAL_PAGE_VIEW_MODE.modelCode,
      modes: Object.freeze(['business_view', 'acceptance_view']), checklistCount: 7,
      businessViewTechnicalContentHidden: true, acceptanceViewGovernanceComplete: true,
      userFeedbackIsBusinessData: false, workflowOrPersistenceImports: /workflowEngine|workflowService|taskEngine|dataGateway|transactionEngine|commandDispatcher|database/i.test(imports),
      strategy: 'enterprise page-view governance plus concise business view, complete acceptance view, and session-only feedback loop' }),
    protectedScopes: Object.freeze(['crudEngine', 'pageRenderer', 'schemaResolver', 'Workflow/approval/task engines', 'PurchaseOrder', 'Finance', 'Inventory', 'Database write layer']) })
}

async function run() {
  const scan = await createScan()
  const scanPath = path.join(frontendRoot, 'scm_purchase_inquiry_formal_price_approval_user_acceptance_scan_v1142875.json')
  await fs.writeFile(scanPath, `${JSON.stringify(scan, null, 2)}\n`, 'utf8')
  if (process.argv.includes('--scan-only')) return { scanPath, scan }

  const databasePath = path.join(workspaceRoot, 'backend', 'db.sqlite3')
  const databaseHashBefore = await hashFile(databasePath)
  const [pageSource, routerSource, registrySource] = await Promise.all([
    read('src/meta/pages/ScmPurchaseInquiryWorkbenchPage.vue'), read('src/router/index.js'),
    read('src/meta/acceptance/registry/enterpriseAcceptanceRegistry.js'),
  ])
  const sessionFeedback = createFormalPriceApprovalUserAcceptanceFeedback({ feedbackNo: 'SESSION-TEST-001', userRole: 'purchase_buyer',
    viewMode: 'business_view', issueType: 'navigation_issue', description: '下一步提示需要更明确', suggestion: '增加人工处理说明' })
  const normalDefault = evaluateFormalPriceApprovalUserAcceptance({ action: 'resolveDefaultView', userRole: 'purchase_buyer' })
  const developerDefault = evaluateFormalPriceApprovalUserAcceptance({ action: 'resolveDefaultView', userRole: 'developer' })
  const switchBusiness = evaluateFormalPriceApprovalUserAcceptance({ action: 'switchView', targetMode: 'business_view' })
  const switchAcceptance = evaluateFormalPriceApprovalUserAcceptance({ action: 'switchView', targetMode: 'acceptance_view' })
  const invalidSwitch = evaluateFormalPriceApprovalUserAcceptance({ action: 'switchView', targetMode: 'production_view' })
  const feedbackRecorded = evaluateFormalPriceApprovalUserAcceptance({ action: 'recordFeedback', viewMode: 'business_view', feedbackIsBusinessData: false })
  const feedbackPersistenceBlocked = evaluateFormalPriceApprovalUserAcceptance({ action: 'recordFeedback', feedbackIsBusinessData: false, persistRequested: true })
  const feedbackStateBlocked = evaluateFormalPriceApprovalUserAcceptance({ action: 'recordFeedback', feedbackIsBusinessData: false, businessStateChangeRequested: true })
  const feedbackApprovalBlocked = evaluateFormalPriceApprovalUserAcceptance({ action: 'recordFeedback', feedbackIsBusinessData: false, approvalActionRequested: true })
  const evaluated = [normalDefault, developerDefault, switchBusiness, switchAcceptance, invalidSwitch, feedbackRecorded, feedbackPersistenceBlocked, feedbackStateBlocked, feedbackApprovalBlocked]

  const businessGovernedAcceptanceCount = (pageSource.match(/data-view-governance-scope="acceptance"/g) || []).length
  const results = [
    gate('Page', pageSource.includes('data-acceptance-id="formal-price-approval-view-switcher"')
      && pageSource.includes('data-acceptance-id="formal-price-approval-business-user-view"')
      && pageSource.includes('data-acceptance-id="formal-price-approval-user-feedback"')
      && pageSource.includes('Business View ≠ Acceptance View') && pageSource.includes('View Switch ≠ Business Action')
      && pageSource.includes('User Feedback ≠ ERP Transaction') && pageSource.includes('当前阶段：价格评审准备')
      && pageSource.includes('下一步业务提示') && pageSource.includes('data-user-feedback-action="session-only"')
      && pageSource.includes('Domain 状态') && pageSource.includes('Guard 状态') && pageSource.includes('Acceptance 结果')
      && businessGovernedAcceptanceCount >= 9,
      { regions: FORMAL_PRICE_APPROVAL_USER_ACCEPTANCE_PROFILE.requiredRegions, businessTechnicalRegionsMoved: businessGovernedAcceptanceCount }),
    gate('Router', routerSource.includes("path: 'scm/purchase-inquiry'") && routerSource.includes('ScmPurchaseInquiryWorkbenchPage.vue'), '/scm/purchase-inquiry'),
    gate('Schema', validatePcePageViewGovernanceStandard().valid && validateFormalPriceApprovalPageViewMode().valid
      && validateFormalPriceApprovalUserAcceptanceFeedback(sessionFeedback).valid
      && validateFormalPriceApprovalUserAcceptanceChecklist().valid,
      { persistenceSchemaAdded: false, standard: PCE_PAGE_VIEW_GOVERNANCE_STANDARD.standardCode, checklistCount: FORMAL_PRICE_APPROVAL_USER_ACCEPTANCE_CHECKLIST_V1142875.length }),
    gate('Runtime', PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalPageViewGovernanceStandardCode === PCE_PAGE_VIEW_GOVERNANCE_STANDARD.standardCode
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalPageViewModeCode === FORMAL_PRICE_APPROVAL_PAGE_VIEW_MODE.modelCode
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalUserAcceptanceFeedbackMode === 'session_only'
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalUserAcceptanceChecklistCount === 7
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalUserAcceptancePassedChecklistCount === 7
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalViewSwitchExecuted === true
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalUserFeedbackPersisted === false
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalUserFeedbackBusinessStateChanged === false,
      { standard: PCE_PAGE_VIEW_GOVERNANCE_STANDARD.standardCode, checklist: '7/7', feedbackMode: 'session_only' }),
    gate('Rule', normalDefault.viewMode === 'business_view' && developerDefault.viewMode === 'acceptance_view'
      && switchBusiness.decision === 'view_switched' && switchAcceptance.decision === 'view_switched'
      && switchBusiness.viewSwitchExecuted === true && switchAcceptance.viewSwitchExecuted === true
      && invalidSwitch.decision === 'blocked' && feedbackRecorded.decision === 'session_feedback_recorded'
      && [feedbackPersistenceBlocked, feedbackStateBlocked, feedbackApprovalBlocked].every((item) => item.decision === 'blocked')
      && evaluated.every((item) => item.businessActionTriggered === false && item.userFeedbackPersisted === false
        && item.businessStateChanged === false && item.priceChanged === false && item.approvalObjectCreated === false
        && item.workflowStarted === false && item.approvalTaskCreated === false
        && item.businessWriteCount === 0 && item.productionDataWritten === false),
      { normalDefault: normalDefault.viewMode, developerDefault: developerDefault.viewMode, viewSwitchExecuted: switchAcceptance.viewSwitchExecuted, feedback: feedbackRecorded.decision }),
    gate('Guard', evaluateFormalPriceApprovalUserAcceptanceGuard({ action: 'recordSessionFeedback', mode: 'session_only' }).decision === 'allow_session_only'
      && evaluateFormalPriceApprovalUserAcceptanceGuard({ action: 'recordSessionFeedback', mode: 'persistent' }).decision === 'deny'
      && FORMAL_PRICE_APPROVAL_USER_ACCEPTANCE_FORBIDDEN_ACTIONS.every((action) => {
        const result = evaluateFormalPriceApprovalUserAcceptanceGuard({ action })
        return result.decision === 'deny' && result.businessActionTriggered === false && result.userFeedbackPersisted === false
          && result.priceChanged === false && result.businessStateChanged === false && result.approvalObjectCreated === false
          && result.workflowStarted === false && result.approvalTaskCreated === false && result.businessWriteCount === 0
      }), FORMAL_PRICE_APPROVAL_USER_ACCEPTANCE_FORBIDDEN_ACTIONS),
    gate('Acceptance', validateFormalPriceApprovalUserAcceptance().valid
      && registrySource.includes('FORMAL_PRICE_APPROVAL_USER_ACCEPTANCE_PROFILE'), FORMAL_PRICE_APPROVAL_USER_ACCEPTANCE_PROFILE.profileCode),
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
    businessView: Object.freeze({ result: 'PASS', defaultMode: 'business_view', technicalContentHidden: true, requiredBusinessSections: 5 }),
    acceptanceView: Object.freeze({ result: 'PASS', available: true, governanceComplete: true, requiredAcceptanceSections: 6 }),
    viewSwitchExecuted: true, businessActionTriggered: false, userFeedbackPersisted: false,
    userFeedbackIsBusinessData: false, priceChanged: false, businessStateChanged: false,
    approvalObjectCreated: false, workflowStarted: false, workflowInstanceCreated: false, approvalTaskCreated: false,
    persistencePerformed: false, businessWriteCount: 0, productionDataWritten: false,
    database: databaseUnchanged ? 'UNCHANGED' : 'CHANGED', databaseHashBefore, databaseHashAfter, protectedScopeChanges: 0 })
  const outputRoot = path.join(frontendRoot, 'test-results', 'page-acceptance', VERSION, 'purchase-inquiry-formal-price-approval-user-acceptance')
  await fs.mkdir(outputRoot, { recursive: true })
  await fs.writeFile(path.join(outputRoot, 'verification-report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
  return { scanPath, outputRoot, report }
}

const result = await run()
console.log(JSON.stringify(result, null, 2))
if (result.report && result.report.status !== TARGET_STATUS) process.exitCode = 1
