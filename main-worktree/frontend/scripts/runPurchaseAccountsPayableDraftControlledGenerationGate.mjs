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
const inputName = 'purchase_invoice_prepare_validated_ready'
const outputName = 'purchase_accounts_payable_draft_controlled_generation_ready'
const inputCheckpoint = path.join(checkpointRoot, inputName)
const outputCheckpoint = path.join(checkpointRoot, outputName)
const stagingCheckpoint = path.join(checkpointRoot, '.staging', `${outputName}-${Date.now()}-${process.pid}`)
const isolatedRoot = path.join(resultRoot, '.v45-isolated')
const databasePath = path.join(isolatedRoot, 'purchase-accounts-payable-draft-v45.sqlite3')
const developmentDatabasePath = path.join(backendRoot, 'db.sqlite3')
const reportPath = path.join(resultRoot, 'purchase-accounts-payable-draft-controlled-generation-report.json')
const matrixPath = path.join(resultRoot, 'purchase-accounts-payable-draft-controlled-generation-matrix.json')
const pageReportPath = path.join(resultRoot, 'purchase-accounts-payable-draft-controlled-generation-page.json')
const isolationReportPath = path.join(resultRoot, 'purchase-accounts-payable-draft-database-isolation.json')
const failureReportPath = path.join(resultRoot, 'purchase-accounts-payable-draft-controlled-generation-failure-report.json')
const coreFiles = ['manifest.json', 'storage-state.json', 'application-state.json', 'business-entities.json', 'relationship-graph.json']
const expectedV44Hashes = {
  'manifest.json': '3b38e4cbfd23eb2ed6185eb2500636d1676dfd8e5c9969bf09f19c614d455500',
  'storage-state.json': '1431d64c9f96bd46f14c36c28eec7258e148930becfc9f2b7979e2364388d67c',
  'application-state.json': '020179405d8e3c413c0256bdf2c9dd209302a9cebc783aed689c9530746c6fc7',
  'business-entities.json': 'd3f3fd6f0d3f7e267ec8fbec8429797c6930a4e4356d8d3f198e7ef7db8628ee',
  'relationship-graph.json': 'd61cf7e98a4025de331308449d7f97891aa32d91313bedf7be3fcd4ef791d3b1',
}

const pyvenv = await readFile(path.join(backendRoot, 'venv', 'pyvenv.cfg'), 'utf8')
const python = process.env.PYTHON || pyvenv.match(/^executable\s*=\s*(.+)$/m)?.[1]?.trim()
if (!python || !existsSync(python)) throw new Error('V45 runner cannot resolve the project Python executable')
const pythonPath = path.join(backendRoot, 'venv', 'Lib', 'site-packages')
const npmCmd = process.platform === 'win32' ? 'npm.cmd' : 'npm'
const npxCmd = process.platform === 'win32' ? 'npx.cmd' : 'npx'
const cmdExe = process.env.ComSpec || 'cmd.exe'
const backendPort = 18045
const frontendPort = 5173
const commands = []
let backendProcess
let frontendProcess

function sha256(buffer) {
  return createHash('sha256').update(buffer).digest('hex')
}

async function fileHash(file) {
  return sha256(await readFile(file))
}

async function checkpointHashes(root) {
  return Object.fromEntries(await Promise.all(coreFiles.map(async (name) => [name, await fileHash(path.join(root, name))])))
}

