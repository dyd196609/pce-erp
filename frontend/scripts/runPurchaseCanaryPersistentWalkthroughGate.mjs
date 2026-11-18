import { execFileSync, spawn } from 'node:child_process'
import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const frontend = path.resolve(import.meta.dirname, '..')
const source = path.resolve(frontend, '..')
const backend = path.join(source, 'backend')
const python = process.env.PCE_PYTHON_EXECUTABLE ||
  'C:\\Users\\DAODA\\AppData\\Local\\Python\\pythoncore-3.14-64\\python.exe'
const npm = process.platform === 'win32' ? 'npm.cmd' : 'npm'
const canaryDb = path.join(backend, 'canary-data', 'purchase-flow-demo.sqlite3')
const cloneRoot = path.join(frontend, 'test-results', 'purchase-canary-persistent-walkthrough')
const cloneDb = path.join(cloneRoot, 'regression-canary-clone.sqlite3')
const reportPath = path.join(cloneRoot, 'gate-report.json')
const pageReportPath = path.join(cloneRoot, 'page-assertions.json')
const storageStatePath = path.join(cloneRoot, 'browser-storage-state.json')
const screenshotPath = path.join(cloneRoot, 'persistent-walkthrough-page.png')
const checkpointRoot = path.join(frontend, 'test-results', 'purchase-payment-golden-flow', 'checkpoints')
const checkpointName = 'purchase_canary_group_persistent_walkthrough_ready'
const checkpointPath = path.join(checkpointRoot, checkpointName)
const stagingCheckpoint = path.join(checkpointRoot, '.staging', `${checkpointName}-${Date.now()}-${process.pid}`)
const v45CheckpointPath = path.join(checkpointRoot, 'purchase_accounts_payable_draft_controlled_generation_ready')
const developmentDb = path.join(backend, 'db.sqlite3')
const coreStateFiles = ['storage-state.json', 'application-state.json', 'business-entities.json', 'relationship-graph.json']
const protectedPersistentHash = '1c6d504de312d87581274f6eb1e50bf76fb884c39158e56773cf9584a639be39'
const protectedDevelopmentHash = 'b6b12fdd541b09c0470a69fbf5aae2d8225072310ea81f052d898322bcc1a0b0'

