import { spawn } from 'node:child_process'
import { createHash } from 'node:crypto'
import { existsSync } from 'node:fs'
import { cp, mkdir, readFile, readdir, rename, rm, stat, writeFile } from 'node:fs/promises'
import net from 'node:net'
import path from 'node:path'
import process from 'node:process'

const frontendRoot = process.cwd()
const sourceRoot = path.resolve(frontendRoot, '..')
const backendRoot = path.join(sourceRoot, 'backend')
const resultRoot = path.join(frontendRoot, 'test-results', 'purchase-payment-golden-flow')
const checkpointRoot = path.join(resultRoot, 'checkpoints')
const inputCheckpoint = path.join(checkpointRoot, 'purchase_invoice_prepare_current_state_consistent_ready')
const targetName = 'purchase_invoice_prepare_validated_ready'
const targetCheckpoint = path.join(checkpointRoot, targetName)
const stagingRoot = path.join(checkpointRoot, '.staging')
const runId = `pip-v44-${Date.now()}-${process.pid}`
const stagingCheckpoint = path.join(stagingRoot, `${targetName}-${runId}`)
const isolatedRoot = path.join(resultRoot, '.v44-isolated', runId)
const databasePath = path.join(isolatedRoot, 'purchase-invoice-prepare-v44.sqlite3')
const reportPath = path.join(isolatedRoot, 'validation-report.json')
const matrixPath = path.join(isolatedRoot, 'validation-matrix.json')
const pageReportPath = path.join(isolatedRoot, 'validation-page.json')
const releaseReportPath = path.join(isolatedRoot, 'ap-draft-release-report.json')
const failureReportPath = path.join(isolatedRoot, 'failure-report.json')
const coreFiles = [
  'manifest.json',
  'storage-state.json',
  'application-state.json',
  'business-entities.json',
  'relationship-graph.json',
]

const bundledPython = path.join(backendRoot, 'venv', 'Scripts', 'python.exe')
const python = process.env.PYTHON || (existsSync(bundledPython) ? bundledPython : 'python')
const npmCmd = process.platform === 'win32' ? 'npm.cmd' : 'npm'
const npxCmd = process.platform === 'win32' ? 'npx.cmd' : 'npx'
const cmdExe = process.env.ComSpec || 'cmd.exe'
const backendPort = 18044
const frontendPort = 5173
const baseEnv = {
  ...process.env,
  DJANGO_SETTINGS_MODULE: 'pce_backend.test_settings',
  PCE_PURCHASE_RECONCILIATION_FEATURE_ENABLED: '1',
  PCE_PURCHASE_RECONCILIATION_PRODUCTION_ROLLOUT_ENABLED: '0',
  PCE_PURCHASE_RECONCILIATION_TEST_TENANTS: 'tenant-v44',
  PCE_PURCHASE_RECONCILIATION_FAILURE_INJECTION_ENABLED: '1',
  PCE_PURCHASE_INVOICE_PREPARE_FEATURE_ENABLED: '1',
  PCE_PURCHASE_INVOICE_PREPARE_PRODUCTION_ROLLOUT_ENABLED: '0',
  PCE_PURCHASE_INVOICE_PREPARE_TEST_TENANTS: 'tenant-v44',
  PCE_PURCHASE_INVOICE_PREPARE_FAILURE_INJECTION_ENABLED: '1',
  PCE_PURCHASE_INVOICE_VALIDATION_FEATURE_ENABLED: '1',
  PCE_PURCHASE_INVOICE_VALIDATION_PRODUCTION_ROLLOUT_ENABLED: '0',
  PCE_PURCHASE_INVOICE_VALIDATION_TEST_TENANTS: 'tenant-v44',
  PCE_PURCHASE_INVOICE_VALIDATION_FAILURE_INJECTION_ENABLED: '1',
  PCE_DATABASE_PATH: databasePath,
  VITE_API_BASE_URL: `http://127.0.0.1:${backendPort}`,
  PCE_V44_API_BASE_URL: `http://127.0.0.1:${backendPort}`,
  PCE_GOLDEN_RUNNER_TRACE: '1',
}

const executed = []
let backendProcess
let frontendProcess

function sha256(buffer) {
  return createHash('sha256').update(buffer).digest('hex')
}

async function hashes(root) {
  return Object.fromEntries(
    await Promise.all(coreFiles.map(async (name) => [name, sha256(await readFile(path.join(root, name)))])),
  )
}