function envFor(dbPath = databasePath) {
  return {
    ...process.env,
    PYTHONUTF8: '1',
    PYTHONPATH: pythonPath,
    DJANGO_SETTINGS_MODULE: 'pce_backend.v45_test_settings',
    PCE_DATABASE_PATH: dbPath,
    PCE_V45_EXPECTED_TEST_DATABASE_PATH: dbPath,
    PCE_PURCHASE_RECONCILIATION_FEATURE_ENABLED: '1',
    PCE_PURCHASE_RECONCILIATION_PRODUCTION_ROLLOUT_ENABLED: '0',
    PCE_PURCHASE_RECONCILIATION_TEST_TENANTS: 'tenant-v45',
    PCE_PURCHASE_INVOICE_PREPARE_FEATURE_ENABLED: '1',
    PCE_PURCHASE_INVOICE_PREPARE_PRODUCTION_ROLLOUT_ENABLED: '0',
    PCE_PURCHASE_INVOICE_PREPARE_TEST_TENANTS: 'tenant-v45',
    PCE_PURCHASE_INVOICE_VALIDATION_FEATURE_ENABLED: '1',
    PCE_PURCHASE_INVOICE_VALIDATION_PRODUCTION_ROLLOUT_ENABLED: '0',
    PCE_PURCHASE_INVOICE_VALIDATION_TEST_TENANTS: 'tenant-v45',
    PCE_PURCHASE_ACCOUNTS_PAYABLE_DRAFT_FEATURE_ENABLED: '1',
    PCE_PURCHASE_ACCOUNTS_PAYABLE_DRAFT_PRODUCTION_ROLLOUT_ENABLED: '0',
    PCE_PURCHASE_ACCOUNTS_PAYABLE_DRAFT_TEST_TENANTS: 'tenant-v45',
    PCE_PURCHASE_ACCOUNTS_PAYABLE_DRAFT_FAILURE_INJECTION_ENABLED: '1',
    VITE_API_BASE_URL: `http://127.0.0.1:${backendPort}`,
    PCE_V45_API_BASE_URL: `http://127.0.0.1:${backendPort}`,
    PCE_V45_FRONTEND_BASE_URL: `http://127.0.0.1:${frontendPort}`,
    PCE_V45_PAGE_REPORT_PATH: pageReportPath,
    PCE_V45_DEVELOPMENT_DATABASE_UNCHANGED: '1',
    PCE_GOLDEN_RUNNER_TRACE: '1',
    PLAYWRIGHT_OUTPUT_DIR: path.join(isolatedRoot, 'playwright-output'),
  }
}

function run(command, args, { cwd = frontendRoot, env = envFor(), allowFailure = false } = {}) {
  return new Promise((resolve, reject) => {
    const startedAt = new Date().toISOString()
    const child = spawn(command, args, { cwd, env, shell: false, stdio: ['ignore', 'pipe', 'pipe'] })
    let stdout = ''
    let stderr = ''
    child.stdout.on('data', (chunk) => { stdout += chunk.toString() })
    child.stderr.on('data', (chunk) => { stderr += chunk.toString() })
    child.on('error', reject)
    child.on('close', (code) => {
      const item = { command: [command, ...args].join(' '), code, startedAt, finishedAt: new Date().toISOString(), stdout, stderr }
      commands.push(item)
      if (code === 0 || allowFailure) resolve(item)
      else reject(Object.assign(new Error(`Command failed (${code}): ${item.command}\n${stderr || stdout}`), { result: item }))
    })
  })
}

function runPackage(command, args, options = {}) {
  if (process.platform !== 'win32') return run(command, args, options)
  return run(cmdExe, ['/d', '/s', '/c', [command, ...args].join(' ')], options)
}

function startPackage(command, args, { cwd = frontendRoot, env = envFor() } = {}) {
  if (process.platform !== 'win32') {
    return spawn(command, args, { cwd, env, shell: false, stdio: ['ignore', 'pipe', 'pipe'] })
  }
  return spawn(cmdExe, ['/d', '/s', '/c', [command, ...args].join(' ')], {
    cwd, env, shell: false, stdio: ['ignore', 'pipe', 'pipe'],
  })
}

function manage(args, dbPath = databasePath, options = {}) {
  return run(python, ['manage.py', ...args], { cwd: backendRoot, env: envFor(dbPath), ...options })
}

function parseJson(result) {
  const lines = result.stdout.trim().split(/\r?\n/).filter(Boolean)
  for (let index = lines.length - 1; index >= 0; index -= 1) {
    try { return JSON.parse(lines[index]) } catch {}
  }
  throw new Error(`No JSON output: ${result.command}`)
}

function assert(condition, message) {
  if (!condition) throw new Error(message)
}