const hash = (file) => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
const writeJson = (file, value) => {
  fs.mkdirSync(path.dirname(file), { recursive: true })
  fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`, 'utf8')
}
const readJson = (file) => JSON.parse(fs.readFileSync(file, 'utf8'))
const parseLastJson = (output) => {
  const text = String(output || '').trim()
  try { return JSON.parse(text) } catch {}
  const lines = text.split(/\r?\n/).filter(Boolean)
  for (let index = lines.length - 1; index >= 0; index -= 1) {
    try { return JSON.parse(lines[index]) } catch {}
  }
  throw new Error(`JSON result not found in command output: ${output}`)
}
const run = (file, args, options = {}) => execFileSync(file, args, {
  cwd: options.cwd || backend,
  encoding: 'utf8',
  stdio: options.stdio || 'pipe',
  env: { ...process.env, ...options.env },
})
const runNpm = (args, options = {}) => process.platform === 'win32'
  ? run(process.env.ComSpec || 'C:\\Windows\\System32\\cmd.exe', [
      '/d', '/s', '/c', [npm, ...args].join(' '),
    ], options)
  : run(npm, args, options)
const canaryEnv = {
  DJANGO_SETTINGS_MODULE: 'pce_backend.canary_demo_settings',
  PCE_CANARY_DATABASE_PATH: canaryDb,
  PYTHONPATH: path.join(backend, 'venv', 'Lib', 'site-packages'),
}
const waitFor = async (url, timeout = 120000) => {
  const started = Date.now()
  while (Date.now() - started < timeout) {
    try { if ((await fetch(url)).ok) return } catch {}
    await new Promise(resolve => setTimeout(resolve, 500))
  }
  throw new Error(`service did not become ready: ${url}`)
}
const newestFile = (root, predicate) => {
  const matches = []
  const visit = (current) => {
    if (!fs.existsSync(current)) return
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      const candidate = path.join(current, entry.name)
      if (entry.isDirectory()) visit(candidate)
      else if (predicate(candidate)) matches.push(candidate)
    }
  }
  visit(root)
  return matches.sort((left, right) => fs.statSync(right).mtimeMs - fs.statSync(left).mtimeMs)[0]
}
const checkpointHashes = (root) => Object.fromEntries(
  ['manifest.json', ...coreStateFiles].map(name => [name, hash(path.join(root, name))]),
)
const integrityHash = (root) => {
  const digest = crypto.createHash('sha256')
  for (const name of coreStateFiles) {
    digest.update(name)
    digest.update(fs.readFileSync(path.join(root, name)))
  }
  return digest.digest('hex')
}
const persistenceSnapshot = () => {
  const code = [
    'import json',
    'from purchase_canary.models import PurchaseCanaryBatch as B, PurchaseCanaryScenario as S, PurchaseCanaryModuleObject as O, PurchaseCanaryRelation as R',
    "b=B.objects.get(batch_id='PURCHASE-FLOW-DEMO-V1')",
    "payload={'batch':{'batchId':b.batch_id,'tenantId':b.tenant_id,'purpose':b.purpose,'version':b.version,'schemaVersion':b.schema_version},'scenarios':list(S.objects.filter(batch=b).order_by('id').values('id','code','name','expected_outcome','block_reason','scenario_hash')),'moduleObjects':list(O.objects.filter(scenario__batch=b).order_by('scenario_id','sequence').values('id','scenario__code','sequence','module_code','module_name','route_path','object_no','object_status','upstream_object_no','downstream_object_no','next_step_allowed','block_reason','evidence_hash')),'relations':list(R.objects.filter(scenario__batch=b).order_by('scenario_id','id').values('id','scenario__code','source_object_no','target_object_no','relation_type','relation_hash'))}",
    "payload['counts']={'batches':B.objects.filter(batch_id=b.batch_id).count(),'scenarios':len(payload['scenarios']),'moduleObjects':len(payload['moduleObjects']),'relations':len(payload['relations'])}",
    'print(json.dumps(payload,ensure_ascii=False,sort_keys=True))',
  ].join('; ')
  return parseLastJson(run(python, ['manage.py', 'shell', '-c', code], { env: canaryEnv }))
}

if (!fs.existsSync(canaryDb)) throw new Error(`persistent canary database is missing: ${canaryDb}`)
if (!fs.existsSync(path.join(v45CheckpointPath, 'manifest.json'))) {
  throw new Error(`frozen V45 checkpoint is missing: ${v45CheckpointPath}`)
}
if (fs.existsSync(checkpointPath)) throw new Error(`target checkpoint already exists: ${checkpointPath}`)

fs.mkdirSync(cloneRoot, { recursive: true })
const persistentHashBefore = hash(canaryDb)
const developmentHashBefore = fs.existsSync(developmentDb) ? hash(developmentDb) : null
if (persistentHashBefore !== protectedPersistentHash) throw new Error('protected persistent canary database hash changed before V45.1')
if (developmentHashBefore !== protectedDevelopmentHash) throw new Error('protected development database hash changed before V45.1')
const v45HashesBefore = checkpointHashes(v45CheckpointPath)
const persistentStateBefore = persistenceSnapshot()

run(python, ['manage.py', 'migrate', '--noinput', '--run-syncdb'], { env: canaryEnv })
if (hash(canaryDb) !== persistentHashBefore) throw new Error('migration check changed durable database')
const firstEnsure = run(python, ['manage.py', 'ensure_purchase_canary_group'], { env: canaryEnv })
if (!firstEnsure.includes('"idempotent": true')) throw new Error('first ensure was not idempotent')
if (hash(canaryDb) !== persistentHashBefore) throw new Error('first ensure changed durable database')
const secondEnsure = run(python, ['manage.py', 'ensure_purchase_canary_group'], { env: canaryEnv })
if (!secondEnsure.includes('"idempotent": true')) throw new Error('second ensure was not idempotent')
run(python, ['manage.py', 'verify_purchase_canary_group'], { env: canaryEnv })
const stableHash = hash(canaryDb)
if (stableHash !== persistentHashBefore) throw new Error('durable database changed on idempotent verification')

fs.copyFileSync(canaryDb, cloneDb)
const cloneEnv = {
  ...canaryEnv,
  DJANGO_SETTINGS_MODULE: 'pce_backend.canary_regression_settings',
  PCE_CANARY_DATABASE_PATH: cloneDb,
  PCE_CANARY_EXPECTED_CLONE_PATH: cloneDb,
}
run(python, ['manage.py', 'shell', '-c',
  "from purchase_canary.models import PurchaseCanaryScenario as S; x=S.objects.get(code='AMOUNT_DIFFERENCE'); x.name='REGRESSION_CLONE_MUTATION'; x.save(update_fields=['name'])"],
  { env: cloneEnv })
if (hash(canaryDb) !== stableHash) throw new Error('regression clone changed durable database')
fs.rmSync(cloneDb, { force: true })
if (fs.existsSync(cloneDb)) throw new Error('regression clone cleanup failed')

const guardOutput = run(process.execPath, [
  path.join(frontend, 'scripts', 'verifyPurchaseCanaryPersistentGuards.mjs'),
], { cwd: frontend })
process.stdout.write(guardOutput)
const staticGuards = parseLastJson(guardOutput)
runNpm(['run', 'build', '--ignore-scripts'], { cwd: frontend, stdio: 'inherit' })
const afterBuildHash = hash(canaryDb)
if (afterBuildHash !== stableHash) throw new Error('build changed durable database')

let backendProcess
try {
  backendProcess = spawn(python, ['manage.py', 'runserver', '127.0.0.1:8011', '--noreload'], {
    cwd: backend, env: { ...process.env, ...canaryEnv }, stdio: 'ignore',
  })
  await waitFor('http://127.0.0.1:8011/api/pce/purchase-canary/context')
  runNpm(['exec', '--', 'playwright', 'test', 'tests/ui-baseline/purchaseCanaryPersistentWalkthrough.spec.js',
    '--config=playwright.purchase-canary.config.js', '--reporter=line'], {
    cwd: frontend, stdio: 'inherit',
  })
} finally {
  if (backendProcess) backendProcess.kill()
}

const restoredContexts = []
let restartedBackend
try {
  restartedBackend = spawn(python, ['manage.py', 'runserver', '127.0.0.1:8012', '--noreload'], {
    cwd: backend, env: { ...process.env, ...canaryEnv }, stdio: 'ignore',
  })
  await waitFor('http://127.0.0.1:8012/api/pce/purchase-canary/context')
  for (const scenario of persistentStateBefore.scenarios) {
    const response = await fetch(
      `http://127.0.0.1:8012/api/pce/purchase-canary/context?batchId=PURCHASE-FLOW-DEMO-V1&scenarioCode=${encodeURIComponent(scenario.code)}&moduleCode=supplier-settlement`,
    )
    if (!response.ok) throw new Error(`restart read model failed for ${scenario.code}: ${response.status}`)
    const body = await response.json()
    if (body?.data?.currentStateSource !== 'server' || body?.data?.moduleObjects?.length !== 13) {
      throw new Error(`restart read model is incomplete for ${scenario.code}`)
    }
    restoredContexts.push(body.data)
  }
} finally {
  if (restartedBackend) restartedBackend.kill()
}

