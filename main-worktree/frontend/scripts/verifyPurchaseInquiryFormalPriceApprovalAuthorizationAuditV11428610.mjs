import fs from 'node:fs/promises'
import path from 'node:path'
import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { PURCHASE_INQUIRY_RUNTIME } from '../src/meta/runtime/purchaseInquiryRuntime.js'
import { FORMAL_PRICE_APPROVAL_CREATION_AUTHORIZATION, validateFormalPriceApprovalCreationAuthorization } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalCreationAuthorizationModel.js'
import { FORMAL_PRICE_APPROVAL_CREATION_AUDIT_TRAIL, buildFormalPriceApprovalCreationAuditTrail, validateFormalPriceApprovalCreationAuditTrail } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalCreationAuditTrailModel.js'
import { evaluateFormalPriceApprovalCreationAuthorization } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalCreationAuthorizationRuleEngine.js'
import { FORMAL_PRICE_APPROVAL_CREATION_AUTHORIZATION_FORBIDDEN_ACTIONS, evaluateFormalPriceApprovalCreationAuthorizationGuard } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalCreationAuthorizationGuard.js'
import { FORMAL_PRICE_APPROVAL_CREATION_AUTHORIZATION_AUDIT_ACCEPTANCE_PROFILE, validateFormalPriceApprovalCreationAuthorizationAuditAcceptance } from '../src/meta/acceptance/scm/formalPriceApprovalCreationAuthorizationAuditAcceptanceProfile.js'

const VERSION = 'V1.14.2.8.6.10'
const TARGET_STATUS = 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_AUTHORIZATION_AUDIT_READY'
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
  try { await walk(root) } catch { /* missing root is reported as an empty inventory */ }
  return files.sort()
}

async function createScan() {
  const [domainFiles, runtimeFiles, schemaFiles, acceptanceFiles, authorizationSource, auditSource] = await Promise.all([
    listFiles('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject'),
    listFiles('src/meta/runtime'),
    listFiles('src/meta/schema/scm'),
    listFiles('src/meta/acceptance/scm'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalCreationAuthorizationModel.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalCreationAuditTrailModel.js'),
  ])
  const executionOrPersistenceImports = /dataGateway|transactionEngine|workflowEngine|commandDispatcher|fetch\s*\(/i.test(`${authorizationSource}\n${auditSource}`)
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
      authorizationModelPresent: domainFiles.includes('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalCreationAuthorizationModel.js'),
      auditTrailModelPresent: domainFiles.includes('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalCreationAuditTrailModel.js') }),
    analysis: Object.freeze({
      prerequisite: 'SCM_CREATE_FORMAL_PRICE_APPROVAL_COMMAND',
      designTargets: Object.freeze([FORMAL_PRICE_APPROVAL_CREATION_AUTHORIZATION.authorizationCode, FORMAL_PRICE_APPROVAL_CREATION_AUDIT_TRAIL.auditCode]),
      requesterAuthorizerSeparationRequired: true,
      authorizationIsExecution: false,
      auditIsPersistence: false,
      executionOrPersistenceImports,
      strategy: 'segregated design-only authorization plus immutable non-persistent audit description',
    }),
    protectedScopes: Object.freeze(['Formal Price Approval object instances', 'Approval Workflow', 'Command execution', 'Audit persistence', 'Database']),
  })
}