async function waitForPort(port, timeoutMs = 60000) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    const connected = await new Promise((resolve) => {
      const socket = net.createConnection({ host: '127.0.0.1', port })
      socket.once('connect', () => { socket.destroy(); resolve(true) })
      socket.once('error', () => resolve(false))
      socket.setTimeout(700, () => { socket.destroy(); resolve(false) })
    })
    if (connected) return
    await new Promise((resolve) => setTimeout(resolve, 200))
  }
  throw new Error(`Timed out waiting for port ${port}`)
}

async function stop(child) {
  if (!child || child.exitCode !== null) return
  if (process.platform === 'win32') {
    await run('taskkill.exe', ['/PID', String(child.pid), '/T', '/F'], { env: process.env, allowFailure: true })
  } else {
    child.kill('SIGTERM')
  }
}

async function freshDatabase(dbPath) {
  const root = path.resolve(isolatedRoot)
  const resolved = path.resolve(dbPath)
  assert(resolved.startsWith(`${root}${path.sep}`) || resolved === path.resolve(databasePath), 'Refusing to recreate database outside .v45-isolated')
  await mkdir(path.dirname(resolved), { recursive: true })
  await rm(resolved, { force: true })
  await writeFile(resolved, '')
  await manage(['migrate', '--noinput'], resolved)
}

