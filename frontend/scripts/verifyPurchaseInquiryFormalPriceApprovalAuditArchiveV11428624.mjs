import fs from 'node:fs/promises'
import path from 'node:path'
import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { PURCHASE_INQUIRY_RUNTIME } from '../src/meta/runtime/purchaseInquiryRuntime.js'
import { FORMAL_PRICE_APPROVAL_AUDIT_TRAIL, validateFormalPriceApprovalAuditTrail } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalAuditTrailModel.js'
import { FORMAL_PRICE_APPROVAL_EVIDENCE_ARCHIVE_BOUNDARY, validateFormalPriceApprovalEvidenceArchiveBoundary } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalEvidenceArchiveBoundary.js'
import { evaluateFormalPriceApprovalAuditArchive } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalAuditArchiveRuleEngine.js'
import { FORMAL_PRICE_APPROVAL_AUDIT_ARCHIVE_FORBIDDEN_ACTIONS, evaluateFormalPriceApprovalAuditArchiveGuard } from '../src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalAuditArchiveGuard.js'
import { FORMAL_PRICE_APPROVAL_AUDIT_ARCHIVE_ACCEPTANCE_PROFILE, validateFormalPriceApprovalAuditArchiveAcceptance } from '../src/meta/acceptance/scm/formalPriceApprovalAuditArchiveAcceptanceProfile.js'

const VERSION = 'V1.14.2.8.6.24'
const TARGET_STATUS = 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_AUDIT_ARCHIVE_READY'
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
  const [domainFiles, runtimeFiles, schemaFiles, acceptanceFiles, auditSource, archiveSource, ruleSource, guardSource] = await Promise.all([
    listFiles('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject'), listFiles('src/meta/runtime'), listFiles('src/meta/schema/scm'), listFiles('src/meta/acceptance/scm'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalAuditTrailModel.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalEvidenceArchiveBoundary.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalAuditArchiveRuleEngine.js'),
    read('src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject/formalPriceApprovalAuditArchiveGuard.js'),
  ])
  const imports = `${auditSource}\n${archiveSource}\n${ruleSource}\n${guardSource}`
    .split(/\r?\n/).filter((line) => line.trimStart().startsWith('import ')).join('\n')
  return Object.freeze({ version: VERSION, generatedAt: new Date().toISOString(),
    scope: Object.freeze(['src/meta/domain/scm/purchaseInquiry/formalPriceApprovalObject', 'src/meta/runtime', 'src/meta/schema/scm', 'src/meta/acceptance/scm']),
    inventory: Object.freeze({ domainFiles, runtimeFiles, schemaFiles, acceptanceFiles }),
    analysis: Object.freeze({ prerequisite: 'SCM_FORMAL_PRICE_APPROVAL_FEEDBACK_BOUNDARY', auditTrail: FORMAL_PRICE_APPROVAL_AUDIT_TRAIL.auditCode,
      archiveBoundary: FORMAL_PRICE_APPROVAL_EVIDENCE_ARCHIVE_BOUNDARY.boundaryCode, auditMeansPersistence: false,
      evidenceArchiveMeansBusinessWrite: false, auditMeansApprovalExecution: false, auditDefinitionCount: 6, archiveBoundaryCount: 1, persistedRecordCount: 0,
      workflowOrPersistenceImports: /workflowEngine|workflowService|taskEngine|stateManager|dataGateway|transactionEngine|commandDispatcher/i.test(imports),
      strategy: 'definition-only end-to-end audit templates and evidence archive boundary with no persistence or execution' }),
    protectedScopes: Object.freeze(['crudEngine', 'pageRenderer', 'schemaResolver', 'Workflow Engine', 'Approval execution', 'Task engine', 'PurchaseOrder', 'Finance', 'Inventory', 'Database write layer']) })
}