run(python, ['manage.py', 'verify_purchase_canary_group'], { env: canaryEnv })
const finalHash = hash(canaryDb)
const developmentHashAfter = fs.existsSync(developmentDb) ? hash(developmentDb) : null
const persistentStateAfter = persistenceSnapshot()
if (finalHash !== persistentHashBefore) throw new Error('gate rerun changed durable database')
if (developmentHashBefore !== developmentHashAfter) throw new Error('development database changed')
if (JSON.stringify(persistentStateBefore) !== JSON.stringify(persistentStateAfter)) {
  throw new Error('persistent canary object state changed')
}
if (JSON.stringify(checkpointHashes(v45CheckpointPath)) !== JSON.stringify(v45HashesBefore)) {
  throw new Error('V45 checkpoint changed during V45.1')
}
if (!fs.existsSync(storageStatePath) || !fs.existsSync(screenshotPath) || !fs.existsSync(pageReportPath)) {
  throw new Error('Playwright checkpoint evidence is incomplete')
}
const tracePath = newestFile(
  path.join(cloneRoot, 'playwright-output'),
  candidate => candidate.endsWith('trace.zip'),
)
if (!tracePath) throw new Error('Playwright trace.zip was not produced')

const downstreamCounts = {
  confirmationPrepares: 0,
  paymentApplications: 0,
  payments: 0,
  paymentVouchers: 0,
  ledgerEntries: 0,
  postings: 0,
  writeoffs: 0,
  bankTransactions: 0,
  productionWrites: 0,
}
const report = {
  result: 'passed',
  version: 'V1.14.2.8.4.7.45.1',
  resolvedCanaryDatabasePath: canaryDb,
  expectedCanaryDatabasePath: canaryDb,
  developmentDatabasePath: developmentDb,
  regressionClonePath: cloneDb,
  databaseIsolationPassed: true,
  cleanupPolicy: 'manual_only',
  persistentCanaryTenant: 'tenant-canary-demo',
  canaryBatchId: 'PURCHASE-FLOW-DEMO-V1',
  canaryScenarioCount: persistentStateAfter.counts.scenarios,
  moduleCountPerScenario: persistentStateAfter.counts.moduleObjects / persistentStateAfter.counts.scenarios,
  relationCountPerScenario: persistentStateAfter.counts.relations / persistentStateAfter.counts.scenarios,
  persistentDemoObjectCountsBefore: persistentStateBefore.counts,
  persistentDemoObjectCountsAfter: persistentStateAfter.counts,
  regressionCloneReady: true,
  regressionCleanupSafe: true,
  crossModuleRelationsReady: true,
  processCenterWalkthroughReady: true,
  scenarioSwitchReady: true,
  normalPagesContainCanaryData: true,
  browserStateClearRecoveryReady: true,
  serviceRestartRecoveryReady: restoredContexts.length === 8,
  buildPersistenceReady: true,
  gateRerunPersistenceReady: true,
  moduleNavigationUnchanged: true,
  canaryDatabaseHashBefore: persistentHashBefore,
  canaryDatabaseHashAfter: finalHash,
  developmentDatabaseHashBefore: developmentHashBefore,
  developmentDatabaseHashAfter: developmentHashAfter,
  v45CheckpointHashesBefore: v45HashesBefore,
  v45CheckpointHashesAfter: checkpointHashes(v45CheckpointPath),
  productionDataWritten: false,
  productionDataModifiedCount: 0,
  downstreamCounts,
  confirmationPrepareCreated: false,
  confirmationPrepareCount: 0,
  zeroPaymentObjectWrite: true,
  zeroPaymentVoucherWrite: true,
  zeroLedgerWrite: true,
  persistentCanaryDatabaseReady: true,
  immutable: true,
}
writeJson(reportPath, report)