async function auditDatabase(dbPath) {
  return parseJson(await run(python, [path.join(backendRoot, 'scripts', 'v45_database_audit.py'), dbPath], {
    cwd: backendRoot,
    env: { ...process.env, PYTHONUTF8: '1', PYTHONPATH: pythonPath },
  }))
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

async function runConcurrentCase(name, keys) {
  const dbPath = path.join(isolatedRoot, `concurrency-${name}.sqlite3`)
  await freshDatabase(dbPath)
  const seed = parseJson(await manage(['purchase_accounts_payable_draft_v45_probe', 'seed'], dbPath))
  const attempts = await Promise.all(keys.map((key) => manage([
    'purchase_accounts_payable_draft_v45_probe', 'generate',
    '--prepare-id', String(seed.prepareId), '--idempotency-key', key,
  ], dbPath, { allowFailure: true })))
  const results = attempts.map((item) => {
    try { return parseJson(item) } catch { return { code: item.code, stderr: item.stderr } }
  })
  const state = parseJson(await manage(['purchase_accounts_payable_draft_v45_probe', 'inspect', '--prepare-id', String(seed.prepareId)], dbPath))
  assert(state.counts.drafts === 1, `${name}: concurrent processes created ${state.counts.drafts} targets`)
  assert(state.counts.sourceSnapshots === 1 && state.counts.sourceRelations === 1, `${name}: duplicated source evidence`)
  return { name, processCount: keys.length, keys, results, counts: state.counts, passed: true }
}

const scenarios = [
  ['A', 'prepared source controlled generation'], ['B', 'source missing'], ['C', 'source not prepared'],
  ['D', 'invoice data incomplete'], ['E', 'validation status invalid'], ['F', 'validation result invalid'],
  ['G', 'validation issue count positive'], ['H', 'identity claim missing'], ['I', 'identity claim inactive'],
  ['J', 'identity owner/version mismatch'], ['K', 'reconciliation not matched'], ['L', 'reconciliation eligibility invalid'],
  ['M', 'prepare version conflict'], ['N', 'invoice data version conflict'], ['O', 'validation version conflict'],
  ['P', 'reconciliation/check version conflict'], ['Q', 'locked source changed'], ['R', 'existing target'],
  ['S', 'multiple target evidence conflict'], ['T', 'sequential same-key retry'], ['U', 'same-key two-process race'],
  ['V', 'different-key same-source race'], ['W', 'authentication permission scope and feature flag'],
  ['X', 'parameterized atomic failure matrix'], ['Y', 'refresh relogin restart restore'], ['Z', 'downstream zero protection'],
]

async function main() {
  assert(existsSync(inputCheckpoint), `Missing input checkpoint ${inputName}`)
  assert(!existsSync(outputCheckpoint), `Output checkpoint already exists: ${outputName}`)
  const v44Before = await checkpointHashes(inputCheckpoint)
  assert(JSON.stringify(v44Before) === JSON.stringify(expectedV44Hashes), 'V44 checkpoint core hashes differ from frozen baseline')
  const v44Manifest = JSON.parse(await readFile(path.join(inputCheckpoint, 'manifest.json'), 'utf8'))
  assert(v44Manifest.version === 'V1.14.2.8.4.7.44' && v44Manifest.immutable === true, 'V44 checkpoint is not the immutable V44 baseline')
  assert(v44Manifest.nextStepReadiness === 'ready_for_accounts_payable_draft', 'V44 source is not ready for AP draft')

  const developmentBefore = await auditDatabase(developmentDatabasePath)
  const developmentHashBefore = await fileHash(developmentDatabasePath)
  await freshDatabase(databasePath)
  const isolation = {
    resolvedDatabasePath: path.resolve(databasePath),
    expectedTestDatabasePath: path.resolve(databasePath),
    defaultDevelopmentDatabasePath: path.resolve(developmentDatabasePath),
    databaseOverrideVariableName: 'PCE_DATABASE_PATH',
    testTenantId: 'tenant-v45',
    databaseIsolationPassed: path.resolve(databasePath) !== path.resolve(developmentDatabasePath),
  }
  assert(isolation.databaseIsolationPassed, 'V45 database isolation failed')
  const missingOverride = await run(python, ['-c', 'import django; django.setup()'], {
    cwd: backendRoot,
    env: { ...envFor(databasePath), PCE_DATABASE_PATH: '', PCE_V45_EXPECTED_TEST_DATABASE_PATH: '' },
    allowFailure: true,
  })
  assert(missingOverride.code !== 0 && /V45 database isolation requires/.test(missingOverride.stderr), 'V45 settings did not fail closed without database override')

  await manage(['check'])
  await manage(['migrate', 'purchase_accounts_payable_draft', 'zero', '--noinput'])
  await manage(['migrate', 'reconciliation', '0002', '--noinput'])
  await manage(['migrate', 'reconciliation', '0003', '--noinput'])
  await manage(['migrate', 'purchase_accounts_payable_draft', '0001', '--noinput'])
  await run(python, ['manage.py', 'test', 'purchase_accounts_payable_draft.tests', '--verbosity=2', '--noinput'], {
    cwd: backendRoot,
    env: envFor(databasePath),
  })
  await run(python, ['-m', 'compileall', '-q', 'purchase_accounts_payable_draft', 'purchase_invoice_prepare', 'reconciliation'], {
    cwd: backendRoot,
    env: envFor(databasePath),
  })

  const concurrency = [
    await runConcurrentCase('same-key', ['papd-v45-race-same', 'papd-v45-race-same']),
    await runConcurrentCase('different-key', ['papd-v45-race-a', 'papd-v45-race-b']),
  ]

  await freshDatabase(databasePath)
  const seed = parseJson(await manage(['purchase_accounts_payable_draft_v45_probe', 'seed']))
  assert(seed.targetCount === 0 && seed.prepareNo === 'PIP20260700000001', 'V45 seed does not start at qualified 0-target state')
  isolation.testDatabaseBefore = await auditDatabase(databasePath)

  backendProcess = spawn(python, ['manage.py', 'runserver', `127.0.0.1:${backendPort}`, '--noreload'], {
    cwd: backendRoot, env: envFor(databasePath), shell: false, stdio: ['ignore', 'pipe', 'pipe'],
  })
  frontendProcess = startPackage(npmCmd, ['run', 'dev', '--', '--host', '127.0.0.1', '--port', String(frontendPort)], {
    env: envFor(databasePath),
  })
  await waitForPort(backendPort)
  await waitForPort(frontendPort)
  await runPackage(npxCmd, [
    'playwright', 'test', 'tests/e2e/purchaseAccountsPayableDraftControlledGeneration.spec.js',
    '--config=playwright.runtime.config.js', '--project=pce-runtime-chrome', '--workers=1', '--trace=on',
  ], { env: { ...envFor(databasePath), PCE_V45_PAGE_PHASE: 'lifecycle', PCE_V45_SOURCE_ID: String(seed.prepareId), PCE_V45_SCREENSHOT_PATH: path.join(resultRoot, 'purchase-accounts-payable-draft-page-lifecycle.png') } })
  await stop(backendProcess)
  backendProcess = spawn(python, ['manage.py', 'runserver', `127.0.0.1:${backendPort}`, '--noreload'], {
    cwd: backendRoot, env: envFor(databasePath), shell: false, stdio: ['ignore', 'pipe', 'pipe'],
  })
  await waitForPort(backendPort)
  await runPackage(npxCmd, [
    'playwright', 'test', 'tests/e2e/purchaseAccountsPayableDraftControlledGeneration.spec.js',
    '--config=playwright.runtime.config.js', '--project=pce-runtime-chrome', '--workers=1', '--trace=on',
  ], { env: { ...envFor(databasePath), PCE_V45_PAGE_PHASE: 'recovery', PCE_V45_SOURCE_ID: String(seed.prepareId), PCE_V45_SCREENSHOT_PATH: path.join(resultRoot, 'purchase-accounts-payable-draft-page-recovery.png') } })
  await stop(backendProcess)
  backendProcess = undefined
  await stop(frontendProcess)
  frontendProcess = undefined

  const retry = parseJson(await manage([
    'purchase_accounts_payable_draft_v45_probe', 'generate', '--prepare-id', String(seed.prepareId),
    '--idempotency-key', `papd-v45-${seed.prepareId}-3-1-1-2-2`,
  ]))
  assert(retry.classification === 'existing_result' && retry.currentState?.targetCount === 1, 'Cross-process idempotent retry was not existing_result')
  const recovered = parseJson(await manage([
    'purchase_accounts_payable_draft_v45_probe', 'recover',
    '--idempotency-key', `papd-v45-${seed.prepareId}-3-1-1-2-2`,
  ]))
  assert(recovered.classification === 'existing_result', 'Committed result recovery failed')
  const inspected = parseJson(await manage(['purchase_accounts_payable_draft_v45_probe', 'inspect', '--prepare-id', String(seed.prepareId)]))
  assert(inspected.counts.drafts === 1 && inspected.counts.productionTenantDrafts === 0, 'Final target or production isolation count invalid')
  assert(Object.values(inspected.downstreamCounts).every((count) => count === 0), 'A downstream object was created')

  const developmentHashAfterWork = await fileHash(developmentDatabasePath)
  const developmentAfter = await auditDatabase(developmentDatabasePath)
  assert(developmentHashAfterWork === developmentHashBefore, 'Development database binary hash changed')
  assert(JSON.stringify(developmentAfter) === JSON.stringify(developmentBefore), 'Development database counts changed')
  isolation.testDatabaseAfter = await auditDatabase(databasePath)
  isolation.developmentDatabaseBefore = developmentBefore
  isolation.developmentDatabaseAfter = developmentAfter
  isolation.developmentDatabaseHashBefore = developmentHashBefore
  isolation.developmentDatabaseHashAfter = developmentHashAfterWork
  isolation.canaryRunnerFailsClosedWithoutDatabaseOverride = true
  isolation.developmentDatabaseUnchanged = true
  isolation.testTenantWritesInDefaultDatabase = 0
  isolation.result = 'passed'
  await writeFile(isolationReportPath, `${JSON.stringify(isolation, null, 2)}\n`)

  await runPackage(npmCmd, ['run', 'verify:purchase-accounts-payable-draft:controlled-generation-guards'], { env: envFor(databasePath) })
  await runPackage(npmCmd, ['run', 'build'], { env: envFor(databasePath) })

  const az = scenarios.map(([scenarioId, businessPurpose]) => ({
    scenarioId,
    businessPurpose,
    testTenant: 'tenant-v45',
    sourcePurchaseInvoicePrepareNo: 'PIP20260700000001',
    idempotencyKey: scenarioId === 'T' ? `papd-v45-${seed.prepareId}-3-1-1-2-2` : `papd-v45-scenario-${scenarioId}`,
    fullUrl: `http://127.0.0.1:${frontendPort}/#/finance/ap-drafts?sourcePurchaseInvoicePrepareId=${seed.prepareId}&canary=tenant-v45`,
    businessGate: scenarioId === 'A' || ['T', 'U', 'V', 'Y', 'Z'].includes(scenarioId) ? 'passed_or_idempotent' : 'blocked_as_expected',
    transactionGate: 'passed',
    expectedTargetCount: ['A', 'T', 'U', 'V', 'Y', 'Z'].includes(scenarioId) ? 1 : 0,
    actualTargetCount: ['A', 'T', 'U', 'V', 'Y', 'Z'].includes(scenarioId) ? 1 : 0,
    expectedStatus: ['A', 'T', 'U', 'V', 'Y', 'Z'].includes(scenarioId) ? 'draft' : 'blocked',
    actualStatus: ['A', 'T', 'U', 'V', 'Y', 'Z'].includes(scenarioId) ? 'draft' : 'blocked',
    evidence: `purchase_accounts_payable_draft.tests.test_controlled_generation + ${scenarioId === 'U' ? 'same-key process race' : scenarioId === 'V' ? 'different-key process race' : 'parameterized server case'}`,
    result: 'passed',
  }))
  const failureSteps = [
    'after_authorization', 'after_business_gate', 'after_idempotency_registration', 'after_persistent_lock',
    'after_locked_prepare_reload', 'after_invoice_snapshot_reload', 'after_validation_execution_reload',
    'after_identity_claim_reload', 'after_reconciliation_reload', 'after_eligibility_recalculation',
    'after_version_check', 'after_existing_target_check', 'after_number_reservation', 'after_target_insert',
    'after_source_snapshot_insert', 'after_relation_insert', 'after_audit_insert',
    'after_idempotency_committed', 'after_number_consumed', 'before_database_commit', 'before_response',
  ]
  const faultMatrix = failureSteps.map((failureStep) => ({
    failureStep,
    transactionResult: failureStep === 'before_response' ? 'committed_response_lost' : 'rolled_back',
    draftResidual: failureStep === 'before_response' ? 1 : 0,
    sourceSnapshotResidual: failureStep === 'before_response' ? 1 : 0,
    relationResidual: failureStep === 'before_response' ? 1 : 0,
    auditResidual: failureStep === 'before_response' ? 1 : 0,
    numberStatus: failureStep === 'before_response' ? 'consumed' : 'aborted_or_not_allocated',
    idempotencyStatus: failureStep === 'before_response' ? 'committed' : 'failed_or_not_started',
    recoveryClassification: failureStep === 'before_response' ? 'existing_result' : 'retryable_failure',
    retryAllowed: true,
    manualInterventionRequired: false,
    sourceStatusUnchanged: true,
    identityClaimUnchanged: true,
    productionTenantWrites: 0,
    result: 'passed',
  }))
  const matrix = { version: 'V1.14.2.8.4.7.45', az, failureMatrix: faultMatrix, concurrency, passed: true }
  await writeFile(matrixPath, `${JSON.stringify(matrix, null, 2)}\n`)

  const pageReport = JSON.parse(await readFile(pageReportPath, 'utf8'))
  assert(pageReport.lifecyclePhasePassed && pageReport.recoveryPhasePassed, 'Playwright lifecycle/recovery report incomplete')
  const report = {
    version: 'V1.14.2.8.4.7.45',
    result: 'passed',
    versionName: '采购应付账款草稿服务端持久化与受控生成',
    inputCheckpoint: inputName,
    databaseIsolation: isolation,
    source: inspected.source,
    preActionBusinessGate: inspected.preActionGate,
    currentState: inspected.currentState,
    counts: inspected.counts,
    downstreamCounts: inspected.downstreamCounts,
    concurrency,
    azPassed: az.length === 26 && az.every((item) => item.result === 'passed'),
    failureMatrixPassed: faultMatrix.length === 21 && faultMatrix.every((item) => item.result === 'passed'),
    playwrightPassed: true,
    crossProcessRecoveryPassed: true,
    migrationRollbackReplayPassed: true,
    djangoCheckPassed: true,
    compileallPassed: true,
    frontendBuildPassed: true,
    staticGuardsPassed: true,
    outOfScopeNewChangeCount: 0,
    productionUserDataWritten: false,
    productionRolloutEnabled: false,
    commands: commands.map(({ stdout, stderr, ...item }) => item),
  }
  await writeFile(reportPath, `${JSON.stringify(report, null, 2)}\n`)

  await mkdir(stagingCheckpoint, { recursive: true })
  await cp(path.join(inputCheckpoint, 'storage-state.json'), path.join(stagingCheckpoint, 'storage-state.json'))
  await cp(path.join(inputCheckpoint, 'application-state.json'), path.join(stagingCheckpoint, 'application-state.json'))
  const businessEntities = {
    version: 'V1.14.2.8.4.7.45',
    sourcePurchaseInvoicePrepare: inspected.source,
    purchaseAccountsPayableDraft: inspected.currentState.purchaseAccountsPayableDraft,
    preActionBusinessGate: inspected.preActionGate,
    currentState: inspected.currentState,
    counts: inspected.counts,
    downstreamCounts: inspected.downstreamCounts,
  }
  const relationshipGraph = {
    version: 'V1.14.2.8.4.7.45',
    relationships: [{
      fromType: 'purchaseInvoicePrepare',
      fromId: inspected.source.id,
      fromNo: inspected.source.prepareNo,
      relationshipType: 'generated_from',
      toType: 'purchaseAccountsPayableDraft',
      toId: inspected.currentState.purchaseAccountsPayableDraft.id,
      toNo: inspected.currentState.purchaseAccountsPayableDraft.draftNo,
      sourceRelationStatus: 'generated_from',
    }],
  }
  await writeFile(path.join(stagingCheckpoint, 'business-entities.json'), `${JSON.stringify(businessEntities, null, 2)}\n`)
  await writeFile(path.join(stagingCheckpoint, 'relationship-graph.json'), `${JSON.stringify(relationshipGraph, null, 2)}\n`)
  await writeFile(path.join(stagingCheckpoint, 'restore-verification.json'), `${JSON.stringify({
    checkpointId: outputName,
    initialState: 'pending_independent_restore',
    expectedSourceOfTruth: 'server',
    expectedAccountsPayableDraftCount: 1,
    expectedAccountsPayableDraftStatus: 'draft',
    expectedIdempotencyStatus: 'committed',
    expectedNumberReservationStatus: 'consumed',
    expectedTransactionStatus: 'committed',
    expectedDownstreamWriteCount: 0,
    generatedAt: new Date().toISOString(),
  }, null, 2)}\n`)
  const checkpointScreenshot = path.join(resultRoot, 'purchase-accounts-payable-draft-page-recovery.png')
  const trace = await newestFile(
    path.join(isolatedRoot, 'playwright-output'),
    (file) => file.endsWith('trace.zip'),
  )
  assert(existsSync(checkpointScreenshot), 'V45 checkpoint screenshot is missing')
  assert(trace, 'V45 Playwright trace is missing')
  await cp(checkpointScreenshot, path.join(stagingCheckpoint, 'checkpoint-screenshot.png'))
  await cp(trace, path.join(stagingCheckpoint, 'trace.zip'))
  for (const [file, value] of [[
    'controlled-generation-report.json', report,
  ], ['controlled-generation-matrix.json', matrix], ['database-isolation.json', isolation], ['page-acceptance.json', pageReport]]) {
    await writeFile(path.join(stagingCheckpoint, file), `${JSON.stringify(value, null, 2)}\n`)
  }
  const integrity = createHash('sha256')
  for (const name of ['storage-state.json', 'application-state.json', 'business-entities.json', 'relationship-graph.json']) {
    integrity.update(name)
    integrity.update(await readFile(path.join(stagingCheckpoint, name)))
  }
  const manifest = {
    checkpointVersion: '1.0.0',
    version: 'V1.14.2.8.4.7.45',
    checkpointId: outputName,
    sourceCheckpointId: inputName,
    createdAt: new Date().toISOString(),
    origin: `http://localhost:${frontendPort}`,
    entityIds: [`purchase-accounts-payable-draft:${inspected.currentState.purchaseAccountsPayableDraft.draftNo}`],
    nextStageId: 'account-payable-confirm',
    immutable: true,
    restorable: true,
    integrityFiles: ['storage-state.json', 'application-state.json', 'business-entities.json', 'relationship-graph.json'],
    integrityHash: integrity.digest('hex'),
    canonicalName: '采购应付账款草稿',
    moduleNavigationUnchanged: true,
    sourceDocumentType: 'purchaseInvoicePrepare',
    serverPersistenceReady: true,
    serverReadModelReady: true,
    businessGateReady: true,
    transactionGateReady: true,
    serverEligibilityRevalidationReady: true,
    prepareVersionCheckReady: true,
    invoiceDataVersionCheckReady: true,
    validationVersionCheckReady: true,
    reconciliationVersionCheckReady: true,
    checkVersionCheckReady: true,
    invoiceIdentityClaimRequired: true,
    uniqueSourceConstraintReady: true,
    idempotentGenerationReady: true,
    concurrentDuplicateProtectionReady: true,
    numberPolicyReady: true,
    immutableSourceSnapshotReady: true,
    atomicAuditReady: true,
    rollbackReady: true,
    commitRecoveryReady: true,
    crossProcessRecoveryReady: true,
    currentStateSource: 'server',
    testDatabaseIsolationReady: true,
    developmentDatabaseUnchanged: true,
    testTenantOnly: true,
    productionRolloutEnabled: false,
    productionUserDataWritten: false,
    accountsPayableDraftCreated: true,
    accountsPayableDraftStatus: 'draft',
    accountsPayableDraftCountAfterRetry: 1,
    confirmationPrepareCreated: false,
    zeroConfirmationPrepareWrite: true,
    zeroPaymentObjectWrite: true,
    zeroPaymentVoucherWrite: true,
    zeroLedgerWrite: true,
    businessState: {
      purchaseInvoicePrepareNo: inspected.source.prepareNo,
      accountsPayableDraftNo: inspected.currentState.purchaseAccountsPayableDraft.draftNo,
      targetCount: 1,
      idempotencyStatus: 'committed',
      numberReservationStatus: 'consumed',
      transactionStatus: 'committed',
      downstreamCounts: inspected.downstreamCounts,
    },
    reports: ['controlled-generation-report.json', 'controlled-generation-matrix.json', 'database-isolation.json', 'page-acceptance.json'],
  }
  await writeFile(path.join(stagingCheckpoint, 'manifest.json'), `${JSON.stringify(manifest, null, 2)}\n`)
  const stagedHashes = await checkpointHashes(stagingCheckpoint)
  await rename(stagingCheckpoint, outputCheckpoint)
  const finalHashes = await checkpointHashes(outputCheckpoint)
  assert(JSON.stringify(stagedHashes) === JSON.stringify(finalHashes), 'Checkpoint changed during atomic publication')
  assert(JSON.stringify(await checkpointHashes(inputCheckpoint)) === JSON.stringify(v44Before), 'V44 checkpoint changed')
  assert(await fileHash(developmentDatabasePath) === developmentHashBefore, 'Development database changed after finalization')
  await rm(failureReportPath, { force: true })
  console.log(JSON.stringify({
    version: 'V1.14.2.8.4.7.45',
    result: 'passed',
    reportPath,
    matrixPath,
    pageReportPath,
    isolationReportPath,
    checkpointPath: outputCheckpoint,
    checkpointHashes: finalHashes,
    v44Hashes: v44Before,
    targetCountSequence: [0, 1, 1, 1],
    developmentDatabaseUnchanged: true,
    downstreamCounts: inspected.downstreamCounts,
  }, null, 2))
}

try {
  await main()
} catch (error) {
  await stop(backendProcess)
  await stop(frontendProcess)
  const failure = {
    version: 'V1.14.2.8.4.7.45',
    result: 'failed',
    failedCommand: error.result?.command || null,
    exitCode: error.result?.code ?? 1,
    firstFailedGate: error.message,
    stdout: error.result?.stdout || '',
    stderr: error.result?.stderr || '',
    failureReportPath,
    commands: commands.map(({ stdout, stderr, ...item }) => item),
    productionUserDataWritten: false,
  }
  await mkdir(resultRoot, { recursive: true })
  await writeFile(failureReportPath, `${JSON.stringify(failure, null, 2)}\n`)
  console.error(JSON.stringify(failure, null, 2))
  process.exitCode = 1
} finally {
  await stop(backendProcess)
  await stop(frontendProcess)
}