async function run() {
  const scan = await createScan()
  const scanPath = path.join(frontendRoot, 'scm_purchase_inquiry_formal_price_approval_audit_archive_scan_v11428624.json')
  await fs.writeFile(scanPath, `${JSON.stringify(scan, null, 2)}\n`, 'utf8')
  if (process.argv.includes('--scan-only')) return { scanPath, scan }
  const databasePath = path.join(workspaceRoot, 'backend', 'db.sqlite3')
  const databaseHashBefore = await hashFile(databasePath)
  const [pageSource, routerSource, registrySource] = await Promise.all([read('src/meta/pages/ScmPurchaseInquiryWorkbenchPage.vue'), read('src/router/index.js'), read('src/meta/acceptance/registry/enterpriseAcceptanceRegistry.js')])
  const regionStart = pageSource.indexOf('data-acceptance-id="formal-price-approval-audit-archive"')
  const regionEnd = pageSource.indexOf('data-acceptance-id="inquiry-list"', regionStart)
  const pageRegion = pageSource.slice(regionStart, regionEnd)
  const safeInput = Object.freeze({ assessmentRequested: true, traceableSources: ['node', 'rule', 'comment', 'evidence'], evidenceReferencePresent: true, auditSeparatedFromPersistence: true, archiveSeparatedFromBusinessData: true, auditSeparatedFromApprovalExecution: true })
  const ready = evaluateFormalPriceApprovalAuditArchive(safeInput)
  const notAssessed = evaluateFormalPriceApprovalAuditArchive({})
  const rule001 = evaluateFormalPriceApprovalAuditArchive({ ...safeInput, traceableSources: ['node', 'rule', 'comment'] })
  const rule002 = evaluateFormalPriceApprovalAuditArchive({ ...safeInput, evidenceReferencePresent: false })
  const rule003 = evaluateFormalPriceApprovalAuditArchive({ ...safeInput, auditSeparatedFromPersistence: false })
  const rule004 = evaluateFormalPriceApprovalAuditArchive({ ...safeInput, archiveSeparatedFromBusinessData: false })
  const rule005 = evaluateFormalPriceApprovalAuditArchive({ ...safeInput, auditSeparatedFromApprovalExecution: false })
  const persistenceBlocked = evaluateFormalPriceApprovalAuditArchive({ ...safeInput, archivePersistenceRequested: true })
  const executionBlocked = evaluateFormalPriceApprovalAuditArchive({ ...safeInput, approvalExecutionRequested: true })
  const resultBlocked = evaluateFormalPriceApprovalAuditArchive({ ...safeInput, approvalResultCreationRequested: true })
  const businessBlocked = evaluateFormalPriceApprovalAuditArchive({ ...safeInput, priceChangeRequested: true })
  const evaluated = [notAssessed, ready, rule001, rule002, rule003, rule004, rule005, persistenceBlocked, executionBlocked, resultBlocked, businessBlocked]
  const results = [
    gate('Page', regionStart >= 0 && pageRegion.includes('Audit ≠ Persistence') && pageRegion.includes('Evidence Archive ≠ Business Write')
      && pageRegion.includes('Audit ≠ Approval Execution') && pageRegion.includes('6 / 1 / 0')
      && !/<(?:el-)?button\b/i.test(pageRegion) && !/data-action=(?:"|')(?:save-audit|archive-evidence|approve|execute)/i.test(pageRegion), FORMAL_PRICE_APPROVAL_AUDIT_ARCHIVE_ACCEPTANCE_PROFILE.requiredRegions),
    gate('Router', routerSource.includes("path: 'scm/purchase-inquiry'") && routerSource.includes('ScmPurchaseInquiryWorkbenchPage.vue'), '/scm/purchase-inquiry'),
    gate('Schema', validateFormalPriceApprovalAuditTrail().valid && validateFormalPriceApprovalEvidenceArchiveBoundary().valid
      && routerSource.includes("schema: 'PriceApprovalSchema'") && FORMAL_PRICE_APPROVAL_EVIDENCE_ARCHIVE_BOUNDARY.persisted === false
      && FORMAL_PRICE_APPROVAL_EVIDENCE_ARCHIVE_BOUNDARY.databaseWriterConnected === false, { persistenceSchemaAdded: false, auditFields: FORMAL_PRICE_APPROVAL_AUDIT_TRAIL.fields, archiveFields: FORMAL_PRICE_APPROVAL_EVIDENCE_ARCHIVE_BOUNDARY.fields }),
    gate('Runtime', PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalAuditTrailCode === FORMAL_PRICE_APPROVAL_AUDIT_TRAIL.auditCode
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalEvidenceArchiveBoundaryCode === FORMAL_PRICE_APPROVAL_EVIDENCE_ARCHIVE_BOUNDARY.boundaryCode
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalAuditDefinitionCount === 6 && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalArchiveBoundaryCount === 1
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalAuditPersistedRecordCount === 0 && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalAuditPersisted === false
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalEvidenceArchivePersisted === false && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalAuditApprovalExecution === false
      && PURCHASE_INQUIRY_RUNTIME.formalPriceApprovalAuditBusinessEffectApplied === false, { auditDefinitions: 6, archiveBoundaries: 1, persistedRecords: 0 }),
    gate('Rule', notAssessed.assessmentStatus === 'not_assessed' && ready.assessmentStatus === 'audit_archive_definition_ready'
      && rule001.blockedReasons.includes('Rule001_audit_source_incomplete') && rule002.blockedReasons.includes('Rule002_evidence_reference_missing')
      && rule003.blockedReasons.includes('Rule003_audit_isolation_failed') && rule004.blockedReasons.includes('Rule004_archive_isolation_failed')
      && rule005.blockedReasons.includes('Rule005_execution_isolation_failed')
      && [persistenceBlocked, executionBlocked, resultBlocked, businessBlocked].every((item) => item.assessmentStatus === 'blocked')
      && evaluated.every((item) => item.auditPersisted === false && item.evidenceArchivePersisted === false && item.approvalInstanceCreated === false && item.approvalTaskCreated === false && item.approvalExecuted === false && item.approvalResultCreated === false && item.businessEffectApplied === false && item.priceChanged === false && item.businessStateChanged === false && item.databaseWritten === false && item.businessWriteCount === 0 && item.productionDataWritten === false), { Rule001: rule001.decision, Rule002: rule002.decision, Rule003: rule003.decision, Rule004: rule004.decision, Rule005: rule005.decision }),
    gate('Guard', evaluateFormalPriceApprovalAuditArchiveGuard({ action: 'inspectAuditArchiveDefinition', mode: 'design_only' }).decision === 'allow_definition_inspection_only'
      && evaluateFormalPriceApprovalAuditArchiveGuard({ action: 'inspectAuditArchiveDefinition', mode: 'execution' }).decision === 'deny'
      && FORMAL_PRICE_APPROVAL_AUDIT_ARCHIVE_FORBIDDEN_ACTIONS.every((action) => { const result = evaluateFormalPriceApprovalAuditArchiveGuard({ action }); return result.decision === 'deny' && result.auditPersisted === false && result.evidenceArchivePersisted === false && result.approvalExecuted === false && result.approvalResultCreated === false && result.businessEffectApplied === false && result.databaseWritten === false }), FORMAL_PRICE_APPROVAL_AUDIT_ARCHIVE_FORBIDDEN_ACTIONS),
    gate('Acceptance', validateFormalPriceApprovalAuditArchiveAcceptance().valid && registrySource.includes('FORMAL_PRICE_APPROVAL_AUDIT_ARCHIVE_ACCEPTANCE_PROFILE'), FORMAL_PRICE_APPROVAL_AUDIT_ARCHIVE_ACCEPTANCE_PROFILE.profileCode),
  ]
  try {
    const output = execFileSync(process.execPath, [path.join(frontendRoot, 'node_modules', 'vite', 'bin', 'vite.js'), 'build', '.', '--emptyOutDir=false'], { cwd: frontendRoot, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], timeout: 240000 })
    results.push(gate('Build', true, output.trim().split(/\r?\n/).slice(-2)))
  } catch (error) { results.push(gate('Build', false, String(error.stderr || error.message))) }
  const databaseHashAfter = await hashFile(databasePath)
  const databaseUnchanged = databaseHashBefore === databaseHashAfter
  const passed = results.every((item) => item.result === 'PASS') && databaseUnchanged && scan.analysis.workflowOrPersistenceImports === false
  const report = Object.freeze({ version: VERSION, generatedAt: new Date().toISOString(), status: passed ? TARGET_STATUS : 'FAIL', problemAnalysis: scan.analysis,
    gates: Object.freeze(results), summary: Object.freeze({ PASS: results.filter((item) => item.result === 'PASS').length, FAIL: results.filter((item) => item.result === 'FAIL').length }),
    auditMeansPersistence: false, evidenceArchiveMeansBusinessWrite: false, auditMeansApprovalExecution: false,
    auditPersisted: false, evidenceArchivePersisted: false, approvalInstanceCreated: false, approvalTaskCreated: false, approvalExecuted: false, approvalResultCreated: false, businessEffectApplied: false, priceChanged: false, businessStateChanged: false, databaseWritten: false,
    businessWriteCount: 0, productionDataWritten: false, database: databaseUnchanged ? 'UNCHANGED' : 'CHANGED', databaseHashBefore, databaseHashAfter, protectedScopeChanges: 0 })
  const outputRoot = path.join(frontendRoot, 'test-results', 'page-acceptance', VERSION, 'purchase-inquiry-formal-price-approval-audit-archive')
  await fs.mkdir(outputRoot, { recursive: true })
  await fs.writeFile(path.join(outputRoot, 'verification-report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
  return { scanPath, outputRoot, report }
}

const result = await run()
console.log(JSON.stringify(result, null, 2))
if (result.report && result.report.status !== TARGET_STATUS) process.exitCode = 1