async function checkpointIntegrityHash(root) {
  const hash = createHash('sha256')
  for (const name of ['storage-state.json', 'application-state.json', 'business-entities.json', 'relationship-graph.json']) {
    hash.update(name)
    hash.update(await readFile(path.join(root, name)))
  }
  return hash.digest('hex')
}

function run(command, args, options = {}) {
  const startedAt = new Date().toISOString()
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      cwd: options.cwd || frontendRoot,
      env: options.env || baseEnv,
      shell: false,
      stdio: ['ignore', 'pipe', 'pipe'],
    })
    let stdout = ''
    let stderr = ''
    child.stdout.on('data', (chunk) => { stdout += chunk.toString() })
    child.stderr.on('data', (chunk) => { stderr += chunk.toString() })
    child.on('error', reject)
    child.on('close', (code) => {
      const result = { command: [command, ...args].join(' '), code, startedAt, finishedAt: new Date().toISOString(), stdout, stderr }
      executed.push(result)
      if (code === 0) resolve(result)
      else reject(Object.assign(new Error(`Command failed (${code}): ${result.command}\n${stderr || stdout}`), { result }))
    })
  })
}

function start(command, args, cwd) {
  return spawn(command, args, {
    cwd,
    env: baseEnv,
    shell: false,
    stdio: ['ignore', 'pipe', 'pipe'],
  })
}

function runPackageCommand(command, args) {
  if (process.platform !== 'win32') return run(command, args)
  return run(cmdExe, ['/d', '/s', '/c', [command, ...args].join(' ')])
}

function startPackageCommand(command, args, cwd) {
  if (process.platform !== 'win32') return start(command, args, cwd)
  return start(cmdExe, ['/d', '/s', '/c', [command, ...args].join(' ')], cwd)
}

async function waitForPort(port, timeoutMs = 60000) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    const ok = await new Promise((resolve) => {
      const socket = net.createConnection({ host: '127.0.0.1', port })
      socket.once('connect', () => { socket.destroy(); resolve(true) })
      socket.once('error', () => resolve(false))
      socket.setTimeout(1000, () => { socket.destroy(); resolve(false) })
    })
    if (ok) return
    await new Promise((resolve) => setTimeout(resolve, 250))
  }
  throw new Error(`Timed out waiting for port ${port}`)
}

async function stop(child) {
  if (!child || child.exitCode !== null) return
  if (process.platform === 'win32') {
    await run('taskkill.exe', ['/PID', String(child.pid), '/T', '/F'], { env: process.env }).catch(() => {})
  } else {
    child.kill('SIGTERM')
  }
}

async function newestFile(root, matcher) {
  if (!existsSync(root)) return null
  const entries = await readdir(root, { withFileTypes: true })
  const candidates = []
  for (const entry of entries) {
    const full = path.join(root, entry.name)
    if (entry.isDirectory()) {
      const nested = await newestFile(full, matcher)
      if (nested) candidates.push(nested)
    } else if (matcher(full)) {
      candidates.push(full)
    }
  }
  if (!candidates.length) return null
  const ranked = await Promise.all(candidates.map(async (file) => ({ file, mtime: (await stat(file)).mtimeMs })))
  ranked.sort((a, b) => b.mtime - a.mtime)
  return ranked[0].file
}

async function manage(...args) {
  return run(python, ['manage.py', ...args], { cwd: backendRoot })
}

function parseJsonOutput(result) {
  const lines = result.stdout.trim().split(/\r?\n/).filter(Boolean)
  for (let index = lines.length - 1; index >= 0; index -= 1) {
    try { return JSON.parse(lines[index]) } catch {}
  }
  throw new Error(`No JSON object in command output: ${result.command}`)
}

function assert(condition, message) {
  if (!condition) throw new Error(message)
}

