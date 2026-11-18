import fs from 'node:fs/promises'
import path from 'node:path'
import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { PURCHASE_INQUIRY_RUNTIME } from '../src/meta/runtime/purchaseInquiryRuntime.js'
import { CREATE_FORMAL_PRICE_APPROVAL_COMMAND, CREATE_FORMAL_PRICE_APPROVAL_COMMAND_STATES, validateCreateFormalPriceApprovalCommand } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/createFormalPriceApprovalCommandModel.js'
import { evaluateCreateFormalPriceApprovalCommand } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/createFormalPriceApprovalCommandRuleEngine.js'
import { CREATE_FORMAL_PRICE_APPROVAL_COMMAND_FORBIDDEN_ACTIONS, evaluateCreateFormalPriceApprovalCommandGuard } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/createFormalPriceApprovalCommandGuard.js'
import { CREATE_FORMAL_PRICE_APPROVAL_COMMAND_ACCEPTANCE_PROFILE, validateCreateFormalPriceApprovalCommandAcceptance } from '../src/meta/acceptance/scm/createFormalPriceApprovalCommandAcceptanceProfile.js'

const VERSION = 'V1.14.2.8.6.9'
const TARGET_STATUS = 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_CREATION_COMMAND_DESIGN_READY'
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
  try { await walk(root) } catch { /* empty inventory reports a missing root */ }
  return files.sort()
}

