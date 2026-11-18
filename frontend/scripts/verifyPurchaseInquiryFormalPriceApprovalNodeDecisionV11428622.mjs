import fs from 'node:fs/promises'
import path from 'node:path'
import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { PURCHASE_INQUIRY_RUNTIME } from '../src/meta/runtime/purchaseInquiryRuntime.js'
import { FORMAL_PRICE_APPROVAL_NODE_DEFINITION, validateFormalPriceApprovalNodeDefinition } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalNodeDefinitionModel.js'
import { FORMAL_PRICE_APPROVAL_DECISION_RULE_MODEL, validateFormalPriceApprovalDecisionRuleModel } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalDecisionRuleModel.js'
import { FORMAL_PRICE_APPROVAL_NODE_DECISION_BOUNDARY, validateFormalPriceApprovalNodeDecisionBoundary } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalNodeDecisionBoundary.js'
import { evaluateFormalPriceApprovalNodeDecisionRules } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalNodeDecisionRuleEngine.js'
import { FORMAL_PRICE_APPROVAL_NODE_DECISION_FORBIDDEN_ACTIONS, evaluateFormalPriceApprovalNodeDecisionGuard } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalNodeDecisionGuard.js'
import { FORMAL_PRICE_APPROVAL_NODE_DECISION_ACCEPTANCE_PROFILE, validateFormalPriceApprovalNodeDecisionAcceptance } from '../src/meta/acceptance/scm/formalPriceApprovalNodeDecisionAcceptanceProfile.js'

const VERSION = 'V1.14.2.8.6.22'
const TARGET_STATUS = 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_NODE_DECISION_READY'
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
  const [domainFiles, runtimeFiles, schemaFiles, acceptanceFiles, nodeSource, decisionSource, boundarySource, ruleSource, guardSource] = await Promise.all([
    listFiles('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject'), listFiles('src/meta/runtime'), listFiles('src/meta/schema/scm'), listFiles('src/meta/acceptance/scm'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalNodeDefinitionModel.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalDecisionRuleModel.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalNodeDecisionBoundary.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalNodeDecisionRuleEngine.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalNodeDecisionGuard.js'),
  ])
  const imports = `${nodeSource}\n${decisionSource}\n${boundarySource}\n${ruleSource}\n${guardSource}`
    .split(/\r?\n/).filter((line) => line.trimStart().startsWith('import ')).join('\n')
  return Object.freeze({
    version: VERSION, generatedAt: new Date().toISOString(),
    scope: Object.freeze(['src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject', 'src/meta/runtime', 'src/meta/schema/scm', 'src/meta/acceptance/scm']),
    inventory: Object.freeze({ domainFiles, runtimeFiles, schemaFiles, acceptanceFiles }),
    analysis: Object.freeze({ prerequisite: 'SCM_FORMAL_PRICE_APPROVAL_WORKFLOW_RUNTIME_STATE', nodeDefinition: FORMAL_PRICE_APPROVAL_NODE_DEFINITION.definitionCode,
      decisionRule: FORMAL_PRICE_APPROVAL_DECISION_RULE_MODEL.ruleModelCode, boundary: FORMAL_PRICE_APPROVAL_NODE_DECISION_BOUNDARY.boundaryCode,
      nodeDefinitionMeansTaskCreated: false, decisionRuleMeansResult: false, approvalDecisionMeansBusinessEffect: false,
      workflowOrPersistenceImports: /workflowEngine|workflowService|stateManager|dataGateway|transactionEngine|commandDispatcher/i.test(imports),
      strategy: 'definition-only approval nodes and decision rules isolated from tasks, results, and business effects' }),
    protectedScopes: Object.freeze(['Approval task creation', 'Node execution', 'Approval result creation', 'Business effect', 'Database']),
  })
}