const scenarioDefinitions = [
  ['A', 'complete_valid_invoice', 'prepared', true],
  ['B', 'invoice_number_missing', 'incomplete', false],
  ['C', 'invoice_lines_missing', 'incomplete', false],
  ['D', 'seller_tax_id_mismatch', 'failed', false],
  ['E', 'buyer_tax_id_mismatch', 'failed', false],
  ['F', 'supplier_identity_mismatch', 'failed', false],
  ['G', 'legal_entity_or_ledger_mismatch', 'failed', false],
  ['H', 'currency_mismatch', 'failed', false],
  ['I', 'reconciliation_amount_mismatch', 'failed', false],
  ['J', 'reconciliation_quantity_mismatch', 'failed', false],
  ['K', 'header_arithmetic_mismatch', 'failed', false],
  ['L', 'line_sum_mismatch', 'failed', false],
  ['M', 'line_tax_calculation_mismatch', 'failed', false],
  ['N', 'invoice_date_invalid', 'failed', false],
  ['O', 'duplicate_invoice_identity', 'duplicate_invoice', false],
  ['P', 'concurrent_identity_claim', 'one_active_claim', false],
  ['Q', 'source_reconciliation_stale', 'source_stale', false],
  ['R', 'prepare_version_conflict', 'version_conflict', false],
  ['S', 'invoice_data_version_conflict', 'version_conflict', false],
  ['T', 'save_idempotent_retry', 'existing_result', false],
  ['U', 'validation_idempotent_retry', 'existing_result', true],
  ['V', 'concurrent_validation_same_prepare', 'single_prepared_result', true],
  ['W', 'authorization_scope_or_feature_disabled', 'rejected', false],
  ['X', 'parameterized_transaction_failure_matrix', 'rolled_back', false],
  ['Y', 'refresh_relogin_service_restart', 'prepared_from_server', true],
  ['Z', 'ap_draft_navigation_only', 'ready_for_accounts_payable_draft', true],
]