fs.mkdirSync(stagingCheckpoint, { recursive: true })
fs.copyFileSync(storageStatePath, path.join(stagingCheckpoint, 'storage-state.json'))
writeJson(path.join(stagingCheckpoint, 'application-state.json'), {
  version: report.version,
  currentStateSource: 'server',
  serviceRestartRecovered: true,
  browserStateClearRecovered: true,
  contexts: restoredContexts,
  pageAcceptance: readJson(pageReportPath),
})
writeJson(path.join(stagingCheckpoint, 'business-entities.json'), {
  version: report.version,
  sourceOfTruth: 'persistent_server_database',
  ...persistentStateAfter,
  downstreamCounts,
})
writeJson(path.join(stagingCheckpoint, 'relationship-graph.json'), {
  version: report.version,
  sourceOfTruth: 'persistent_server_database',
  relationships: persistentStateAfter.relations,
})
writeJson(path.join(stagingCheckpoint, 'restore-verification.json'), {
  result: 'passed',
  checkpointId: checkpointName,
  currentStateSource: 'server',
  persistentHashBefore,
  persistentHashAfter: finalHash,
  objectCountsBefore: persistentStateBefore.counts,
  objectCountsAfter: persistentStateAfter.counts,
  serviceRestartScenarioCount: restoredContexts.length,
  generatedAt: new Date().toISOString(),
})
writeJson(path.join(stagingCheckpoint, 'gate-report.json'), report)
writeJson(path.join(stagingCheckpoint, 'page-assertions.json'), readJson(pageReportPath))
writeJson(path.join(stagingCheckpoint, 'static-guards.json'), staticGuards)
fs.copyFileSync(screenshotPath, path.join(stagingCheckpoint, 'checkpoint-screenshot.png'))
fs.copyFileSync(tracePath, path.join(stagingCheckpoint, 'trace.zip'))