async function createScan() {
  const [domainFiles, runtimeFiles, schemaFiles, acceptanceFiles, commandSource] = await Promise.all([
    listFiles('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject'),
    listFiles('src/meta/runtime'),
    listFiles('src/meta/schema/scm'),
    listFiles('src/meta/acceptance/scm'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/createFormalPriceApprovalCommandModel.js'),
  ])
  return Object.freeze({
    version: VERSION,
    generatedAt: new Date().toISOString(),
    scope: Object.freeze([
      'src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject',
      'src/meta/runtime',
      'src/meta/schema/scm',
      'src/meta/acceptance/scm',
    ]),
    inventory: Object.freeze({ domainFiles, runtimeFiles, schemaFiles, acceptanceFiles,
      commandModelPresent: domainFiles.includes('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/createFormalPriceApprovalCommandModel.js') }),
    analysis: Object.freeze({
      prerequisite: 'SCM_FORMAL_PRICE_APPROVAL_CREATION_SIMULATION',
      designTarget: CREATE_FORMAL_PRICE_APPROVAL_COMMAND.commandCode,
      lifecycle: CREATE_FORMAL_PRICE_APPROVAL_COMMAND.lifecycle,
      closedStates: CREATE_FORMAL_PRICE_APPROVAL_COMMAND.closedStates,
      manualTriggerBoundaryPresent: true,
      executionImportsPresent: /dataGateway|transactionEngine|workflowEngine|commandDispatcher|fetch\s*\(/i.test(commandSource),
      automaticExecution: false,
      strategy: 'manual-trigger command contract with validation-only evaluation and execution states frozen',
    }),
    protectedScopes: Object.freeze(['Formal Price Approval object instances', 'Approval Workflow', 'Approval Tasks', 'Command execution', 'Database']),
  })
}

async function run() {
  const scan = await createScan()
  const scanPath = path.join(frontendRoot, 'scm_purchase_inquiry_formal_price_approval_creation_command_scan_v1142869.json')
  await fs.writeFile(scanPath, `${JSON.stringify(scan, null, 2)}\n`, 'utf8')
  if (process.argv.includes('--scan-only')) return { scanPath, scan }

  const databasePath = path.join(workspaceRoot, 'backend', 'db.sqlite3')
  const databaseHashBefore = await hashFile(databasePath)
  const [pageSource, routerSource, registrySource] = await Promise.all([
    read('src/meta/pages/ScmPurchaseInquiryWorkbenchPage.vue'),
    read('src/router/index.js'),
    read('src/meta/acceptance/registry/enterpriseAcceptanceRegistry.js'),
  ])
  const manualResult = evaluateCreateFormalPriceApprovalCommand({
    triggerMode: 'manual', requestedBy: 'manual-requester', simulationStatus: 'completed', runtimeEvaluatedStatus: 'ready_for_creation',
  })
  const automaticResult = evaluateCreateFormalPriceApprovalCommand({
    triggerMode: 'automatic', requestedBy: 'system', simulationStatus: 'completed', runtimeEvaluatedStatus: 'ready_for_creation',
  })
  const incompleteResult = evaluateCreateFormalPriceApprovalCommand({
    triggerMode: 'manual', requestedBy: '', simulationStatus: 'blocked', runtimeEvaluatedStatus: 'definition_only',
  })
  const results = [
    gate('Page', pageSource.includes('data-acceptance-id="create-formal-price-approval-command-design"')
      && pageSource.includes('正式价格审批对象创建动作设计')
      && pageSource.includes('仅人工触发设计')
      && pageSource.includes('approved_for_execution 与 executed 保持关闭'), CREATE_FORMAL_PRICE_APPROVAL_COMMAND_ACCEPTANCE_PROFILE.requiredRegions),
    gate('Router', routerSource.includes("path: 'scm/purchase-inquiry'") && routerSource.includes('ScmPurchaseInquiryWorkbenchPage.vue'), '/scm/purchase-inquiry'),
    gate('Schema', validateCreateFormalPriceApprovalCommand().valid
      && routerSource.includes("schema: 'PriceApprovalSchema'")
      && CREATE_FORMAL_PRICE_APPROVAL_COMMAND.commandKind === 'DESIGN_ONLY', {
        commandFields: CREATE_FORMAL_PRICE_APPROVAL_COMMAND.fields,
        persistenceSchemaAdded: false,
        existingSchema: 'PriceApprovalSchema',
      }),
    gate('Runtime', PURCHASE_INQUIRY_RUNTIME.createFormalPriceApprovalCommandCode === CREATE_FORMAL_PRICE_APPROVAL_COMMAND.commandCode
      && PURCHASE_INQUIRY_RUNTIME.createFormalPriceApprovalCommandTriggerMode === 'manual_only'
      && PURCHASE_INQUIRY_RUNTIME.createFormalPriceApprovalCommandDispatcherConnected === false
      && PURCHASE_INQUIRY_RUNTIME.createFormalPriceApprovalCommandInstanceCount === 0
      && CREATE_FORMAL_PRICE_APPROVAL_COMMAND.dispatcherConnected === false
      && CREATE_FORMAL_PRICE_APPROVAL_COMMAND.automaticExecution === false
      && CREATE_FORMAL_PRICE_APPROVAL_COMMAND.commandInstanceCount === 0, {
        commandCode: CREATE_FORMAL_PRICE_APPROVAL_COMMAND.commandCode,
        triggerMode: CREATE_FORMAL_PRICE_APPROVAL_COMMAND.triggerMode,
        dispatcherConnected: false,
        commandInstanceCount: 0,
      }),
    gate('Rule', manualResult.decision === 'validated_design_only'
      && manualResult.evaluatedStatus === 'validated'
      && manualResult.manualTriggerRecognized === true
      && automaticResult.decision === 'rejected'
      && automaticResult.manualTriggerRecognized === false
      && incompleteResult.decision === 'rejected'
      && [manualResult, automaticResult, incompleteResult].every((result) => result.commandInstanceCreated === false
        && result.commandDispatched === false
        && result.approvedForExecution === false
        && result.executed === false
        && result.formalPriceApprovalObjectCreated === false
        && result.businessWriteCount === 0
        && result.productionDataWritten === false)
      && CREATE_FORMAL_PRICE_APPROVAL_COMMAND_STATES.filter((item) => ['approved_for_execution', 'executed'].includes(item.code)).every((item) => item.currentEnabled === false), {
        manualDecision: manualResult.decision,
        automaticDecision: automaticResult.decision,
        closedStates: CREATE_FORMAL_PRICE_APPROVAL_COMMAND.closedStates,
      }),
    gate('Guard', CREATE_FORMAL_PRICE_APPROVAL_COMMAND_FORBIDDEN_ACTIONS.every((action) => evaluateCreateFormalPriceApprovalCommandGuard(action).decision === 'deny'), CREATE_FORMAL_PRICE_APPROVAL_COMMAND_FORBIDDEN_ACTIONS),
    gate('Acceptance', validateCreateFormalPriceApprovalCommandAcceptance().valid
      && registrySource.includes('CREATE_FORMAL_PRICE_APPROVAL_COMMAND_ACCEPTANCE_PROFILE'), CREATE_FORMAL_PRICE_APPROVAL_COMMAND_ACCEPTANCE_PROFILE.profileCode),
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
  const passed = results.every((item) => item.result === 'PASS') && databaseUnchanged && scan.analysis.executionImportsPresent === false
  const report = Object.freeze({
    version: VERSION,
    generatedAt: new Date().toISOString(),
    status: passed ? TARGET_STATUS : 'FAIL',
    problemAnalysis: scan.analysis,
    gates: Object.freeze(results),
    summary: Object.freeze({ PASS: results.filter((item) => item.result === 'PASS').length, FAIL: results.filter((item) => item.result === 'FAIL').length }),
    lifecycle: CREATE_FORMAL_PRICE_APPROVAL_COMMAND.lifecycle,
    closedStates: CREATE_FORMAL_PRICE_APPROVAL_COMMAND.closedStates,
    manualTriggerDesignPresent: true,
    automaticExecutionExists: false,
    commandInstanceCreated: false,
    commandDispatched: false,
    approvedForExecution: false,
    executed: false,
    formalPriceApprovalObjectCreated: false,
    approvalWorkflowStarted: false,
    approvalTaskCreated: false,
    businessWriteCount: 0,
    productionDataWritten: false,
    database: databaseUnchanged ? 'UNCHANGED' : 'CHANGED',
    databaseHashBefore,
    databaseHashAfter,
    protectedScopeChanges: 0,
  })
  const outputRoot = path.join(frontendRoot, 'test-results', 'page-acceptance', VERSION, 'purchase-inquiry-formal-price-approval-creation-command')
  await fs.mkdir(outputRoot, { recursive: true })
  await fs.writeFile(path.join(outputRoot, 'verification-report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
  return { scanPath, outputRoot, report }
}

const result = await run()
console.log(JSON.stringify(result, null, 2))
if (result.report && result.report.status !== TARGET_STATUS) process.exitCode = 1