async function run() {
  const scan = await createScan()
  const scanPath = path.join(frontendRoot, 'scm_purchase_inquiry_formal_price_approval_node_decision_scan_v11428622.json')
  await fs.writeFile(scanPath, `${JSON.stringify(scan, null, 2)}\n`, 'utf8')
  if (process.argv.includes('--scan-only')) return { scanPath, scan }

  const databasePath = path.join(workspaceRoot, 'backend', 'db.sqlite3')
  const databaseHashBefore = await hashFile(databasePath)
  const [pageSource, routerSource, registrySource] = await Promise.all([
    read('src/meta/pages/ScmPurchaseInquiryWorkbenchPage.vue'), read('src/router/index.js'), read('src/meta/acceptance/registry/enterpriseAcceptanceRegistry.js'),
  ])
  const safeInput = Object.freeze({ assessmentRequested: true, workflowRuntimeStatus: 'runtime_definition_ready', nodeDefinitionsComplete: true, decisionRulesComplete: true, nodeDecisionBoundaryIsolated: true })
  const ready = evaluateFormalPriceApprovalNodeDecisionRules(safeInput)
  const notAssessed = evaluateFormalPriceApprovalNodeDecisionRules({})
  const missingBoundary = evaluateFormalPriceApprovalNodeDecisionRules({ ...safeInput, nodeDecisionBoundaryIsolated: false })
  const taskBlocked = evaluateFormalPriceApprovalNodeDecisionRules({ ...safeInput, taskCreationRequested: true })
  const nodeBlocked = evaluateFormalPriceApprovalNodeDecisionRules({ ...safeInput, nodeExecutionRequested: true })
  const decisionBlocked = evaluateFormalPriceApprovalNodeDecisionRules({ ...safeInput, decisionExecutionRequested: true })
  const resultBlocked = evaluateFormalPriceApprovalNodeDecisionRules({ ...safeInput, approvalResultCreationRequested: true })
  const effectBlocked = evaluateFormalPriceApprovalNodeDecisionRules({ ...safeInput, businessEffectRequested: true })
  const persistenceBlocked = evaluateFormalPriceApprovalNodeDecisionRules({ ...safeInput, persistenceRequested: true })
  const evaluated = [notAssessed, ready, missingBoundary, taskBlocked, nodeBlocked, decisionBlocked, resultBlocked, effectBlocked, persistenceBlocked]
  const results = [
    gate('Page', pageSource.includes('data-acceptance-id="formal-price-approval-node-decision"')
      && pageSource.includes('Node Definition ≠ Task Created') && pageSource.includes('Decision Rule ≠ Result') && pageSource.includes('Approval Decision ≠ Business Effect'), FORMAL_PRICE_APPROVAL_NODE_DECISION_ACCEPTANCE_PROFILE.requiredRegions),
    gate('Router', routerSource.includes("path: 'scm/purchase-inquiry'") && routerSource.includes('ScmPurchaseInquiryWorkbenchPage.vue'), '/scm/purchase-inquiry'),
    gate('Schema', validateFormalPriceApprovalNodeDefinition().valid && validateFormalPriceApprovalDecisionRuleModel().valid
      && validateFormalPriceApprovalNodeDecisionBoundary().valid && routerSource.includes("schema: 'PriceApprovalSchema'")
      && FORMAL_PRICE_APPROVAL_NODE_DECISION_BOUNDARY.persistenceAdapterConnected === false, { persistenceSchemaAdded: false, nodeCount: FORMAL_PRICE_APPROVAL_NODE_DEFINITION.nodes.length, ruleCount: FORMAL_PRICE_APPROVAL_DECISION_RULE_MODEL.rules.length }),
    gate('Runtime', PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalNodeDefinitionCode === FORMAL_PRICE_APPROVAL_NODE_DEFINITION.definitionCode
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalDecisionRuleCode === FORMAL_PRICE_APPROVAL_DECISION_RULE_MODEL.ruleModelCode
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalNodeDecisionBoundaryCode === FORMAL_PRICE_APPROVAL_NODE_DECISION_BOUNDARY.boundaryCode
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalNodeDefinitionCount === 3
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalNodeRuntimeCount === 0
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalNodeTaskCount === 0
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalNodeDecisionResultCount === 0
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalNodeDecisionBusinessEffectApplied === false, { nodeDefinitions: 3, nodeRuntime: 0, tasks: 0, results: 0, businessEffect: false }),
    gate('Rule', notAssessed.definitionStatus === 'not_assessed' && ready.definitionStatus === 'node_decision_definition_ready'
      && [missingBoundary, taskBlocked, nodeBlocked, decisionBlocked, resultBlocked, effectBlocked, persistenceBlocked].every((item) => item.definitionStatus === 'blocked')
      && evaluated.every((item) => item.taskCreated === false && item.nodeExecuted === false && item.decisionExecuted === false && item.approvalResultCreated === false && item.businessEffectApplied === false && item.businessStateChanged === false && item.persistencePerformed === false && item.businessWriteCount === 0 && item.productionDataWritten === false), { ready: ready.definitionStatus, nodeExecution: nodeBlocked.definitionStatus, resultCreation: resultBlocked.definitionStatus, businessEffect: effectBlocked.definitionStatus }),
    gate('Guard', evaluateFormalPriceApprovalNodeDecisionGuard({ action: 'inspectNodeDecisionDefinition', mode: 'definition_inspection_only' }).decision === 'allow_definition_inspection_only'
      && evaluateFormalPriceApprovalNodeDecisionGuard({ action: 'inspectNodeDecisionDefinition', mode: 'execution' }).decision === 'deny'
      && FORMAL_PRICE_APPROVAL_NODE_DECISION_FORBIDDEN_ACTIONS.every((action) => {
        const result = evaluateFormalPriceApprovalNodeDecisionGuard({ action })
        return result.decision === 'deny' && result.taskCreated === false && result.nodeExecuted === false && result.approvalResultCreated === false && result.businessEffectApplied === false && result.persistencePerformed === false
      }), FORMAL_PRICE_APPROVAL_NODE_DECISION_FORBIDDEN_ACTIONS),
    gate('Acceptance', validateFormalPriceApprovalNodeDecisionAcceptance().valid
      && registrySource.includes('FORMAL_PRICE_APPROVAL_NODE_DECISION_ACCEPTANCE_PROFILE'), FORMAL_PRICE_APPROVAL_NODE_DECISION_ACCEPTANCE_PROFILE.profileCode),
  ]
  try {
    const output = execFileSync(process.execPath, [path.join(frontendRoot, 'node_modules', 'vite', 'bin', 'vite.js'), 'build', '.', '--emptyOutDir=false'], { cwd: frontendRoot, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], timeout: 240000 })
    results.push(gate('Build', true, output.trim().split(/\r?\n/).slice(-2)))
  } catch (error) { results.push(gate('Build', false, String(error.stderr || error.message))) }

  const databaseHashAfter = await hashFile(databasePath)
  const databaseUnchanged = databaseHashBefore === databaseHashAfter
  const passed = results.every((item) => item.result === 'PASS') && databaseUnchanged && scan.analysis.workflowOrPersistenceImports === false
  const report = Object.freeze({
    version: VERSION, generatedAt: new Date().toISOString(), status: passed ? TARGET_STATUS : 'FAIL', problemAnalysis: scan.analysis,
    gates: Object.freeze(results), summary: Object.freeze({ PASS: results.filter((item) => item.result === 'PASS').length, FAIL: results.filter((item) => item.result === 'FAIL').length }),
    nodeDefinitionMeansTaskCreated: false, decisionRuleMeansResult: false, approvalDecisionMeansBusinessEffect: false,
    taskCreated: false, nodeExecuted: false, decisionExecuted: false, approvalResultCreated: false, businessEffectApplied: false, businessStateChanged: false, persistencePerformed: false,
    businessWriteCount: 0, productionDataWritten: false, database: databaseUnchanged ? 'UNCHANGED' : 'CHANGED', databaseHashBefore, databaseHashAfter, protectedScopeChanges: 0,
  })
  const outputRoot = path.join(frontendRoot, 'test-results', 'page-acceptance', VERSION, 'purchase-inquiry-formal-price-approval-node-decision')
  await fs.mkdir(outputRoot, { recursive: true })
  await fs.writeFile(path.join(outputRoot, 'verification-report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
  return { scanPath, outputRoot, report }
}

const result = await run()
console.log(JSON.stringify(result, null, 2))
if (result.report && result.report.status !== TARGET_STATUS) process.exitCode = 1