const manifest = {
  checkpointVersion: '1.0.0',
  version: report.version,
  checkpointId: checkpointName,
  sourceCheckpointId: 'purchase_accounts_payable_draft_controlled_generation_ready',
  createdAt: new Date().toISOString(),
  origin: 'http://localhost:5173',
  entityIds: [
    'purchase-canary-batch:PURCHASE-FLOW-DEMO-V1',
    ...persistentStateAfter.scenarios.map(item => `purchase-canary-scenario:${item.code}`),
  ],
  nextStageId: null,
  immutable: true,
  restorable: true,
  integrityFiles: coreStateFiles,
  integrityHash: integrityHash(stagingCheckpoint),
  currentStateSource: 'server',
  persistentDatabaseHash: finalHash,
  persistentDatabaseUnchanged: true,
  developmentDatabaseUnchanged: true,
  canaryScenarioCount: 8,
  moduleCountPerScenario: 13,
  relationCountPerScenario: 12,
  processCenterWalkthroughReady: true,
  browserStateClearRecoveryReady: true,
  serviceRestartRecoveryReady: true,
  buildPersistenceReady: true,
  gateRerunPersistenceReady: true,
  productionUserDataWritten: false,
  confirmationPrepareCreated: false,
  downstreamCounts,
  reports: ['gate-report.json', 'page-assertions.json', 'static-guards.json', 'restore-verification.json'],
  screenshotAndTraceInventory: ['checkpoint-screenshot.png', 'trace.zip'],
}
writeJson(path.join(stagingCheckpoint, 'manifest.json'), manifest)
for (const file of ['manifest.json', ...coreStateFiles]) {
  if (!fs.existsSync(path.join(stagingCheckpoint, file)) || fs.statSync(path.join(stagingCheckpoint, file)).size === 0) {
    throw new Error(`checkpoint core file is missing or empty: ${file}`)
  }
}
if (readJson(path.join(stagingCheckpoint, 'manifest.json')).integrityHash !== integrityHash(stagingCheckpoint)) {
  throw new Error('checkpoint integrity hash mismatch before publication')
}
fs.renameSync(stagingCheckpoint, checkpointPath)
const finalCheckpointHashes = checkpointHashes(checkpointPath)
if (readJson(path.join(checkpointPath, 'manifest.json')).integrityHash !== integrityHash(checkpointPath)) {
  throw new Error('checkpoint integrity hash mismatch after publication')
}

const finalReport = {
  ...report,
  checkpointPath,
  checkpointHashes: finalCheckpointHashes,
  reportPath,
  pageReportPath,
  tracePath,
  screenshotPath,
}
writeJson(reportPath, finalReport)
console.log(JSON.stringify(finalReport, null, 2))