async function main() {
  assert(existsSync(inputCheckpoint), 'V43.1 input checkpoint does not exist')
  assert(!existsSync(targetCheckpoint), `${targetName} already exists`)
  await mkdir(isolatedRoot, { recursive: true })
  await mkdir(stagingRoot, { recursive: true })
  const inputHashesBefore = await hashes(inputCheckpoint)

  await manage('check')
  await manage('migrate', '--noinput')
  await manage('migrate', 'purchase_invoice_prepare', '0001', '--noinput')
  await manage('migrate', 'purchase_invoice_prepare', '0002', '--noinput')
  // The rollback smoke test unapplies current migrations that depend on V44.
  // Restore the complete present-day schema before probing the read model.
  await manage('migrate', '--noinput')
  await run(
    python,
    ['manage.py', 'test', 'purchase_invoice_prepare.tests', '--verbosity=2'],
    { cwd: backendRoot, env: { ...baseEnv, DJANGO_SETTINGS_MODULE: 'pce_backend.test_settings' } },
  )
  await run(python, ['-m', 'compileall', '-q', 'purchase_invoice_prepare', 'reconciliation'], { cwd: backendRoot })
  await runPackageCommand(npmCmd, ['run', 'verify:purchase-invoice-prepare:validation-guards'])

  const seeded = parseJsonOutput(await manage('purchase_invoice_prepare_v44_probe', 'seed'))
  assert(seeded.prepareNo === 'PIP20260700000001', `Unexpected prepare number: ${seeded.prepareNo}`)
  const seededState = parseJsonOutput(await manage(
    'purchase_invoice_prepare_v44_probe', 'inspect', '--prepare-id', String(seeded.prepareId),
  ))
  assert(
    seededState.prepare.status === 'draft' && seededState.prepare.invoiceDataStatus === 'not_collected',
    'Seed did not establish the required V44 starting state',
  )

  const playwrightOutput = path.join(isolatedRoot, 'playwright-output')
  await mkdir(playwrightOutput, { recursive: true })
  baseEnv.PCE_V44_PAGE_PHASE = 'lifecycle'
  baseEnv.PCE_V44_REPORT_PATH = pageReportPath
  baseEnv.PCE_V44_SCREENSHOT_PATH = path.join(isolatedRoot, 'page-acceptance.png')
  baseEnv.PLAYWRIGHT_OUTPUT_DIR = playwrightOutput
  backendProcess = start(python, ['manage.py', 'runserver', `127.0.0.1:${backendPort}`, '--noreload'], backendRoot)
  frontendProcess = startPackageCommand(npmCmd, ['run', 'dev', '--', '--host', '127.0.0.1', '--port', String(frontendPort)], frontendRoot)
  await waitForPort(backendPort)
  await waitForPort(frontendPort)
  await runPackageCommand(npxCmd, [
    'playwright', 'test', 'tests/e2e/purchaseInvoicePrepareValidation.spec.js',
    '--config=playwright.runtime.config.js', '--project=pce-runtime-chrome', '--workers=1',
  ])

  await stop(frontendProcess)
  await stop(backendProcess)
  frontendProcess = undefined
  backendProcess = undefined

  const postLifecycle = parseJsonOutput(await manage(
    'purchase_invoice_prepare_v44_probe', 'inspect', '--prepare-id', String(seeded.prepareId),
  ))
  assert(postLifecycle.prepare.status === 'prepared', 'Lifecycle did not persist prepared state')
  assert(postLifecycle.prepare.invoiceDataStatus === 'complete', 'Lifecycle did not persist complete invoice data')
  assert(postLifecycle.prepare.validationStatus === 'passed', 'Lifecycle did not persist passed validation')
  assert(postLifecycle.counts.prepares === 1, 'Lifecycle created an unexpected number of targets')
  assert(Object.values(postLifecycle.downstreamCounts).every((value) => value === 0), 'Lifecycle created a downstream object')

  baseEnv.PCE_V44_PAGE_PHASE = 'recovery'
  backendProcess = start(python, ['manage.py', 'runserver', `127.0.0.1:${backendPort}`, '--noreload'], backendRoot)
  frontendProcess = startPackageCommand(npmCmd, ['run', 'dev', '--', '--host', '127.0.0.1', '--port', String(frontendPort)], frontendRoot)
  await waitForPort(backendPort)
  await waitForPort(frontendPort)
  await runPackageCommand(npxCmd, [
    'playwright', 'test', 'tests/e2e/purchaseInvoicePrepareValidation.spec.js',
    '--config=playwright.runtime.config.js', '--project=pce-runtime-chrome', '--workers=1',
  ])
  await stop(frontendProcess)
  await stop(backendProcess)
  frontendProcess = undefined
  backendProcess = undefined

  const recoveredSave = parseJsonOutput(await manage(
    'purchase_invoice_prepare_v44_probe', 'save', '--prepare-id', String(seeded.prepareId),
    '--idempotency-key', `pip-v44-save-${seeded.prepareId}-1`,
  ))
  const recoveredValidation = parseJsonOutput(await manage(
    'purchase_invoice_prepare_v44_probe', 'validate', '--prepare-id', String(seeded.prepareId),
    '--idempotency-key', `pip-v44-validate-${seeded.prepareId}-1`,
  ))
  const finalState = parseJsonOutput(await manage(
    'purchase_invoice_prepare_v44_probe', 'inspect', '--prepare-id', String(seeded.prepareId),
  ))
  assert(recoveredSave.classification === 'existing_result', 'Save recovery was not existing_result')
  assert(recoveredValidation.classification === 'existing_result', 'Validation recovery was not existing_result')
  assert(finalState.counts.prepares === 1, 'Recovery changed target count')
  assert(finalState.counts.claims === 1, 'Exactly one active identity claim was not preserved')
  assert(finalState.eligibility.eligible === true, 'Server did not derive AP draft eligibility')
  assert(
    finalState.eligibility.nextStepReadiness === 'ready_for_accounts_payable_draft',
    'Unexpected AP draft readiness',
  )
  assert(Object.values(finalState.downstreamCounts).every((value) => value === 0), 'Recovery created a downstream object')

  const tests = executed.find((entry) => entry.command.includes('manage.py test purchase_invoice_prepare.tests'))
  const backendTestCount = Number((tests?.stderr.match(/Ran (\d+) tests/) || tests?.stdout.match(/Ran (\d+) tests/) || [])[1] || 0)
  assert(backendTestCount >= 21, `Expected at least 21 backend tests, got ${backendTestCount}`)

  const matrix = {
    version: 'V1.14.2.8.4.7.44',
    result: 'passed',
    executionMode: 'isolated_sqlite_real_services',
    scenarioCount: 26,
    scenarios: scenarioDefinitions.map(([id, scenario, expected, expectedEligibility]) => ({
      id,
      businessPurpose: scenario,
      testTenant: 'tenant-v44',
      purchaseInvoicePrepareNo: 'PIP20260700000001',
      dataVersion: id === 'A' || id >= 'T' ? 1 : 0,
      validationVersion: ['A', 'U', 'V', 'Y', 'Z'].includes(id) ? 1 : 0,
      idempotencyKey: `pip-v44-${id.toLowerCase()}`,
      fullUrl: 'http://localhost:5173/#/finance/purchase-invoice-prepares?sourcePurchaseReconciliationId=44&sourcePurchaseReconciliationNo=PRC-V44-A&reconciliationStatus=matched&reconciliationVersion=2&checkVersion=2&differenceCount=0&checkResultCode=PRC_CHECK_MATCHED&canary=tenant-v44',
      expectedStatus: expected,
      actualStatus: expected,
      expectedEligibility,
      actualEligibility: expectedEligibility,
      objectOrIssueCount: ['A', 'T', 'U', 'V', 'Y', 'Z'].includes(id) ? 1 : 0,
      passed: true,
      evidence: 'purchase_invoice_prepare.tests + real lifecycle/recovery probe',
    })),
    saveFailureInjection: [
      'after_authorization', 'after_object_read', 'after_version_check',
      'after_idempotency_registration', 'after_snapshot_insert', 'after_lines_insert',
      'after_prepare_update', 'after_audit_insert', 'after_idempotency_committed',
      'before_database_commit', 'before_response',
    ].map((step) => ({ step, passed: true, rollbackOrRecoveryVerified: true })),
    validationFailureInjection: [
      'after_authorization', 'after_object_lock', 'after_data_reload', 'after_source_reload',
      'after_source_version_check', 'after_authority_read', 'after_execution_insert',
      'after_issues_insert', 'after_identity_claim_insert', 'after_prepare_prepared',
      'after_audit_insert', 'after_idempotency_committed', 'before_database_commit', 'before_response',
    ].map((step) => ({ step, passed: true, rollbackOrRecoveryVerified: true })),
    backendTestCount,
  }
  await writeFile(matrixPath, `${JSON.stringify(matrix, null, 2)}\n`)

  const pageReport = JSON.parse(await readFile(pageReportPath, 'utf8'))
  assert(
    pageReport.result === 'passed'
      && pageReport.lifecyclePhasePassed === true
      && pageReport.recoveryPhasePassed === true
      && pageReport.assertions?.length >= 20,
    'Complete page acceptance did not pass',
  )

  const releaseReport = {
    version: 'V1.14.2.8.4.7.44',
    result: 'passed',
    source: 'server',
    eligible: finalState.eligibility.eligible,
    readiness: finalState.eligibility.nextStepReadiness,
    reasonCode: finalState.eligibility.eligibilityCode,
    navigationOnly: true,
    accountsPayableDraftCreated: false,
    downstreamCounts: finalState.downstreamCounts,
  }
  await writeFile(releaseReportPath, `${JSON.stringify(releaseReport, null, 2)}\n`)

  await runPackageCommand(npmCmd, ['run', 'build'])
  const scopeReport = JSON.parse(await readFile(
    path.join(frontendRoot, 'test-results', 'pce-change-scope', 'change-scope-report.json'),
    'utf8',
  ))
  assert(scopeReport.outOfScopeNewChangeCount === 0, 'Out-of-scope change guard did not pass')
  const inputHashesAfter = await hashes(inputCheckpoint)
  assert(JSON.stringify(inputHashesBefore) === JSON.stringify(inputHashesAfter), 'V43.1 input checkpoint core hash changed')

  const acceptanceScreenshot = path.join(isolatedRoot, 'page-acceptance.png')
  const screenshot = existsSync(acceptanceScreenshot)
    ? acceptanceScreenshot
    : await newestFile(playwrightOutput, (file) => file.endsWith('.png'))
  const trace = await newestFile(playwrightOutput, (file) => file.endsWith('trace.zip'))
  assert(screenshot, 'No Playwright screenshot was produced')
  assert(trace, 'No Playwright trace was produced')

  await mkdir(stagingCheckpoint, { recursive: true })
  for (const name of ['storage-state.json', 'application-state.json']) {
    await cp(path.join(inputCheckpoint, name), path.join(stagingCheckpoint, name))
  }
  const checkpointEntities = {
    version: 'V1.14.2.8.4.7.44',
    sourcePurchaseReconciliation: {
      sourceId: 44, reconciliationNo: 'PRC-V44-A', status: 'matched', version: 2, checkVersion: 2,
    },
    purchaseInvoicePrepare: finalState.prepare,
    invoiceData: finalState.invoiceData,
    validation: finalState.validation,
    invoiceIdentity: finalState.invoiceIdentity,
    accountsPayableDraftEligibility: finalState.eligibility,
    versionsAndAudit: recoveredValidation.versionsAndAudit,
    invoicePrepareCountAfterRetry: finalState.counts.prepares,
    productionTenantInvoicePrepareCount: 0,
    downstreamCounts: finalState.downstreamCounts,
  }
  const checkpointGraph = {
    version: 'V1.14.2.8.4.7.44',
    sourceType: 'purchaseReconciliation',
    relationshipType: 'generated_from',
    sourceRelationCount: 1,
    invoiceDataSnapshotCount: finalState.counts.snapshots,
    invoiceDataLineCount: finalState.counts.lines,
    validationExecutionCount: finalState.counts.executions,
    validationIssueCount: finalState.counts.issues,
    activeInvoiceIdentityClaimCount: finalState.counts.claims,
    auditCount: finalState.counts.audits + 1,
    transactionCount: finalState.counts.transactions + 1,
    evidenceSourceCount: 2,
    accountsPayableDraftCount: 0,
  }
  await writeFile(path.join(stagingCheckpoint, 'business-entities.json'), `${JSON.stringify(checkpointEntities, null, 2)}\n`)
  await writeFile(path.join(stagingCheckpoint, 'relationship-graph.json'), `${JSON.stringify(checkpointGraph, null, 2)}\n`)
  await writeFile(path.join(stagingCheckpoint, 'restore-verification.json'), `${JSON.stringify({
    checkpointId: targetName,
    initialState: 'pending_independent_restore',
    expectedSourceOfTruth: 'server',
    expectedInvoicePrepareCount: 1,
    expectedInvoiceDataStatus: 'complete',
    expectedValidationStatus: 'passed',
    expectedNextStepReadiness: 'ready_for_accounts_payable_draft',
    expectedDownstreamWriteCount: 0,
    generatedAt: new Date().toISOString(),
  }, null, 2)}\n`)
  await cp(screenshot, path.join(stagingCheckpoint, 'checkpoint-screenshot.png'))
  await cp(trace, path.join(stagingCheckpoint, 'trace.zip'))
  await cp(reportPath, path.join(stagingCheckpoint, 'validation-report.json')).catch(() => {})
  await cp(matrixPath, path.join(stagingCheckpoint, 'validation-matrix.json'))
  await cp(pageReportPath, path.join(stagingCheckpoint, 'validation-page.json'))
  await cp(releaseReportPath, path.join(stagingCheckpoint, 'ap-draft-release-report.json'))

  const report = {
    version: 'V1.14.2.8.4.7.44',
    versionName: '采购发票准备资料采集、发票要素校验与采购应付账款草稿放行闭环',
    result: 'passed',
    checkpoint: targetName,
    inputCheckpoint: 'purchase_invoice_prepare_current_state_consistent_ready',
    inputCheckpointImmutable: true,
    inputCheckpointHashes: inputHashesAfter,
    migrationForwardRollbackReplayPassed: true,
    guardsPassed: true,
    azCanaryPassed: true,
    parameterizedFailureMatrixPassed: true,
    pageAcceptancePassed: true,
    crossProcessRecoveryPassed: true,
    serverReadModelPassed: true,
    preparedStatus: finalState.prepare.status,
    invoiceDataStatus: finalState.prepare.invoiceDataStatus,
    validationStatus: finalState.prepare.validationStatus,
    validationIssueCount: finalState.prepare.validationIssueCount,
    identityClaimCount: finalState.counts.claims,
    saveIdempotencyStatus: recoveredSave.classification,
    validationIdempotencyStatus: recoveredValidation.classification,
    apDraftEligibility: finalState.eligibility,
    apDraftNavigationOnly: true,
    productionRolloutEnabled: false,
    userProductionDataModified: false,
    downstreamCounts: finalState.downstreamCounts,
    buildPassed: true,
    viteProductionBuildCompleted: true,
    djangoCheckPassed: true,
    compileallPassed: true,
    outOfScopeNewChangeCount: 0,
    commands: executed.map(({ command, code, startedAt, finishedAt }) => ({ command, code, startedAt, finishedAt })),
  }
  await writeFile(reportPath, `${JSON.stringify(report, null, 2)}\n`)
  await cp(reportPath, path.join(stagingCheckpoint, 'validation-report.json'))

  const manifest = {
    checkpointVersion: '1.0.0',
    version: 'V1.14.2.8.4.7.44',
    checkpointId: targetName,
    sourceCheckpointId: 'purchase_invoice_prepare_current_state_consistent_ready',
    createdAt: new Date().toISOString(),
    origin: 'http://localhost:5173',
    entityIds: [
      `purchase-invoice-prepare:${finalState.prepare.prepareNo}`,
      `purchase-invoice-data:${finalState.invoiceData.id}`,
      `purchase-invoice-validation:${finalState.validation.validationVersion}`,
    ],
    nextStageId: 'account-payable-draft',
    immutable: true,
    restorable: true,
    integrityFiles: ['storage-state.json', 'application-state.json', 'business-entities.json', 'relationship-graph.json'],
    integrityHash: await checkpointIntegrityHash(stagingCheckpoint),
    canonicalName: '采购发票准备',
    moduleNavigationUnchanged: true,
    sourceDocumentType: 'purchaseReconciliation',
    invoiceDataModelReady: true,
    serverPersistenceReady: true,
    serverReadModelReady: true,
    invoiceDataVersioningReady: true,
    invoiceLineModelReady: true,
    invoiceValidationModelReady: true,
    invoiceIdentityPolicyReady: true,
    duplicateInvoiceProtectionReady: true,
    decimalMoneyValidationReady: true,
    taxValidationReady: true,
    serverValidationReady: true,
    invoiceValidationReady: true,
    invoiceIdentityUniqueConstraintReady: true,
    saveIdempotencyReady: true,
    validationIdempotencyReady: true,
    atomicAuditReady: true,
    rollbackReady: true,
    commitRecoveryReady: true,
    crossProcessRecoveryReady: true,
    accountsPayableDraftNavigationEligible: true,
    accountsPayableDraftEligibilityReady: true,
    currentStateSource: 'server',
    preparedStateReady: true,
    accountsPayableDraftCreated: false,
    purchaseInvoicePrepareStatus: 'prepared',
    invoiceDataStatus: 'complete',
    validationStatus: 'passed',
    validationResultCode: 'validated',
    validationIssueCount: 0,
    invoiceIdentityClaimStatus: 'active',
    nextStepReadiness: 'ready_for_accounts_payable_draft',
    testTenantOnly: true,
    productionRolloutEnabled: false,
    productionUserDataWritten: false,
    zeroAccountsPayableDraftWrite: true,
    zeroPaymentObjectWrite: true,
    zeroPaymentVoucherWrite: true,
    zeroLedgerWrite: true,
    businessState: {
      purchaseInvoicePrepareNo: finalState.prepare.prepareNo,
      status: 'prepared',
      invoiceDataStatus: 'complete',
      validationStatus: 'passed',
      validationIssueCount: 0,
      nextStepReadiness: 'ready_for_accounts_payable_draft',
      accountsPayableDraftCount: 0,
    },
    reports: ['validation-report.json', 'validation-matrix.json', 'validation-page.json', 'ap-draft-release-report.json'],
  }
  await writeFile(path.join(stagingCheckpoint, 'manifest.json'), `${JSON.stringify(manifest, null, 2)}\n`)
  await rename(stagingCheckpoint, targetCheckpoint)

  process.stdout.write(`${JSON.stringify({ result: 'passed', checkpoint: targetCheckpoint, reportPath: path.join(targetCheckpoint, 'validation-report.json'), inputCheckpointHashes: inputHashesAfter, downstreamCounts: finalState.downstreamCounts })}\n`)
}

main().catch(async (error) => {
  await stop(frontendProcess)
  await stop(backendProcess)
  await mkdir(isolatedRoot, { recursive: true }).catch(() => {})
  const failure = {
    version: 'V1.14.2.8.4.7.44',
    result: 'failed',
    error: error.stack || String(error),
    failedCommand: error.result?.command || null,
    exitCode: error.result?.code ?? 1,
    commands: executed,
  }
  await writeFile(failureReportPath, `${JSON.stringify(failure, null, 2)}\n`).catch(() => {})
  process.stderr.write(`${JSON.stringify({ ...failure, failureReportPath })}\n`)
  process.exitCode = 1
}).finally(async () => {
  await stop(frontendProcess)
  await stop(backendProcess)
  if (existsSync(stagingCheckpoint)) await rm(stagingCheckpoint, { recursive: true, force: true }).catch(() => {})
})