async function run() {
  const scan = await createScan()
  const scanPath = path.join(frontendRoot, 'scm_purchase_inquiry_formal_price_approval_authorization_audit_scan_v11428610.json')
  await fs.writeFile(scanPath, `${JSON.stringify(scan, null, 2)}\n`, 'utf8')
  if (process.argv.includes('--scan-only')) return { scanPath, scan }

  const databasePath = path.join(workspaceRoot, 'backend', 'db.sqlite3')
  const databaseHashBefore = await hashFile(databasePath)
  const [pageSource, routerSource, registrySource] = await Promise.all([
    read('src/meta/pages/ScmPurchaseInquiryWorkbenchPage.vue'),
    read('src/router/index.js'),
    read('src/meta/acceptance/registry/enterpriseAcceptanceRegistry.js'),
  ])
  const separatedAuthorization = evaluateFormalPriceApprovalCreationAuthorization({
    commandStatus: 'validated', requesterId: 'requester-a', authorizerId: 'authorizer-b', authorizationMode: 'manual',
  })
  const samePersonAuthorization = evaluateFormalPriceApprovalCreationAuthorization({
    commandStatus: 'validated', requesterId: 'same-user', authorizerId: 'same-user', authorizationMode: 'manual',
  })
  const automaticAuthorization = evaluateFormalPriceApprovalCreationAuthorization({
    commandStatus: 'validated', requesterId: 'requester-a', authorizerId: 'authorizer-b', authorizationMode: 'automatic',
  })
  const auditTrail = buildFormalPriceApprovalCreationAuditTrail([
    { eventType: 'command_evaluated', actorId: 'requester-a', occurredAt: '2026-08-03T00:00:00.000Z', outcome: 'validated', reason: 'design_check' },
    { eventType: 'authorization_evaluated', actorId: 'authorizer-b', occurredAt: '2026-08-03T00:01:00.000Z', outcome: 'authorized_design_only', reason: 'segregation_passed' },
    { eventType: 'execution_blocked', actorId: 'guard', occurredAt: '2026-08-03T00:01:01.000Z', outcome: 'blocked', reason: 'authorization_is_not_execution' },
  ])
  const results = [
    gate('Page', pageSource.includes('data-acceptance-id="formal-price-approval-creation-authorization-audit"')
      && pageSource.includes('创建授权与审计轨迹设计')
      && pageSource.includes('Requester ≠ Authorizer')
      && pageSource.includes('Authorization ≠ Execution')
      && pageSource.includes('Audit ≠ Persistence'), FORMAL_PRICE_APPROVAL_CREATION_AUTHORIZATION_AUDIT_ACCEPTANCE_PROFILE.requiredRegions),
    gate('Router', routerSource.includes("path: 'scm/purchase-inquiry'") && routerSource.includes('ScmPurchaseInquiryWorkbenchPage.vue'), '/scm/purchase-inquiry'),
    gate('Schema', validateFormalPriceApprovalCreationAuthorization().valid
      && validateFormalPriceApprovalCreationAuditTrail().valid
      && routerSource.includes("schema: 'PriceApprovalSchema'")
      && FORMAL_PRICE_APPROVAL_CREATION_AUTHORIZATION.persistenceMode === 'none'
      && FORMAL_PRICE_APPROVAL_CREATION_AUDIT_TRAIL.persistenceMode === 'none', {
        authorizationFields: FORMAL_PRICE_APPROVAL_CREATION_AUTHORIZATION.fields,
        auditFields: FORMAL_PRICE_APPROVAL_CREATION_AUDIT_TRAIL.fields,
        persistenceSchemaAdded: false,
      }),
    gate('Runtime', PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalCreationAuthorizationCode === FORMAL_PRICE_APPROVAL_CREATION_AUTHORIZATION.authorizationCode
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalCreationAuthorizationExecutionPermission === false
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalCreationAuditCode === FORMAL_PRICE_APPROVAL_CREATION_AUDIT_TRAIL.auditCode
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalCreationAuditPersistenceMode === 'none'
      && FORMAL_PRICE_APPROVAL_CREATION_AUTHORIZATION.authorizationInstanceCount === 0
      && auditTrail.entryCount === 3
      && auditTrail.businessObject === false
      && auditTrail.persisted === false
      && auditTrail.auditRecordWritten === false
      && auditTrail.businessWriteCount === 0, {
        authorizationCode: FORMAL_PRICE_APPROVAL_CREATION_AUTHORIZATION.authorizationCode,
        auditCode: FORMAL_PRICE_APPROVAL_CREATION_AUDIT_TRAIL.auditCode,
        auditEntryCount: auditTrail.entryCount,
        executionPermissionGranted: false,
        auditPersisted: false,
      }),
    gate('Rule', separatedAuthorization.decision === 'authorized_design_only'
      && separatedAuthorization.requesterAuthorizerSeparated === true
      && samePersonAuthorization.decision === 'rejected'
      && samePersonAuthorization.requesterAuthorizerSeparated === false
      && automaticAuthorization.decision === 'rejected'
      && [separatedAuthorization, samePersonAuthorization, automaticAuthorization].every((result) => result.authorizationInstanceCreated === false
        && result.executionPermissionGranted === false
        && result.commandExecuted === false
        && result.formalPriceApprovalObjectCreated === false
        && result.businessWriteCount === 0
        && result.productionDataWritten === false), {
        separatedDecision: separatedAuthorization.decision,
        samePersonDecision: samePersonAuthorization.decision,
        automaticDecision: automaticAuthorization.decision,
      }),
    gate('Guard', evaluateFormalPriceApprovalCreationAuthorizationGuard({ action: 'reviewAuthorization', requesterId: 'requester-a', authorizerId: 'authorizer-b' }).decision === 'allow_design_review'
      && evaluateFormalPriceApprovalCreationAuthorizationGuard({ action: 'reviewAuthorization', requesterId: 'same-user', authorizerId: 'same-user' }).decision === 'deny'
      && FORMAL_PRICE_APPROVAL_CREATION_AUTHORIZATION_FORBIDDEN_ACTIONS.every((action) => evaluateFormalPriceApprovalCreationAuthorizationGuard({ action }).decision === 'deny'), FORMAL_PRICE_APPROVAL_CREATION_AUTHORIZATION_FORBIDDEN_ACTIONS),
    gate('Acceptance', validateFormalPriceApprovalCreationAuthorizationAuditAcceptance().valid
      && registrySource.includes('FORMAL_PRICE_APPROVAL_CREATION_AUTHORIZATION_AUDIT_ACCEPTANCE_PROFILE'), FORMAL_PRICE_APPROVAL_CREATION_AUTHORIZATION_AUDIT_ACCEPTANCE_PROFILE.profileCode),
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
  const passed = results.every((item) => item.result === 'PASS') && databaseUnchanged && scan.analysis.executionOrPersistenceImports === false
  const report = Object.freeze({
    version: VERSION,
    generatedAt: new Date().toISOString(),
    status: passed ? TARGET_STATUS : 'FAIL',
    problemAnalysis: scan.analysis,
    gates: Object.freeze(results),
    summary: Object.freeze({ PASS: results.filter((item) => item.result === 'PASS').length, FAIL: results.filter((item) => item.result === 'FAIL').length }),
    requesterEqualsAuthorizerAllowed: false,
    authorizationIsExecution: false,
    executionPermissionGranted: false,
    auditIsPersistence: false,
    auditTrailPersisted: false,
    auditRecordWritten: false,
    authorizationInstanceCreated: false,
    formalPriceApprovalObjectCreated: false,
    approvalWorkflowStarted: false,
    businessWriteCount: 0,
    productionDataWritten: false,
    database: databaseUnchanged ? 'UNCHANGED' : 'CHANGED',
    databaseHashBefore,
    databaseHashAfter,
    protectedScopeChanges: 0,
  })
  const outputRoot = path.join(frontendRoot, 'test-results', 'page-acceptance', VERSION, 'purchase-inquiry-formal-price-approval-authorization-audit')
  await fs.mkdir(outputRoot, { recursive: true })
  await fs.writeFile(path.join(outputRoot, 'verification-report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
  return { scanPath, outputRoot, report }
}

const result = await run()
console.log(JSON.stringify(result, null, 2))
if (result.report && result.report.status !== TARGET_STATUS) process.exitCode = 1
